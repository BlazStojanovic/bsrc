#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "docling>=2",
#   "httpx>=0.27",
#   "python-frontmatter>=1.1",
# ]
# ///
"""Ingest a non-arXiv PDF (local path or URL) via docling.

The first invocation pulls ~hundreds of MB of layout / OCR models. This is
expected. Subsequent runs are cached.

Title and year cannot be reliably extracted from arbitrary PDFs, so the user
provides them via --title / --year. For arXiv papers, prefer
`ingest_arxiv.py`.
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
    inbox_path,
    raw_path,
    refuse_if_exists,
    sha1_short,
    slugify,
    stub_filename,
    today,
    warn,
    write_frontmatter,
)


def _materialize_pdf(arg: str, tmpdir: Path) -> Path:
    """Return a local Path to the PDF, downloading if arg is a URL."""
    if arg.startswith(("http://", "https://")):
        import httpx  # type: ignore[import-not-found]

        info(f"downloading PDF: {arg}")
        target = tmpdir / "input.pdf"
        try:
            with httpx.Client(follow_redirects=True, timeout=120.0) as client:
                with client.stream("GET", arg) as resp:
                    resp.raise_for_status()
                    with target.open("wb") as fh:
                        for chunk in resp.iter_bytes():
                            fh.write(chunk)
        except httpx.HTTPError as exc:
            die(5, f"PDF download failed: {exc}")
        return target
    p = Path(arg).expanduser().resolve()
    if not p.is_file():
        die(2, f"not a file: {p}")
    return p


def _hash_file(path: Path) -> str:
    return sha1_short(path.read_bytes())


def _docling_convert(pdf: Path) -> tuple[str, str | None]:
    """Return (markdown_body, extracted_title_or_None)."""
    info("running docling (first run downloads models, can be slow)…")
    from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]

    converter = DocumentConverter()
    result = converter.convert(str(pdf))
    doc = result.document
    md = doc.export_to_markdown()
    extracted_title = None
    name = getattr(doc, "name", None)
    if isinstance(name, str) and name.strip() and name.strip().lower() != pdf.stem.lower():
        extracted_title = name.strip()
    return md, extracted_title


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", help="local PDF path or PDF URL")
    p.add_argument("--title", help="paper title (required if docling can't extract)")
    p.add_argument("--authors", default="",
                   help="comma-separated authors (e.g. 'Vaswani A.,Shazeer N.')")
    p.add_argument("--year", type=int, help="publication year (required for filename prefix)")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    args = p.parse_args(argv)

    vault = find_vault().path
    info(f"vault: {vault}")

    with tempfile.TemporaryDirectory() as tdir:
        tmpdir = Path(tdir)
        pdf_src = _materialize_pdf(args.input, tmpdir)
        sha = _hash_file(pdf_src)
        info(f"id (sha1): {sha}")

        body_md, extracted_title = _docling_convert(pdf_src)
        title = args.title or extracted_title
        if not title:
            die(2, "could not extract title; pass --title TITLE")
        year = args.year
        if year is None:
            warn("no --year given; defaulting to current year for filename prefix")
            year = int(today().split("-")[0])
        slug = slugify(title)
        info(f"title: {title}")
        info(f"slug:  {slug}")

        raw_pdf_target = raw_path(vault, "paper", f"{sha}.pdf")
        raw_md_target = raw_path(vault, "paper", f"{sha}.md")
        inbox_target = inbox_path(vault, stub_filename(year, slug))

        refuse_if_exists(inbox_target, args.force)
        if raw_pdf_target.exists() and not args.force:
            warn(f"raw_pdf already present, skipping copy: {raw_pdf_target}")
        else:
            raw_pdf_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf_src, raw_pdf_target)
        info(f"wrote: {raw_pdf_target.relative_to(vault)}")

    authors = [a.strip() for a in args.authors.split(",") if a.strip()] if args.authors else []

    raw_md_meta = {
        "source": "paper",
        "arxiv": None,
        "url": args.input if args.input.startswith(("http://", "https://")) else None,
        "title": title,
        "authors": authors,
        "year": year,
        "retrieved": today(),
        "parser": "docling",
    }
    write_frontmatter(raw_md_target, raw_md_meta, body_md)
    info(f"wrote: {raw_md_target.relative_to(vault)}")

    stub_meta = {
        "type": "source",
        "source_kind": "paper",
        "status": "captured",
        "slug": slug,
        "title": title,
        "created": today(),
        "updated": today(),
        "tags": [],
        "id": sha,
        "indexed_in": [],
        "arxiv": None,
        "doi": None,
        "url": args.input if args.input.startswith(("http://", "https://")) else None,
        "authors": authors,
        "year": year,
        "venue": None,
        "raw_pdf": raw_pdf_target.relative_to(vault).as_posix(),
        "raw_md": raw_md_target.relative_to(vault).as_posix(),
        "parser": "docling",
    }
    body = (
        f"# {title}\n\n"
        f"> {', '.join(authors) if authors else 'unknown authors'} — {year}\n\n"
        "## TL;DR\n\n"
        "(stub)\n\n"
        "## Notes\n\n"
        "(stub)\n\n"
        "## Source\n\n"
        f"- Raw markdown: [[raw/papers/{sha}]]\n"
        f"- PDF (gitignored): `raw/papers/{sha}.pdf`\n"
    )
    write_frontmatter(inbox_target, stub_meta, body)
    info(f"wrote: {inbox_target.relative_to(vault)}")

    print(f"inbox={inbox_target}")
    print(f"raw_md={raw_md_target}")
    print(f"raw_pdf={raw_pdf_target}")
    print(f"id={sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
