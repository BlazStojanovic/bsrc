#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "arxiv>=2.1",
#   "httpx>=0.27",
#   "markdownify>=0.13",
#   "python-frontmatter>=1.1",
# ]
# ///
"""Ingest an arXiv paper into the active knowledge-smith vault.

Pipeline:
  1. arXiv API metadata (title, authors, abstract, year, pdf_url).
  2. ar5iv HTML -> markdown for full text. On 404, mark parser as
     'ar5iv-failed' and continue (PDF still downloads).
  3. Stream PDF to raw/papers/<id>.pdf (skipped via --no-pdf).
  4. Write raw/papers/<id>.md (committed: parsed text body).
  5. Write notes/papers/<year>-<slug>.md (the summary note with read=false).

Exit codes:
  0  ok
  2  bad arxiv id
  3  arxiv id not found
  4  note already exists (use --force)
  5  network error
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    die,
    find_vault,
    info,
    note_path,
    raw_path,
    refuse_if_exists,
    slugify,
    stub_filename,
    today,
    warn,
    write_frontmatter,
)

ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,6})(?:v\d+)?")
AR5IV_URL = "https://ar5iv.labs.arxiv.org/html/{id}"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{id}.pdf"


def parse_arxiv_id(s: str) -> str:
    m = ARXIV_ID_RE.search(s)
    if not m:
        die(2, f"not a recognizable arxiv id: {s!r}")
    return m.group(1)


def fetch_metadata(arxiv_id: str) -> dict:
    import arxiv  # type: ignore[import-not-found]

    try:
        client = arxiv.Client(page_size=1, delay_seconds=0, num_retries=2)
        results = list(client.results(arxiv.Search(id_list=[arxiv_id])))
    except Exception as exc:
        die(5, f"arxiv API error: {exc}")
    if not results:
        die(3, f"arxiv id not found: {arxiv_id}")
    r = results[0]
    return {
        "title": r.title.strip(),
        "authors": [a.name for a in r.authors],
        "summary": r.summary.strip(),
        "primary_category": r.primary_category,
        "published": r.published.date().isoformat() if r.published else None,
        "year": r.published.year if r.published else None,
        "pdf_url": r.pdf_url,
        "entry_id": r.entry_id,
    }


def fetch_ar5iv_markdown(arxiv_id: str) -> str | None:
    import httpx  # type: ignore[import-not-found]
    from markdownify import markdownify  # type: ignore[import-not-found]

    url = AR5IV_URL.format(id=arxiv_id)
    try:
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            resp = client.get(url)
    except httpx.HTTPError as exc:
        warn(f"ar5iv fetch failed: {exc}")
        return None
    if resp.status_code == 404:
        warn(f"ar5iv has no rendering for {arxiv_id}")
        return None
    if resp.status_code != 200:
        warn(f"ar5iv returned {resp.status_code} for {arxiv_id}")
        return None
    return markdownify(resp.text, heading_style="ATX", strip=["script", "style"])


def download_pdf(arxiv_id: str, dest: Path) -> bool:
    import httpx  # type: ignore[import-not-found]

    url = ARXIV_PDF_URL.format(id=arxiv_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with httpx.Client(follow_redirects=True, timeout=120.0) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        warn(f"PDF download failed: {exc}")
        return False
    tmp.replace(dest)
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", help="arxiv id or arxiv URL")
    p.add_argument("--force", action="store_true", help="overwrite existing inbox stub")
    p.add_argument("--no-pdf", action="store_true", help="skip PDF download")
    p.add_argument("--no-ar5iv", action="store_true", help="skip ar5iv markdown extraction")
    args = p.parse_args(argv)

    vault = find_vault().path
    arxiv_id = parse_arxiv_id(args.input)

    info(f"vault: {vault}")
    info(f"arxiv: {arxiv_id}")

    meta = fetch_metadata(arxiv_id)
    slug = slugify(meta["title"])
    year = meta["year"]
    stub = stub_filename(year, slug)

    note_target = note_path(vault, "paper", stub)
    refuse_if_exists(note_target, args.force)

    raw_md_target = raw_path(vault, "paper", f"{arxiv_id}.md")
    raw_pdf_target = raw_path(vault, "paper", f"{arxiv_id}.pdf")

    # 1. ar5iv markdown
    parser_label = "ar5iv"
    body_md = ""
    if args.no_ar5iv:
        parser_label = "ar5iv-skipped"
        info("ar5iv: skipped (--no-ar5iv)")
    else:
        ar5iv_md = fetch_ar5iv_markdown(arxiv_id)
        if ar5iv_md is None:
            parser_label = "ar5iv-failed"
        else:
            body_md = ar5iv_md
            info(f"ar5iv: {len(body_md)} chars")

    raw_md_target.parent.mkdir(parents=True, exist_ok=True)
    raw_md_meta = {
        "source": "paper",
        "arxiv": arxiv_id,
        "url": meta["entry_id"],
        "title": meta["title"],
        "authors": meta["authors"],
        "year": year,
        "retrieved": today(),
        "parser": parser_label,
    }
    placeholder = (
        f"<!-- ar5iv unavailable for {arxiv_id}; see raw/papers/{arxiv_id}.pdf -->\n"
    )
    write_frontmatter(raw_md_target, raw_md_meta, body_md or placeholder)
    info(f"wrote: {raw_md_target.relative_to(vault)}")

    # 2. PDF
    pdf_written = False
    if args.no_pdf:
        info("pdf: skipped (--no-pdf)")
    else:
        pdf_written = download_pdf(arxiv_id, raw_pdf_target)
        if pdf_written:
            info(f"wrote: {raw_pdf_target.relative_to(vault)}")

    # 3. Note in notes/papers/
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
        "doi": None,
        "url": meta["entry_id"],
        "venue": None,
        "raw_pdf": raw_pdf_target.relative_to(vault).as_posix(),
        "raw_md": raw_md_target.relative_to(vault).as_posix(),
        "parser": parser_label,
    }
    body = (
        f"# {meta['title']}\n\n"
        f"> *{', '.join(meta['authors'][:3])}{'…' if len(meta['authors']) > 3 else ''}*"
        f" — arXiv {arxiv_id}, {year}\n\n"
        "## TL;DR\n\n"
        "(stub — fill in after reading)\n\n"
        "## Abstract\n\n"
        f"{meta['summary']}\n\n"
        "## Notes\n\n"
        "(your synthesis)\n\n"
        "## Source\n\n"
        f"- Raw markdown: [[raw/papers/{arxiv_id}]]\n"
        f"- PDF (gitignored): `raw/papers/{arxiv_id}.pdf`\n"
        f"- arXiv: <{meta['entry_id']}>\n"
    )
    write_frontmatter(note_target, note_meta, body)
    info(f"wrote: {note_target.relative_to(vault)}")

    # Machine-friendly tail.
    print(f"note={note_target}")
    print(f"raw_md={raw_md_target}")
    if pdf_written:
        print(f"raw_pdf={raw_pdf_target}")
    print(f"parser={parser_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
