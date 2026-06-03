"""Copy sitemap.xml into every page directory.

The mkdocs-material JS fetches ``sitemap.xml`` relative to each ``<link
rel="alternate">`` URL to power the language switcher. With mkdocs-static-i18n only the
root ``sitemap.xml`` is generated, so every sub-directory request returns a 404.  This
hook copies the root sitemap into every directory that contains an ``index.html``,
silencing the warnings for both ``mkdocs serve`` and production.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def on_post_build(config: dict[str, Any], **kwargs: Any) -> None:
    site_dir = Path(config["site_dir"])
    sitemap = site_dir / "sitemap.xml"
    if not sitemap.exists():
        return
    for index_html in site_dir.rglob("index.html"):
        target = index_html.parent / "sitemap.xml"
        if not target.exists():
            shutil.copy2(sitemap, target)
