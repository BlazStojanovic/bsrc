#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1"]
# ///
"""Write an article note + raw clipper file into the active vault.

The agent reads the Web Clipper file directly and extracts metadata +
TL;DR, then passes the metadata via --metadata-json. This script copies
the clipper file into raw/articles/ (preserving the clipper's frontmatter
under a `clipper:` block) and writes the summary note.

Required JSON keys: title, url.
Optional: author, publication, year, slug, tldr, retrieved.

The agent supplies a real `tldr` field — 1-2 sentences distilled from
reading the body — replacing the old regex-truncated 200-char excerpt.

Examples:
  uv run ingest_article.py \\
    --metadata-json '{
      "title": "...",
      "url": "...",
      "author": "...",
      "publication": "...",
      "year": 2024,
      "tldr": "Author argues X by ..."
    }' \\
    --clipper-path /tmp/clipper.md
"""

from __future__ import annotations

import argparse
import sys
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
    validate_metadata_json,
    write_frontmatter,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--clipper-path", required=True,
                   help="path to the Web Clipper markdown file")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    args = p.parse_args(argv)

    src = Path(args.clipper_path).expanduser().resolve()
    if not src.is_file():
        die(2, f"--clipper-path is not a file: {src}")

    meta = validate_metadata_json(args.metadata_json, "article")
    try:
        clipper_meta, body = read_frontmatter(src)
    except Exception as exc:
        die(2, f"could not parse clipper file {src}: {exc}")

    vault = find_vault().path
    info(f"vault: {vault}")
    info(f"clipper: {src}")

    title = meta["title"]
    url = meta["url"]
    slug = meta.get("slug") or slugify(title)
    year = meta.get("year")
    article_id = sha1_short(url)
    stub = stub_filename(year, slug)

    raw_target = raw_path(vault, "article", stub)
    note_target = note_path(vault, "article", stub)
    refuse_if_exists(raw_target, args.force)
    refuse_if_exists(note_target, args.force)

    info(f"url: {url}")
    info(f"slug: {slug}")

    raw_meta = {
        "type": "raw-article",
        "url": url,
        "title": title,
        "author": meta.get("author"),
        "publication": meta.get("publication"),
        "published": meta.get("published") or (str(year) if year else None),
        "retrieved": today(),
        "id": article_id,
        "clipper": dict(clipper_meta),
    }
    raw_target.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter(raw_target, raw_meta, body)
    info(f"wrote: {raw_target.relative_to(vault)}")

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
        "author": meta.get("author"),
        "publication": meta.get("publication"),
        "retrieved": today(),
        "raw_md": raw_target.relative_to(vault).as_posix(),
        "clipper": "obsidian-web-clipper",
    }
    tldr = meta.get("tldr") or "(stub)"
    note_body = (
        f"# {title}\n\n"
        f"> *{meta.get('author') or 'unknown'}* — "
        f"{meta.get('publication') or 'unknown'}, {year or '?'}\n\n"
        f"## TL;DR\n\n{tldr}\n\n"
        "## Notes\n\n(your synthesis)\n\n"
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
