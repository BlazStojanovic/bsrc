#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27",
#   "python-frontmatter>=1.1",
# ]
# ///
"""Write a non-arxiv paper note + raw assets into the active vault.

The agent extracts metadata (title, authors, year, abstract) by reading
the PDF directly with Claude's `Read` tool, then passes it via
--metadata-json. This script handles the file plumbing.

Body-extraction tiers (agent picks one):

  1. Metadata only          — pass nothing else; raw_md is a stub.
  2. Quick body             — agent runs `pdftotext PDF -` itself and
                              pipes via --body-md-path FILE.
  3. High-fidelity (docling) — pass --docling and the script runs
                              docling on the PDF. First run pulls
                              hundreds of MB of layout/OCR models.

Required JSON keys: title, authors (list), year (int).
Optional: abstract, doi, venue, url.

Examples:
  # tier 1: read PDF first via Read tool, supply only metadata
  uv run ingest_pdf.py --metadata-json '{"title":"...","authors":[...],"year":2024}' \
      --pdf-path /tmp/paper.pdf

  # tier 2: agent already extracted body
  uv run ingest_pdf.py --metadata-json '...' --pdf-path /tmp/paper.pdf \
      --body-md-path /tmp/paper.txt

  # tier 3: opt into docling
  uv run ingest_pdf.py --metadata-json '...' --pdf-path /tmp/paper.pdf --docling
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    die,
    find_vault,
    info,
    note_path,
    raw_paper_path,
    refuse_if_exists,
    slugify,
    stub_filename,
    today,
    validate_metadata_json,
    warn,
    write_frontmatter,
)


def _materialize_pdf(arg: str | None, url: str | None, tmpdir: Path) -> Path:
    if arg:
        p = Path(arg).expanduser().resolve()
        if not p.is_file():
            die(2, f"--pdf-path is not a file: {p}")
        return p
    if url:
        import httpx  # type: ignore[import-not-found]

        info(f"downloading PDF: {url}")
        target = tmpdir / "input.pdf"
        try:
            with httpx.Client(follow_redirects=True, timeout=120.0,
                              headers={"User-Agent": "knowledge-smith/0.2"}) as c:
                with c.stream("GET", url) as r:
                    r.raise_for_status()
                    with target.open("wb") as fh:
                        for chunk in r.iter_bytes():
                            fh.write(chunk)
        except httpx.HTTPError as exc:
            die(5, f"PDF download failed: {exc}")
        return target
    die(2, "must pass either --pdf-path or --pdf-url")


def _docling_convert(pdf: Path) -> str:
    """Shell out to the docling helper (its own PEP 723 deps).

    Keeps the main script's dep tree small so non-docling invocations
    don't pay the docling install cost.
    """
    import subprocess

    helper = Path(__file__).resolve().parent / "helpers" / "docling_extract.py"
    if not helper.is_file():
        die(11, f"docling helper missing: {helper}")
    info("running docling (first run pulls layout/OCR models — slow)…")
    try:
        result = subprocess.run(
            [str(helper), str(pdf)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        die(5, f"docling failed (exit {exc.returncode}):\n{exc.stderr}")
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--pdf-path", help="local PDF path (mutually exclusive with --pdf-url)")
    p.add_argument("--pdf-url", help="PDF URL to download (mutually exclusive with --pdf-path)")
    p.add_argument("--body-md-path",
                   help="path to a markdown file with the body text (tier 2: agent ran "
                        "pdftotext or similar). Mutually exclusive with --docling.")
    p.add_argument("--docling", action="store_true",
                   help="tier 3: run docling on the PDF for high-fidelity body markdown")
    p.add_argument("--force", action="store_true", help="overwrite existing note")
    args = p.parse_args(argv)

    if args.body_md_path and args.docling:
        die(2, "--body-md-path and --docling are mutually exclusive")

    meta = validate_metadata_json(args.metadata_json, "paper")
    vault = find_vault().path
    info(f"vault: {vault}")

    with tempfile.TemporaryDirectory() as tdir:
        tmpdir = Path(tdir)
        pdf_src = _materialize_pdf(args.pdf_path, args.pdf_url, tmpdir)

        slug = slugify(meta["title"])
        year = meta["year"]
        note_basename = stub_filename(year, slug)
        stem = note_basename.removesuffix(".md")
        raw_pdf_target = raw_paper_path(vault, "pdf", f"{stem}.pdf")
        raw_md_target = raw_paper_path(vault, "md", f"{stem}.md")
        note_target = note_path(vault, "paper", note_basename)
        refuse_if_exists(note_target, args.force)

        # Body extraction tier.
        if args.docling:
            parser_label = "docling"
            body_md = _docling_convert(pdf_src)
        elif args.body_md_path:
            parser_label = "pdftotext"
            body_md = Path(args.body_md_path).expanduser().read_text(encoding="utf-8")
        else:
            parser_label = "read"
            body_md = ""

        # Copy PDF into the vault.
        if raw_pdf_target.exists() and not args.force:
            warn(f"raw_pdf already present, leaving as-is: {raw_pdf_target.relative_to(vault)}")
        else:
            raw_pdf_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf_src, raw_pdf_target)
        info(f"wrote: {raw_pdf_target.relative_to(vault)}")

    raw_md_meta = {
        "source": "paper",
        "arxiv": meta.get("arxiv"),
        "url": meta.get("url") or args.pdf_url,
        "title": meta["title"],
        "authors": meta["authors"],
        "year": year,
        "retrieved": today(),
        "parser": parser_label,
    }
    placeholder = (
        f"<!-- body extraction tier=read; metadata-only — see {stem}.pdf -->\n"
    )
    write_frontmatter(raw_md_target, raw_md_meta, body_md or placeholder)
    info(f"wrote: {raw_md_target.relative_to(vault)}")

    note_meta = {
        "type": "note",
        "kind": "paper",
        "slug": slug,
        "title": meta["title"],
        "created": today(),
        "updated": today(),
        "read": False,
        "tags": [],
        "year": year,
        "authors": meta["authors"],
        "arxiv": meta.get("arxiv"),
        "doi": meta.get("doi"),
        "url": meta.get("url") or args.pdf_url,
        "venue": meta.get("venue"),
        "raw_pdf": raw_pdf_target.relative_to(vault).as_posix(),
        "raw_md": raw_md_target.relative_to(vault).as_posix(),
        "parser": parser_label,
    }
    abstract_block = meta.get("abstract") or "(abstract not provided)"
    authors_str = ", ".join(meta["authors"][:3]) or "unknown"
    authors_suffix = "…" if len(meta["authors"]) > 3 else ""
    body = (
        f"# {meta['title']}\n\n"
        f"> *{authors_str}{authors_suffix}* — {year}\n\n"
        "## TL;DR\n\n(stub — fill in after reading)\n\n"
        f"## Abstract\n\n{abstract_block}\n\n"
        "## Notes\n\n(your synthesis)\n\n"
        "## Source\n\n"
        f"- Raw markdown: [[raw/papers/md/{stem}]]\n"
        f"- PDF: [[raw/papers/pdf/{stem}.pdf]]\n"
    )
    if meta.get("url"):
        body += f"- Original URL: <{meta['url']}>\n"
    write_frontmatter(note_target, note_meta, body)
    info(f"wrote: {note_target.relative_to(vault)}")

    print(f"note={note_target}")
    print(f"raw_md={raw_md_target}")
    print(f"raw_pdf={raw_pdf_target}")
    print(f"parser={parser_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
