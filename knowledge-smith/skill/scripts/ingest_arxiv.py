#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27",
#   "markdownify>=0.13",
#   "python-frontmatter>=1.1",
#   "pyyaml>=6.0",
# ]
# ///
"""Write an arXiv paper note + raw assets into the active vault.

Thin orchestrator: the agent extracts metadata, picks the slug, drafts
the body markdown. This script downloads the PDF + ar5iv body and
writes the note via merge_frontmatter (preserving user edits on
re-ingest).

Required JSON keys:
    title, slug, year, authors, arxiv  (and links.paper)

The agent is expected to set:
    links.paper = "https://arxiv.org/abs/<id>"

The script auto-fills:
    raw_pdf, raw_md, links.raw, parser

Examples:
  uv run ingest_arxiv.py \\
    --metadata-json '{"arxiv":"1706.03762","title":"Attention Is All You Need",
                      "slug":"attention-is-all-you-need","year":2017,
                      "authors":["Ashish Vaswani","..."]}' \\
    --links-json '{"paper":"https://arxiv.org/abs/1706.03762"}' \\
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
    raw_split_path,
    today,
    validate_meta,
    write_frontmatter,
)
from _ks_helpers import (  # noqa: E402
    download_arxiv_pdf,
    emit_summary,
    fetch_ar5iv,
    load_body,
)

KIND = "paper"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--body-md-path",
                   help="path to a markdown file with the rendered note body")
    p.add_argument("--links-json",
                   help="JSON object overriding/augmenting metadata.links")
    p.add_argument("--force", action="store_true",
                   help="overwrite existing body and raw assets")
    args = p.parse_args(argv)

    vault = find_vault().path
    schema = load_schema(vault)
    info(f"vault: {vault}")

    raw_meta = parse_metadata_json(args.metadata_json)
    links_override = parse_links_json(args.links_json)
    raw_meta["links"] = {**(raw_meta.get("links") or {}), **links_override}

    arxiv_id = raw_meta.get("arxiv")
    if not arxiv_id:
        die(2, "paper metadata missing 'arxiv' id (use ingest_pdf.py for non-arxiv)")
    info(f"arxiv: {arxiv_id}")

    # Compute target paths up front from agent-supplied slug.
    # validate_meta runs after we attach script-derived raw_* paths so
    # the canonical links.raw is filled before write.
    slug = raw_meta.get("slug")
    year = raw_meta.get("year")
    if not slug or not year:
        die(2, "paper metadata missing slug/year (agent must supply)")
    basename = f"{year}-{slug}.md"
    stem = basename.removesuffix(".md")
    raw_pdf_target = raw_split_path(vault, KIND, "pdf", f"{stem}.pdf")
    raw_md_target = raw_split_path(vault, KIND, "md", f"{stem}.md")
    note_target = note_path(vault, KIND, basename)

    # Fetch ar5iv body markdown.
    parser_label: str
    body_md = fetch_ar5iv(arxiv_id)
    if body_md is None:
        parser_label = "ar5iv-failed"
        body_md = f"<!-- ar5iv unavailable for {arxiv_id}; see {arxiv_id}.pdf -->\n"
    else:
        parser_label = "ar5iv"
        info(f"ar5iv: {len(body_md)} chars")

    raw_md_meta = {
        "source": "paper",
        "arxiv": arxiv_id,
        "url": raw_meta.get("links", {}).get("paper")
               or f"https://arxiv.org/abs/{arxiv_id}",
        "title": raw_meta["title"],
        "authors": raw_meta.get("authors"),
        "year": year,
        "retrieved": today(),
        "parser": parser_label,
    }
    write_frontmatter(raw_md_target, raw_md_meta, body_md)
    info(f"wrote: {raw_md_target.relative_to(vault)}")

    # Fetch PDF.
    pdf_ok = download_arxiv_pdf(arxiv_id, raw_pdf_target)
    if pdf_ok:
        info(f"wrote: {raw_pdf_target.relative_to(vault)}")

    # Fold script-derived fields into the metadata before validation.
    raw_meta["raw_pdf"] = raw_pdf_target.relative_to(vault).as_posix() if pdf_ok else None
    raw_meta["raw_md"] = raw_md_target.relative_to(vault).as_posix()
    raw_meta["parser"] = parser_label
    raw_meta["links"].setdefault(
        "paper", f"https://arxiv.org/abs/{arxiv_id}",
    )
    raw_meta["links"].setdefault("raw", f"[[raw/papers/md/{stem}]]")

    meta = validate_meta(raw_meta, KIND, schema)

    # Body: agent-supplied (verbatim). Empty body is allowed; merge_frontmatter
    # preserves prior body on update unless --force.
    note_body = load_body(args.body_md_path, raw_meta.get("body"))

    is_new = merge_frontmatter(note_target, meta, note_body, force_body=args.force)
    info(f"{'wrote' if is_new else 'updated'}: {note_target.relative_to(vault)}")

    emit_summary([
        ("note", note_target),
        ("raw_md", raw_md_target),
        ("raw_pdf", raw_pdf_target if pdf_ok else None),
        ("parser", parser_label),
    ])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
