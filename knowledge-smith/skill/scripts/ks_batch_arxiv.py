#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Batch-ingest arXiv papers into the knowledge-smith vault.

When you have a list of arXiv IDs to capture as stubs (e.g. an inbox
dump), this is the one-call path. It hits the arXiv export API
directly (stdlib `urllib` — no WebFetch), composes a minimal paper-note
body, and shells out to `ingest_arxiv.py` for each ID.

Why this exists: the documented pipeline expects the LLM agent to drive
each ingest one-by-one (WebFetch → compose → call script). That's the
right shape for hand-curated work. For 100+ stubs the agent loop is
slow and may hit harness permission walls on subagents — this script
collapses the per-paper work into a single process you control.

Usage:
    # one-off:
    uv run ks_batch_arxiv.py 1706.03762 2107.03374

    # from a file (one id per line, '#' comments allowed):
    uv run ks_batch_arxiv.py --ids-file inbox-arxiv.txt

    # tune the per-request delay (arxiv rate-limits ~3s for bursts):
    uv run ks_batch_arxiv.py --ids-file ids.txt --delay 3.0

Each entry produces a stub paper note: title + author line + verbatim
abstract + `(stub)` placeholders for TL;DR and Notes. Run the read-pass
later to flesh out body sections.

Failures (rate-limit, malformed ID, network) are reported in the
summary; rerun with just the failed IDs to retry.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ATOM_NS = "{http://www.w3.org/2005/Atom}"

SCRIPT_DIR = Path(__file__).resolve().parent
INGEST_SCRIPT = SCRIPT_DIR / "ingest_arxiv.py"


def fetch_metadata(arxiv_id: str, retries: int = 3) -> dict | None:
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id)}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "knowledge-smith/batch (+https://github.com)"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                xml = r.read().decode("utf-8")
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(3 * (attempt + 1))
    else:
        print(f"  FAIL fetch {arxiv_id}: {last_err}", file=sys.stderr)
        return None

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        print(f"  FAIL parse {arxiv_id}: {e}", file=sys.stderr)
        return None

    entry = root.find(f"{ATOM_NS}entry")
    if entry is None:
        print(f"  FAIL no-entry {arxiv_id}", file=sys.stderr)
        return None

    title_el = entry.find(f"{ATOM_NS}title")
    summary_el = entry.find(f"{ATOM_NS}summary")
    published_el = entry.find(f"{ATOM_NS}published")
    if title_el is None or summary_el is None or published_el is None:
        print(f"  FAIL missing-fields {arxiv_id}", file=sys.stderr)
        return None

    title = re.sub(r"\s+", " ", (title_el.text or "").strip())
    if not title or title.lower() == "error":
        print(f"  FAIL empty-title {arxiv_id}", file=sys.stderr)
        return None
    abstract = (summary_el.text or "").strip()
    published = (published_el.text or "").strip()
    year = int(published[:4]) if len(published) >= 4 else None
    if year is None:
        print(f"  FAIL no-year {arxiv_id}", file=sys.stderr)
        return None

    authors: list[str] = []
    for a in entry.findall(f"{ATOM_NS}author"):
        name_el = a.find(f"{ATOM_NS}name")
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    return {
        "arxiv": arxiv_id,
        "title": title,
        "abstract": abstract,
        "year": year,
        "authors": authors,
    }


_SLUG_STRIP_ARTICLES = {"a", "an", "the"}


def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    parts = s.split("-")
    while parts and parts[0] in _SLUG_STRIP_ARTICLES:
        parts.pop(0)
    s = "-".join(parts)
    if len(s) > 80:
        s = s[:80].rsplit("-", 1)[0]
    return s


def format_authors(authors: list[str]) -> str:
    if not authors:
        return "Unknown"
    if len(authors) > 5:
        return ", ".join(authors[:5]) + ", et al."
    return ", ".join(authors)


def compose_body(meta: dict, slug: str, year: int) -> str:
    arxiv_id = meta["arxiv"]
    stem = f"{year}-{slug}"
    return (
        f"# {meta['title']}\n\n"
        f"> *{format_authors(meta['authors'])}* — arXiv {year}\n\n"
        "## TL;DR\n\n"
        "(stub — fill in after reading)\n\n"
        "## Abstract\n\n"
        f"{meta['abstract']}\n\n"
        "## Notes\n\n"
        "(stub)\n\n"
        "## Source\n\n"
        f"- arXiv: <https://arxiv.org/abs/{arxiv_id}>\n"
        f"- PDF: [[raw/papers/pdf/{stem}.pdf]]\n"
        f"- Raw markdown: [[raw/papers/md/{stem}]]\n"
    )


def ingest_one(meta: dict, cwd: Path | None) -> tuple[bool, str]:
    arxiv_id = meta["arxiv"]
    slug = slugify(meta["title"])
    if not slug:
        return False, f"empty-slug for {arxiv_id}"
    year = meta["year"]
    stem = f"{year}-{slug}"

    body_path = Path(f"/tmp/ks-body-{arxiv_id}.md")
    body_path.write_text(compose_body(meta, slug, year), encoding="utf-8")

    metadata = {
        "arxiv": arxiv_id,
        "title": meta["title"],
        "slug": slug,
        "year": year,
        "authors": meta["authors"],
    }
    links = {
        "source": f"https://arxiv.org/abs/{arxiv_id}",
        "paper": f"https://arxiv.org/abs/{arxiv_id}",
    }

    cmd = [
        "uv", "run", str(INGEST_SCRIPT),
        "--metadata-json", json.dumps(metadata, ensure_ascii=False),
        "--links-json", json.dumps(links, ensure_ascii=False),
        "--body-md-path", str(body_path),
    ]
    try:
        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, timeout=120,
            cwd=str(cwd) if cwd else None,
        )
    except subprocess.TimeoutExpired:
        body_path.unlink(missing_ok=True)
        return False, f"timeout for {arxiv_id}"

    body_path.unlink(missing_ok=True)

    if result.returncode != 0:
        stderr = (result.stderr or "").strip().splitlines()
        tail = " | ".join(stderr[-3:]) if stderr else "(no stderr)"
        return False, f"{arxiv_id} exit={result.returncode}: {tail}"
    return True, stem


_ID_RE = re.compile(r"(\d{4}\.\d{4,5})|([a-z\-]+/\d{7})")


def normalize_ids(raw_ids: list[str]) -> list[str]:
    norm: list[str] = []
    seen: set[str] = set()
    for raw in raw_ids:
        m = _ID_RE.search(raw)
        if not m:
            continue
        nid = m.group(1) or m.group(2)
        if nid in seen:
            continue
        seen.add(nid)
        norm.append(nid)
    return norm


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("ids", nargs="*",
                   help="arxiv ids (or arxiv URLs); or read from --ids-file")
    p.add_argument("--ids-file", help="file with one arxiv id (or URL) per line; "
                                       "'#' lines are comments")
    p.add_argument("--delay", type=float, default=2.0,
                   help="seconds between API calls (default 2.0; arxiv "
                        "rate-limits aggressive bursts)")
    p.add_argument("--cwd", help="working directory for the ingest subprocess "
                                  "(defaults to current dir; use to target a "
                                  "specific vault when the marker isn't in cwd)")
    args = p.parse_args(argv)

    raw_ids: list[str] = list(args.ids)
    if args.ids_file:
        raw_ids.extend(
            line.strip()
            for line in Path(args.ids_file).read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    ids = normalize_ids(raw_ids)
    if not ids:
        print("no arxiv ids provided", file=sys.stderr)
        return 2

    cwd = Path(args.cwd) if args.cwd else None
    ok: list[str] = []
    fail: list[str] = []
    for i, aid in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] {aid}", flush=True)
        meta = fetch_metadata(aid)
        if not meta:
            fail.append(f"{aid} fetch-failed")
            time.sleep(args.delay)
            continue
        success, msg = ingest_one(meta, cwd)
        if success:
            ok.append(msg)
            print(f"  OK  {msg}", flush=True)
        else:
            fail.append(msg)
            print(f"  FAIL {msg}", flush=True)
        time.sleep(args.delay)

    print()
    print(f"# Summary: {len(ok)} succeeded, {len(fail)} failed")
    print("# OK:")
    for s in ok:
        print(f"  {s}")
    print("# FAIL:")
    for s in fail:
        print(f"  {s}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
