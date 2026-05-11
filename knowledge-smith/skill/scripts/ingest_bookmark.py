#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1", "pyyaml>=6.0"]
# ///
"""Write a blog, post, github, or course bookmark note into the active vault.

Thin orchestrator. The agent extracts metadata (title, description,
author/instructor, owner/repo for github) by WebFetch'ing the URL,
picks the slug, and supplies the rendered note body. This script
validates the metadata against the schema and writes the note via
merge_frontmatter.

Required JSON keys (per kind):
    blog:    title, slug          (and links.source)
    post:    title, slug          (and links.source)
    github:  title, slug          (and links.source) — slug is "owner-repo"
    course:  title, slug          (and links.source)

Examples:
  uv run ingest_bookmark.py --kind blog --metadata-json '{
      "title":"Eugene Yan", "slug":"eugene-yan",
      "author":"Eugene Yan", "description":"Applied ML / recsys."
  }' --links-json '{"source":"https://eugeneyan.com/"}' \\
     --body-md-path /tmp/note-body.md

  uv run ingest_bookmark.py --kind github --metadata-json '{
      "title":"openai/whisper", "slug":"openai-whisper",
      "owner":"openai", "repo":"whisper",
      "description":"Robust speech recognition"
  }' --links-json '{"source":"https://github.com/openai/whisper",
                     "code":"https://github.com/openai/whisper"}'
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    basename_from,
    die,
    find_vault,
    info,
    load_schema,
    merge_frontmatter,
    note_path,
    parse_links_json,
    parse_metadata_json,
    validate_meta,
)
from _ks_helpers import emit_summary, load_body  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", choices=("blog", "post", "github", "course"),
                   required=True)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--body-md-path",
                   help="path to a markdown file with the rendered note body")
    p.add_argument("--links-json",
                   help="JSON object overriding/augmenting metadata.links")
    p.add_argument("--force", action="store_true",
                   help="overwrite existing body")
    args = p.parse_args(argv)

    vault = find_vault().path
    schema = load_schema(vault)
    info(f"vault: {vault}")
    info(f"kind:  {args.kind}")

    raw_meta = parse_metadata_json(args.metadata_json)
    links_override = parse_links_json(args.links_json)
    raw_meta["links"] = {**(raw_meta.get("links") or {}), **links_override}

    source_url = raw_meta.get("links", {}).get("source")
    if not source_url:
        die(2, "links.source is required (pass via --links-json or in --metadata-json)")
    parsed = urlparse(source_url)
    if not (parsed.scheme and parsed.netloc):
        die(2, f"links.source not a usable URL: {source_url!r}")

    meta = validate_meta(raw_meta, args.kind, schema)
    basename = basename_from(meta, args.kind, schema)
    target = note_path(vault, args.kind, basename)

    note_body = load_body(args.body_md_path, raw_meta.get("body"))
    is_new = merge_frontmatter(target, meta, note_body, force_body=args.force)
    info(f"{'wrote' if is_new else 'updated'}: {target.relative_to(vault)}")

    emit_summary([("note", target), ("kind", args.kind)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
