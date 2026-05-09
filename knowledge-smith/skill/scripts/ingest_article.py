#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1"]
# ///
"""Ingest a Web Clipper markdown file into the active vault.

Reads frontmatter the clipper produced (url, title, author, publication,
published), normalizes it, copies the file under raw/articles/<year>-<slug>.md
preserving the clipper's original keys under a `clipper:` block, and writes
the article note to notes/articles/<year>-<slug>.md with read=false.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    die,
    find_vault,
    info,
    note_path,
    raw_path,
    read_frontmatter,
    refuse_if_exists,
    sha1_short,
    slugify,
    stub_filename,
    today,
    write_frontmatter,
)


def _parse_year(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.year
    s = str(value).strip()
    m = re.search(r"(\d{4})", s)
    return int(m.group(1)) if m else None


def _excerpt(body: str, n: int = 200) -> str:
    text = re.sub(r"\s+", " ", body).strip()
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0] + "…"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("path", help="Web Clipper markdown file")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    args = p.parse_args(argv)

    src = Path(args.path).expanduser().resolve()
    if not src.is_file():
        die(2, f"not a file: {src}")

    try:
        clipper_meta, body = read_frontmatter(src)
    except Exception as exc:
        die(2, f"could not parse {src}: {exc}")

    url = clipper_meta.get("url") or clipper_meta.get("source")
    if not url:
        die(2, f"clipper file missing 'url' in frontmatter: {src}")
    title = clipper_meta.get("title") or src.stem
    author = clipper_meta.get("author") or clipper_meta.get("byline")
    publication = clipper_meta.get("publication") or clipper_meta.get("site")
    published = clipper_meta.get("published") or clipper_meta.get("date")
    year = _parse_year(published) or _parse_year(today())

    slug = slugify(title)
    article_id = sha1_short(url)
    stub = stub_filename(year, slug)

    vault = find_vault().path
    raw_target = raw_path(vault, "article", stub)
    note_target = note_path(vault, "article", stub)

    refuse_if_exists(raw_target, args.force)
    refuse_if_exists(note_target, args.force)

    info(f"vault: {vault}")
    info(f"clipper: {src}")
    info(f"url: {url}")
    info(f"slug: {slug}")

    # 1. Move the clipper file to raw/articles/, preserving original keys.
    raw_meta = {
        "type": "raw-article",
        "url": url,
        "title": title,
        "author": author,
        "publication": publication,
        "published": str(published) if published else None,
        "retrieved": today(),
        "id": article_id,
        "clipper": dict(clipper_meta),
    }
    raw_target.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter(raw_target, raw_meta, body)
    # Original clipper file: leave it in place. The user may have other
    # consumers; we don't move/delete user files.
    info(f"wrote: {raw_target.relative_to(vault)}")

    # 2. Article note
    note_meta = {
        "type": "note",
        "kind": "article",
        "slug": slug,
        "title": title,
        "created": today(),
        "updated": today(),
        "read": False,
        "tags": [],
        "year": year,
        "url": url,
        "author": author,
        "publication": publication,
        "retrieved": today(),
        "raw_md": raw_target.relative_to(vault).as_posix(),
        "clipper": "obsidian-web-clipper",
    }
    excerpt = _excerpt(body)
    note_body = (
        f"# {title}\n\n"
        f"> *{author or 'unknown'}* — {publication or 'unknown'}, {year}\n\n"
        "## TL;DR\n\n"
        "(stub)\n\n"
        "## Excerpt\n\n"
        f"{excerpt}\n\n"
        "## Notes\n\n"
        "(your synthesis)\n\n"
        "## Source\n\n"
        f"- Raw markdown: [[{raw_target.relative_to(vault).with_suffix('').as_posix()}]]\n"
        f"- Original URL: <{url}>\n"
    )
    write_frontmatter(note_target, note_meta, note_body)
    info(f"wrote: {note_target.relative_to(vault)}")

    print(f"note={note_target}")
    print(f"raw_md={raw_target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
