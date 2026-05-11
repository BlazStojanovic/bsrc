#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27",
#   "python-frontmatter>=1.1",
#   "pyyaml>=6.0",
# ]
# ///
"""Write a non-arXiv paper note + raw assets into the active vault.

Thin orchestrator: the agent supplies metadata, slug, body markdown,
and (optionally) the raw extracted PDF body via `--raw-md-path`. This
script downloads/copies the PDF into raw/papers/pdf/ and writes the
note via merge_frontmatter.

Body extraction tiers (agent picks one, runs it externally):
  - tier 1: skip --raw-md-path; the agent reads the PDF directly via
            Claude's Read tool or doesn't need the full body.
  - tier 2: agent runs `helpers/pdftotext.sh paper.pdf > /tmp/raw.md`
            and passes `--raw-md-path /tmp/raw.md --parser pdftotext`.
  - tier 3: agent runs `helpers/run_docling.py paper.pdf > /tmp/raw.md`
            and passes `--raw-md-path /tmp/raw.md --parser docling`.

Required JSON keys: title, slug, year, authors (and links.paper).

Examples:
  uv run ingest_pdf.py --pdf-path /tmp/paper.pdf \\
    --metadata-json '{...}' --body-md-path /tmp/note-body.md \\
    --raw-md-path /tmp/raw.md --parser pdftotext
"""

from __future__ import annotations

import argparse
import sys
import tempfile
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
    copy_into_raw,
    download_pdf,
    emit_summary,
    load_body,
)

KIND = "paper"


def _materialize_pdf(pdf_path: str | None, pdf_url: str | None, tmpdir: Path) -> Path:
    if pdf_path:
        p = Path(pdf_path).expanduser().resolve()
        if not p.is_file():
            die(2, f"--pdf-path is not a file: {p}")
        return p
    if pdf_url:
        info(f"downloading PDF: {pdf_url}")
        target = tmpdir / "input.pdf"
        if not download_pdf(pdf_url, target):
            die(5, f"PDF download failed: {pdf_url}")
        return target
    die(2, "must pass --pdf-path or --pdf-url")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--pdf-path",
                   help="local PDF path (or pass --pdf-url)")
    p.add_argument("--pdf-url",
                   help="PDF URL to download (or pass --pdf-path)")
    p.add_argument("--body-md-path",
                   help="path to a markdown file with the rendered note body")
    p.add_argument("--raw-md-path",
                   help="path to a markdown file with the extracted PDF body "
                        "(from pdftotext/docling/etc.)")
    p.add_argument("--parser",
                   choices=("read", "pdftotext", "docling"),
                   default="read",
                   help="provenance label for the raw body extraction tier")
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

    slug = raw_meta.get("slug")
    year = raw_meta.get("year")
    if not slug or not year:
        die(2, "paper metadata missing slug/year (agent must supply)")
    basename = f"{year}-{slug}.md"
    stem = basename.removesuffix(".md")
    raw_pdf_target = raw_split_path(vault, KIND, "pdf", f"{stem}.pdf")
    raw_md_target = raw_split_path(vault, KIND, "md", f"{stem}.md")
    note_target = note_path(vault, KIND, basename)

    with tempfile.TemporaryDirectory() as tdir:
        tmpdir = Path(tdir)
        pdf_src = _materialize_pdf(args.pdf_path, args.pdf_url, tmpdir)
        if copy_into_raw(pdf_src, raw_pdf_target, force=args.force):
            info(f"wrote: {raw_pdf_target.relative_to(vault)}")
        else:
            info(f"raw_pdf already present: {raw_pdf_target.relative_to(vault)}")

    if args.raw_md_path:
        body_extracted = Path(args.raw_md_path).expanduser().read_text(encoding="utf-8")
    else:
        body_extracted = (
            f"<!-- raw body not extracted (parser={args.parser}); see {stem}.pdf -->\n"
        )
    raw_md_meta = {
        "source": "paper",
        "url": raw_meta.get("links", {}).get("paper") or args.pdf_url,
        "title": raw_meta["title"],
        "authors": raw_meta.get("authors"),
        "year": year,
        "retrieved": today(),
        "parser": args.parser,
    }
    write_frontmatter(raw_md_target, raw_md_meta, body_extracted)
    info(f"wrote: {raw_md_target.relative_to(vault)}")

    raw_meta["raw_pdf"] = raw_pdf_target.relative_to(vault).as_posix()
    raw_meta["raw_md"] = raw_md_target.relative_to(vault).as_posix()
    raw_meta["parser"] = args.parser
    raw_meta["links"].setdefault("raw", f"[[raw/papers/md/{stem}]]")

    meta = validate_meta(raw_meta, KIND, schema)
    note_body = load_body(args.body_md_path, raw_meta.get("body"))
    is_new = merge_frontmatter(note_target, meta, note_body, force_body=args.force)
    info(f"{'wrote' if is_new else 'updated'}: {note_target.relative_to(vault)}")

    emit_summary([
        ("note", note_target),
        ("raw_md", raw_md_target),
        ("raw_pdf", raw_pdf_target),
        ("parser", args.parser),
    ])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
