"""Execute the code examples in the documentation.

Documented code drifts silently. This repo already had three examples that
could not run: ``docs/en/backends/networkx.md`` called ``nx.info(G)``,
removed in NetworkX 3.x while ``pyproject.toml`` requires ``>=3.6.1``, and
``docs/en/backends/rdf.md`` documented a ``DDIFragmentParser()`` /
``.parse(path)`` API that has never existed. Nothing caught any of it,
because nothing ran the examples.

This runs them. A fenced block opts in by carrying a ``<!-- runnable -->``
comment on the line before it, which keeps illustrative fragments out while
making the executable ones genuinely executable. Blocks run in a temporary
directory with ``FIXTURE`` pointing at a real DDI file, so an example can do
useful work without depending on the Git LFS demo corpus -- which is not
materialised in CI and is why several demo scripts cannot be run here at
all.

French pages are covered too: the prose differs but the code must not.

An example may need an optional extra. ``rdflib``, ``pyshacl`` and
``networkx`` are in ``[dev]`` so their examples genuinely run in CI; a block
needing anything heavier is skipped with a reason rather than failing, which
is what stops the docs from dictating the dev install.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
FIXTURES = REPO_ROOT / "tests" / "fixtures"

# A block opts in with a preceding ``<!-- runnable -->`` marker.
_RUNNABLE = re.compile(
    r"<!--\s*runnable\s*-->\s*\n```(python|bash)\n(.*?)\n```",
    re.DOTALL,
)


def _blocks() -> list[tuple[str, str, str]]:
    """Return ``(page, language, source)`` for every opted-in block."""
    found: list[tuple[str, str, str]] = []
    for page in sorted(DOCS.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        for language, source in _RUNNABLE.findall(text):
            found.append((str(page.relative_to(REPO_ROOT)), language, source))
    return found


BLOCKS = _blocks()


def test_documentation_contains_runnable_examples() -> None:
    """Guard the guard: a broken marker would silently disable this file."""
    assert BLOCKS, (
        "no runnable examples found -- check the <!-- runnable --> markers "
        "still match the pattern in _RUNNABLE"
    )


def _required_third_party(source: str) -> set[str]:
    """Return the non-stdlib, non-ddigraph packages an example imports.

    Examples may legitimately need an optional extra -- the NetworkX page
    imports ``networkx``. Rather than force every extra into ``[dev]``, a
    block whose dependency is absent is skipped with a reason, so the rest
    still run.
    """
    import ast
    import sys

    try:
        tree = ast.parse(source)
    except SyntaxError:  # a bash block; handled by its own import lines
        return set()

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])

    return {root for root in roots if root != "ddigraph" and root not in sys.stdlib_module_names}


@pytest.mark.parametrize(
    ("page", "language", "source"),
    BLOCKS,
    ids=[f"{page}#{index}" for index, (page, _lang, _src) in enumerate(BLOCKS)],
)
def test_documented_example_runs(page: str, language: str, source: str, tmp_path: Path) -> None:
    """Every opted-in example must execute without error."""
    for package in sorted(_required_third_party(source)):
        pytest.importorskip(package, reason=f"{page} example needs the {package} extra")

    script = tmp_path / ("example.py" if language == "python" else "example.sh")
    script.write_text(source, encoding="utf-8")

    command = (
        [sys.executable, str(script)]
        if language == "python"
        else ["bash", "-euo", "pipefail", str(script)]
    )

    result = subprocess.run(
        command,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
        env=_env(),
    )

    assert result.returncode == 0, (
        f"{page} example failed\n"
        f"--- source ---\n{source}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


_IMPORT = re.compile(r"^\s*from (ddigraph[\w.]*) import ([^\n(]+)$", re.M)


def _documented_imports() -> list[tuple[str, str, str]]:
    """Return ``(page, module, name)`` for every documented ddigraph import."""
    found: list[tuple[str, str, str]] = []
    for page in sorted(DOCS.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        for module, names in _IMPORT.findall(text):
            for raw in names.split(","):
                name = raw.strip().split(" as ")[0].strip()
                if name:
                    found.append((str(page.relative_to(REPO_ROOT)), module, name))
    return found


IMPORTS = _documented_imports()


@pytest.mark.parametrize(
    ("page", "module", "name"),
    IMPORTS,
    ids=[f"{module}.{name}" for _page, module, name in IMPORTS],
)
def test_documented_import_resolves(page: str, module: str, name: str) -> None:
    """Every ``from ddigraph... import X`` in the docs must actually exist.

    This is broader than running the examples: it also covers blocks that
    need a database and so cannot be executed here. It caught three dead
    references -- ``CDILoader``, which has never existed, and a
    ``ddigraph.settings`` module that is called ``ddigraph.config`` -- both
    of which had been sitting in the getting-started pages.
    """
    import importlib

    imported = importlib.import_module(module)
    if hasattr(imported, name):
        return
    # A submodule is a legitimate import target but is not an attribute of
    # its package until it has been imported.
    importlib.import_module(f"{module}.{name}")


def test_docs_do_not_use_the_parser_api_that_never_existed() -> None:
    """``DDIFragmentParser()`` takes a path; there is no ``.parse()``.

    Twenty-five occurrences of this idiom were documented across seven
    pages in both languages. The real class takes the path in ``__init__``
    and exposes ``parse_batches()``; ``iter_graph`` is the supported way to
    stream any flavor.
    """
    offenders = [
        str(page.relative_to(REPO_ROOT))
        for page in DOCS.rglob("*.md")
        if "DDIFragmentParser()" in page.read_text(encoding="utf-8")
    ]

    assert not offenders, f"non-existent parser API documented in: {offenders}"


# A fenced block nested in a tab or admonition is indented, and so is its
# closing fence. Capturing the indent and requiring the same indent on the
# close is what stops the match running past it to the next fence at column
# zero, swallowing the prose in between.
_PY_BLOCK = re.compile(
    r"^(?P<indent>[ \t]*)```python\n(?P<source>.*?)\n(?P=indent)```",
    re.DOTALL | re.MULTILINE,
)


def _non_runnable_python_blocks() -> list[tuple[str, str]]:
    """Return ``(page, source)`` for Python blocks the suite does not execute."""
    found: list[tuple[str, str]] = []
    for page in sorted(DOCS.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        runnable = {source for _language, source in _RUNNABLE.findall(text)}
        for match in _PY_BLOCK.finditer(text):
            source = match.group("source")
            if source not in runnable:
                found.append((str(page.relative_to(REPO_ROOT)), source))
    return found


NON_RUNNABLE = _non_runnable_python_blocks()


@pytest.mark.parametrize(
    ("page", "source"),
    NON_RUNNABLE,
    ids=[f"{page}#{index}" for index, (page, _src) in enumerate(NON_RUNNABLE)],
)
def test_non_runnable_python_at_least_parses(page: str, source: str) -> None:
    """A block that cannot be executed must still be valid Python.

    Plenty of examples legitimately cannot run here -- they need a database,
    a Gremlin server, or an API key. Executing them is not an option, but
    *parsing* them is, and it catches the failure that matters most to a
    reader: code that cannot possibly work when pasted.

    It found one. ``backends/gremlin.md`` had a nested ``for`` with no
    indented body, in both languages, so the example raised
    ``IndentationError`` before reaching the API it was demonstrating -- and
    it used ``fragment.element_type`` / ``.fragment_id``, which no object in
    the package has.

    Blocks nested inside tabs or admonitions arrive indented; dedent before
    parsing or every one of them fails on column alone.
    """
    import ast
    import textwrap

    try:
        ast.parse(textwrap.dedent(source))
    except SyntaxError as exc:
        pytest.fail(f"{page} has a Python block that does not parse: {exc}\n\n{source}")


def test_docs_do_not_name_a_class_that_never_existed() -> None:
    """``CDILoader`` is not a thing and never has been.

    It sat in the glossary and the architecture page in both languages,
    describing how ddigraph "loads DDI-CDI files". The real entry points
    are ``parse_cdi_batches()`` and, since 0.5.0, ``iter_graph()``. The
    import test above cannot catch this: the name appeared in prose and in
    a heading, never in an ``import`` line.
    """
    offenders = [
        str(page.relative_to(REPO_ROOT))
        for page in DOCS.rglob("*.md")
        if "CDILoader" in page.read_text(encoding="utf-8")
    ]

    assert not offenders, f"non-existent class documented in: {offenders}"


_REPO_PATH = re.compile(r"(?<![\w/])((?:demo|scripts|src|tests|audit|hooks)/[\w./-]+\.\w+)")

# ``(page suffix, path)`` pairs that name a file which does not exist, on
# purpose. Keyed by page as well as path so the exemption stays narrow: a new
# reference to ``demo/load_rdf.py`` from any other page still fails.
_INTENTIONALLY_ABSENT: frozenset[tuple[str, str]] = frozenset(
    {
        # Historical: "before 0.5.0 this needed demo/load_rdf.py". The point
        # of the sentence is that the file is gone.
        ("advanced/rdf-case-study.md", "demo/load_rdf.py"),
        # A file the reader is being told to create, not one that ships.
        ("project/contributing.md", "demo/load_mybackend.py"),
        # A design document describing a module it explicitly defers.
        ("project/dsl-design.md", "src/ddigraph/ingest/_coerce.py"),
    }
)


def test_documented_repo_paths_exist() -> None:
    """Every repo file a doc page points at must actually be there.

    Deleting a file is easy; finding the pages that named it is not.
    ``demo/load_rdf.py`` and ``demo/export_files.py`` went away in 0.5.0 and
    left eleven references behind across both languages -- including two
    GitHub links a reader would click and a ``python demo/export_files.py``
    command they would run.

    The changelog is exempt: describing what a release removed means naming
    files that no longer exist, and that entry stays correct forever.
    """
    offenders: dict[str, list[str]] = {}
    for page in sorted(DOCS.rglob("*.md")):
        if page.name == "changelog.md":
            continue
        # ``docs/en/advanced/rdf-case-study.md`` -> ``advanced/rdf-case-study.md``
        suffix = page.relative_to(DOCS).as_posix().split("/", 1)[1]
        referenced = set(_REPO_PATH.findall(page.read_text(encoding="utf-8")))
        gone = sorted(
            ref
            for ref in referenced
            if not (REPO_ROOT / ref).exists() and (suffix, ref) not in _INTENTIONALLY_ABSENT
        )
        if gone:
            offenders[str(page.relative_to(REPO_ROOT))] = gone

    assert not offenders, f"docs point at files that do not exist: {offenders}"


def _env() -> dict[str, str]:
    """Environment for an example: the repo on the path, fixtures located."""
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    # Bash examples type ``ddigraph`` and ``python`` the way a reader would,
    # so the interpreter running the tests has to be the one they find --
    # otherwise a shell example silently tests the system Python instead.
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])
    env["FIXTURE"] = str(FIXTURES / "fragment_instance.xml")
    env["CODEBOOK_FIXTURE"] = str(FIXTURES / "codebook_sample.xml")
    env["CDI_FIXTURE"] = str(FIXTURES / "cdi_sample.xml")
    # Examples must not reach a database; anything that tries should fail
    # loudly here rather than hang against a default localhost URI.
    env["DDIGRAPH_NEO4J_URI"] = "bolt://127.0.0.1:1"
    return env
