#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1", "pyyaml>=6.0"]
# ///
"""Write an article note + raw clipper file into the active vault.

Thin orchestrator: the agent reads the clipper file, extracts metadata
+ TL;DR, picks the slug. This script copies the clipper into
raw/articles/ (preserving its original frontmatter under `clipper:`)
and writes the summary note.

Required JSON keys: title, slug, year (and links.source).

Examples:
  uv run ingest_article.py --clipper-path /tmp/clipper.md \\
    --metadata-json '{"title":"...","slug":"...","year":2024,
                       "author":"...","publication":"...",
                       "tldr":"..."}' \\
    --links-json '{"source":"https://example.com/post"}' \\
    --body-md-path /tmp/note-body.md
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
    load_schema,
    merge_frontmatter,
    note_path,
    parse_links_json,
    parse_metadata_json,
    raw_path,
    today,
    validate_meta,
)
from _ks_helpers import copy_clipper, emit_summary, load_body  # noqa: E402

KIND = "article"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--clipper-path", required=True,
                   help="path to the Web Clipper markdown file")
    p.add_argument("--body-md-path",
                   help="path to a markdown file with the rendered note body")
    p.add_argument("--links-json",
                   help="JSON object overriding/augmenting metadata.links")
    p.add_argument("--force", action="store_true",
                   help="overwrite existing body and raw assets")
    args = p.parse_args(argv)

    src = Path(args.clipper_path).expanduser().resolve()
    if not src.is_file():
        die(2, f"--clipper-path is not a file: {src}")

    vault = find_vault().path
    schema = load_schema(vault)
    info(f"vault: {vault}")
    info(f"clipper: {src}")

    raw_meta = parse_metadata_json(args.metadata_json)
    links_override = parse_links_json(args.links_json)
    raw_meta["links"] = {**(raw_meta.get("links") or {}), **links_override}

    slug = raw_meta.get("slug")
    year = raw_meta.get("year")
    if not slug or not year:
        die(2, "article metadata missing slug/year (agent must supply)")
    basename = f"{year}-{slug}.md"
    raw_target = raw_path(vault, KIND, basename)
    note_target = note_path(vault, KIND, basename)

    copy_clipper(src, raw_target, force=args.force)
    info(f"wrote: {raw_target.relative_to(vault)}")

    raw_meta["raw_md"] = raw_target.relative_to(vault).as_posix()
    raw_meta["clipper"] = "obsidian-web-clipper"
    raw_meta.setdefault("retrieved", today())
    raw_meta["links"].setdefault(
        "raw", f"[[{raw_target.relative_to(vault).with_suffix('').as_posix()}]]",
    )

    meta = validate_meta(raw_meta, KIND, schema)
    note_body = load_body(args.body_md_path, raw_meta.get("body"))
    is_new = merge_frontmatter(note_target, meta, note_body, force_body=args.force)
    info(f"{'wrote' if is_new else 'updated'}: {note_target.relative_to(vault)}")

    emit_summary([
        ("note", note_target),
        ("raw_md", raw_target),
    ])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
