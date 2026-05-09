#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27",
#   "markdownify>=0.13",
#   "python-frontmatter>=1.1",
# ]
# ///
"""Write an arxiv paper note + raw assets into the active vault.

The agent fetches metadata via `WebFetch("https://arxiv.org/abs/<id>", ...)`
and passes it in via --metadata-json. This script:

  1. Validates the JSON.
  2. Streams `https://arxiv.org/pdf/<id>.pdf` to raw/papers/<id>.pdf
     (skip with --no-pdf).
  3. Fetches `https://ar5iv.labs.arxiv.org/html/<id>` and converts to
     markdown for raw/papers/<id>.md (skip with --no-ar5iv).
  4. Writes the summary note to notes/papers/<year>-<slug>.md.

The arxiv API is never called. Both arxiv.org/pdf/ and ar5iv.labs are
separate hosts from export.arxiv.org/api/query, so there's no shared 429
quota with anything else.

Required JSON keys: title, authors (list), year (int).
Optional: arxiv (id), abstract, url, doi, venue.

Example:
  uv run ingest_arxiv.py --metadata-json '{
    "arxiv": "1706.03762",
    "title": "Attention Is All You Need",
    "authors": ["Ashish Vaswani", "Noam Shazeer"],
    "year": 2017,
    "abstract": "...",
    "url": "https://arxiv.org/abs/1706.03762"
  }'
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
    raw_paper_path,
    refuse_if_exists,
    slugify,
    stub_filename,
    today,
    validate_metadata_json,
    warn,
    write_frontmatter,
)

AR5IV_URL = "https://ar5iv.labs.arxiv.org/html/{id}"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{id}.pdf"


def fetch_ar5iv(arxiv_id: str) -> str | None:
    import httpx  # type: ignore[import-not-found]
    from markdownify import markdownify  # type: ignore[import-not-found]

    try:
        with httpx.Client(follow_redirects=True, timeout=60.0,
                          headers={"User-Agent": "knowledge-smith/0.2"}) as c:
            r = c.get(AR5IV_URL.format(id=arxiv_id))
    except httpx.HTTPError as exc:
        warn(f"ar5iv fetch failed: {exc}")
        return None
    if r.status_code != 200:
        warn(f"ar5iv returned {r.status_code} for {arxiv_id}")
        return None
    return markdownify(r.text, heading_style="ATX", strip=["script", "style"])


def download_pdf(arxiv_id: str, dest: Path) -> bool:
    import httpx  # type: ignore[import-not-found]

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with httpx.Client(follow_redirects=True, timeout=120.0,
                          headers={"User-Agent": "knowledge-smith/0.2"}) as c:
            with c.stream("GET", ARXIV_PDF_URL.format(id=arxiv_id)) as r:
                r.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in r.iter_bytes():
                        fh.write(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        warn(f"PDF download failed: {exc}")
        return False
    tmp.replace(dest)
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--force", action="store_true", help="overwrite existing note")
    p.add_argument("--no-pdf", action="store_true", help="skip PDF download")
    p.add_argument("--no-ar5iv", action="store_true",
                   help="skip ar5iv markdown extraction")
    args = p.parse_args(argv)

    meta = validate_metadata_json(args.metadata_json, "paper")
    arxiv_id = meta.get("arxiv")
    if not arxiv_id:
        die(2, "paper metadata is missing 'arxiv' id (required by ingest_arxiv.py; "
               "use ingest_pdf.py for non-arxiv papers)")

    vault = find_vault().path
    info(f"vault: {vault}")
    info(f"arxiv: {arxiv_id}")

    slug = slugify(meta["title"])
    year = meta["year"]
    note_basename = stub_filename(year, slug)
    note_target = note_path(vault, "paper", note_basename)
    refuse_if_exists(note_target, args.force)

    raw_md_target = raw_paper_path(vault, "md", note_basename)
    raw_pdf_target = raw_paper_path(vault, "pdf", note_basename.replace(".md", ".pdf"))

    parser_label = "ar5iv"
    body_md = ""
    if args.no_ar5iv:
        parser_label = "ar5iv-skipped"
        info("ar5iv: skipped (--no-ar5iv)")
    else:
        ar5iv_md = fetch_ar5iv(arxiv_id)
        if ar5iv_md is None:
            parser_label = "ar5iv-failed"
        else:
            body_md = ar5iv_md
            info(f"ar5iv: {len(body_md)} chars")

    raw_md_meta = {
        "source": "paper",
        "arxiv": arxiv_id,
        "url": meta.get("url") or f"https://arxiv.org/abs/{arxiv_id}",
        "title": meta["title"],
        "authors": meta["authors"],
        "year": year,
        "retrieved": today(),
        "parser": parser_label,
    }
    placeholder = f"<!-- ar5iv unavailable for {arxiv_id}; see {arxiv_id}.pdf -->\n"
    write_frontmatter(raw_md_target, raw_md_meta, body_md or placeholder)
    info(f"wrote: {raw_md_target.relative_to(vault)}")

    pdf_written = False
    if args.no_pdf:
        info("pdf: skipped (--no-pdf)")
    else:
        pdf_written = download_pdf(arxiv_id, raw_pdf_target)
        if pdf_written:
            info(f"wrote: {raw_pdf_target.relative_to(vault)}")

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
        "arxiv": arxiv_id,
        "doi": meta.get("doi"),
        "url": meta.get("url") or f"https://arxiv.org/abs/{arxiv_id}",
        "venue": meta.get("venue"),
        "raw_pdf": raw_pdf_target.relative_to(vault).as_posix() if pdf_written else None,
        "raw_md": raw_md_target.relative_to(vault).as_posix(),
        "parser": parser_label,
    }
    abstract_block = meta.get("abstract") or "(abstract not provided)"
    authors_short = ", ".join(meta["authors"][:3])
    authors_suffix = "…" if len(meta["authors"]) > 3 else ""
    stem = note_basename.removesuffix(".md")
    pdf_link = f"[[raw/papers/pdf/{stem}.pdf]]"
    if args.no_pdf:
        pdf_line = f"- PDF (skipped): {pdf_link}"
    elif pdf_written:
        pdf_line = f"- PDF: {pdf_link}"
    else:
        pdf_line = f"- PDF (download failed): {pdf_link}"
    body = (
        f"# {meta['title']}\n\n"
        f"> *{authors_short}{authors_suffix}* — arXiv {arxiv_id}, {year}\n\n"
        "## TL;DR\n\n(stub — fill in after reading)\n\n"
        f"## Abstract\n\n{abstract_block}\n\n"
        "## Notes\n\n(your synthesis)\n\n"
        "## Source\n\n"
        f"- Raw markdown: [[raw/papers/md/{stem}]]\n"
        f"{pdf_line}\n"
        f"- arXiv: <https://arxiv.org/abs/{arxiv_id}>\n"
    )
    write_frontmatter(note_target, note_meta, body)
    info(f"wrote: {note_target.relative_to(vault)}")

    print(f"note={note_target}")
    print(f"raw_md={raw_md_target}")
    if pdf_written:
        print(f"raw_pdf={raw_pdf_target}")
    print(f"parser={parser_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
