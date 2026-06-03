"""Sync DDI schemas from the official DDI Alliance repositories.

The script downloads release archives for DDI-Lifecycle (DDI-L), DDI-Codebook (DDI-C),
and DDI Cross-Domain Integration (DDI-CDI), validates them, and refreshes
``schemas/ddi``, ``schemas/ddi-c``, and ``schemas/ddi-cdi`` respectively. Cached copies
of the archives are reused on subsequent runs. Use ``--check`` in CI to verify the
committed schemas match the pinned manifest without touching the network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

SCHEMAS_ROOT = Path("schemas")
CACHE_DIR = SCHEMAS_ROOT / ".cache"
MANIFEST_PATH = SCHEMAS_ROOT / "manifest.json"


# ---------------------------------------------------------------------------
# Schema family definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SchemaFamily:
    """A DDI schema family to sync from a remote repository."""

    family: str
    description: str
    source_repo: str
    version: str
    tag: str | None
    branch: str | None
    dest_dir: str
    source_dirs: Mapping[str, str]
    archive_sha256: str | None = None
    validation: _Validation | None = None

    @property
    def archive_url(self) -> str:
        ref = self.tag or self.branch or "main"
        return f"{self.source_repo}/archive/refs/{'tags' if self.tag else 'heads'}/{ref}.zip"

    def cache_path(self, cache_dir: Path) -> Path:
        safe_version = self.version.replace("/", "-")
        return cache_dir / f"{self.family}-{safe_version}.zip"


@dataclass(frozen=True)
class _Validation:
    """Optional content validation for a downloaded archive."""

    readme_path: str
    marker: str


FAMILIES: Mapping[str, SchemaFamily] = {
    "ddi-l": SchemaFamily(
        family="ddi-l",
        description="DDI-Lifecycle 3.3 XML Schemas",
        source_repo="https://github.com/ddialliance/ddi-l_3",
        version="3.3",
        tag="v3.3",
        branch=None,
        dest_dir="ddi",
        source_dirs={"XMLSchema/3_1": "v3_1", "XMLSchema/3_2": "v3_2", "XMLSchema/3_3": "v3_3"},
        archive_sha256=None,
        validation=_Validation(readme_path="readme.txt", marker="version 3.3"),
    ),
    "ddi-c": SchemaFamily(
        family="ddi-c",
        description="DDI-Codebook 2.6 XML Schemas",
        source_repo="https://github.com/ddialliance/ddi-c_2",
        version="2.6",
        tag=None,
        branch="master",
        dest_dir="ddi-c",
        source_dirs={"schemas": "."},
        archive_sha256=None,
        validation=_Validation(readme_path="readme.txt", marker="codebook"),
    ),
    "ddi-cdi": SchemaFamily(
        family="ddi-cdi",
        description="DDI-CDI 1.0 XML Schema and Ontology",
        source_repo="https://github.com/ddi-cdi/ddi-cdi",
        version="1.0",
        tag="v1.0",
        branch=None,
        dest_dir="ddi-cdi",
        source_dirs={
            "build/encoding/xml-schema": "xml-schema",
            "build/encoding/ontology": "ontology",
        },
        archive_sha256=None,
        validation=None,
    ),
}

ALL_FAMILY_KEYS = sorted(FAMILIES.keys())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--family",
        choices=[*ALL_FAMILY_KEYS, "all"],
        default="all",
        help="Schema family to sync: ddi-l, ddi-c, ddi-cdi, or all (default: all).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=CACHE_DIR,
        help="Directory to store cached release archives.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the current schemas against the manifest without downloading.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download archives even if cached copies exist.",
    )
    parser.add_argument(
        "--expected-archive-sha256",
        help="Override the expected archive checksum for the selected family.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_release(archive_url: str, destination: Path) -> Path:
    print(f"  Downloading {archive_url} ...")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(archive_url) as response:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            shutil.copyfileobj(response, tmp)
            tmp_path = Path(tmp.name)
    destination.write_bytes(tmp_path.read_bytes())
    tmp_path.unlink(missing_ok=True)
    return destination


def ensure_archive(
    family: SchemaFamily,
    cache_dir: Path,
    force: bool,
    expected_sha: str | None,
) -> tuple[Path, str]:
    cache_path = family.cache_path(cache_dir)
    if cache_path.exists() and not force:
        cached_sha = sha256_file(cache_path)
        if expected_sha is None or cached_sha == expected_sha:
            print(f"  Using cached archive: {cache_path}")
            return cache_path, cached_sha
        cache_path.unlink()

    try:
        archive_path = download_release(family.archive_url, cache_path)
    except (HTTPError, URLError) as error:
        raise SystemExit(f"Failed to download {family.archive_url}: {error}") from error

    archive_sha = sha256_file(archive_path)
    if expected_sha and archive_sha != expected_sha:
        archive_path.unlink(missing_ok=True)
        raise SystemExit(
            f"Downloaded archive checksum mismatch. expected={expected_sha} got={archive_sha}"
        )
    return archive_path, archive_sha


def extract_archive(archive_path: Path, temp_dir: Path) -> Path:
    with zipfile.ZipFile(archive_path) as zip_file:
        zip_file.extractall(temp_dir)
        top_level = {Path(name).parts[0] for name in zip_file.namelist() if not name.endswith("/")}
    if not top_level:
        raise SystemExit("Archive did not contain any files.")
    root = temp_dir / sorted(top_level)[0]
    if not root.exists():
        raise SystemExit(f"Expected extracted directory at {root} not found.")
    return root


def validate_contents(extracted_root: Path, family: SchemaFamily) -> None:
    if family.validation is None:
        return
    readme_path = extracted_root / family.validation.readme_path
    if not readme_path.exists():
        print(f"  Warning: validation file {family.validation.readme_path} not found, skipping.")
        return
    readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")
    if family.validation.marker.lower() not in readme_text.lower():
        raise SystemExit(
            f"Validation failed: {family.validation.readme_path} does not contain "
            f"expected marker '{family.validation.marker}'."
        )


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def sync_family(extracted_root: Path, dest_root: Path, family: SchemaFamily) -> None:
    for source_dir, dest_dir in family.source_dirs.items():
        src = extracted_root / source_dir
        if not src.exists():
            raise SystemExit(
                f"Expected source directory '{source_dir}' missing in {family.family} archive."
            )
        if dest_dir == ".":
            dest = dest_root
        else:
            dest = dest_root / dest_dir
        copy_tree(src, dest)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def build_manifest_entry(
    dest_root: Path,
    family: SchemaFamily,
    archive_sha: str | None,
) -> dict[str, object]:
    files: dict[str, str] = {}
    for path in sorted(dest_root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(dest_root).as_posix()
            files[rel] = sha256_file(path)
    return {
        "source": family.source_repo,
        "version": family.version,
        "tag": family.tag,
        "branch": family.branch,
        "archive_url": family.archive_url,
        "archive_sha256": archive_sha,
        "files": files,
    }


def load_manifest(manifest_path: Path) -> dict[str, object]:
    if not manifest_path.exists():
        raise SystemExit(
            f"Manifest not found at {manifest_path}. Run without --check to generate it."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise SystemExit("Manifest format invalid: expected a JSON object at top level.")
    return cast(dict[str, object], manifest)


def check_family_manifest(
    dest_root: Path,
    expected_files: dict[str, str],
    family_key: str,
) -> list[str]:
    """Check a single family's files against expected checksums.

    Return error lines.
    """
    current_files: dict[str, str] = {}
    if dest_root.exists():
        for path in sorted(dest_root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(dest_root).as_posix()
                current_files[rel] = sha256_file(path)

    missing = set(expected_files) - set(current_files)
    extra = set(current_files) - set(expected_files)
    mismatched = [
        p for p in expected_files if p in current_files and current_files[p] != expected_files[p]
    ]

    errors: list[str] = []
    if missing:
        errors.append(f"  [{family_key}] Missing files: {sorted(missing)}")
    if extra:
        errors.append(f"  [{family_key}] Unexpected files: {sorted(extra)}")
    if mismatched:
        errors.append(f"  [{family_key}] Checksum mismatch: {sorted(mismatched)}")
    return errors


def check_manifest(families_to_check: Sequence[str]) -> None:
    manifest = load_manifest(MANIFEST_PATH)
    all_errors: list[str] = []

    for key in families_to_check:
        family = FAMILIES[key]
        family_manifest = manifest.get(key)
        if family_manifest is None:
            all_errors.append(f"  [{key}] Not present in manifest.")
            continue
        if not isinstance(family_manifest, dict):
            all_errors.append(f"  [{key}] Invalid manifest entry.")
            continue
        expected_files = family_manifest.get("files", {})
        if not isinstance(expected_files, dict):
            all_errors.append(f"  [{key}] Invalid 'files' in manifest.")
            continue
        dest_root = SCHEMAS_ROOT / family.dest_dir
        all_errors.extend(check_family_manifest(dest_root, expected_files, key))

    if not all_errors:
        print("Schemas match manifest; no refresh required.")
    else:
        raise SystemExit("Schema validation failed:\n" + "\n".join(all_errors))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def sync_one_family(
    family: SchemaFamily,
    cache_dir: Path,
    force_download: bool,
    expected_sha: str | None,
) -> tuple[str, dict[str, object]]:
    """Download, validate, and extract a single schema family.

    Return manifest entry.
    """
    print(f"\n[{family.family}] {family.description}")
    archive_path, archive_sha = ensure_archive(family, cache_dir, force_download, expected_sha)

    dest_root = SCHEMAS_ROOT / family.dest_dir

    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_root = Path(tmp_dir)
        extracted_root = extract_archive(archive_path, temp_root)
        validate_contents(extracted_root, family)
        sync_family(extracted_root, dest_root, family)

    entry = build_manifest_entry(dest_root, family, archive_sha)
    print(f"  Synced to {dest_root} ({len(cast(dict[str, object], entry['files']))} files)")
    return family.family, entry


def main() -> int:
    args = parse_args()

    if args.family == "all":
        families_to_process = ALL_FAMILY_KEYS
    else:
        families_to_process = [args.family]

    if args.check:
        check_manifest(families_to_process)
        return 0

    # Load existing manifest to preserve entries for families not being updated
    existing_manifest: dict[str, object] = {}
    if MANIFEST_PATH.exists():
        existing_manifest = load_manifest(MANIFEST_PATH)

    expected_sha = args.expected_archive_sha256

    for key in families_to_process:
        family = FAMILIES[key]
        sha_override = expected_sha if len(families_to_process) == 1 else None
        family_key, entry = sync_one_family(
            family, args.cache_dir, args.force_download, sha_override or family.archive_sha256
        )
        existing_manifest[family_key] = entry

    MANIFEST_PATH.write_text(json.dumps(existing_manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nManifest updated: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
