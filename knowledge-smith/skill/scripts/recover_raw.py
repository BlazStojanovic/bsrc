#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27",
#   "python-frontmatter>=1.1",
# ]
# ///
"""Refetch gitignored binaries (paper PDFs) from source frontmatter.

Walks `inbox/` and `sources/` in the active vault. For each source whose raw
binary is missing on disk, refetches it using the stable identifier in the
frontmatter:

  - paper: `arxiv` field -> https://arxiv.org/pdf/<id>.pdf
  - article: best-effort URL refetch (often broken; warned)
  - youtube: audio is slice-2; metadata + transcript are committed already

Blog and github are never recovered — the note + URL is the artifact.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    find_vault,
    info,
    read_frontmatter,
    warn,
)


SOURCE_KINDS = ("paper", "article", "youtube")


def _stream_to_file(url: str, dest: Path) -> bool:
    import httpx  # type: ignore[import-not-found]

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with httpx.Client(follow_redirects=True, timeout=120.0,
                          headers={"User-Agent": "knowledge-smith/0.1"}) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        warn(f"download failed: {url} ({exc})")
        return False
    tmp.replace(dest)
    return True


def recover_paper(meta: dict, vault: Path, dry_run: bool) -> tuple[int, int]:
    """Returns (planned, recovered)."""
    arxiv_id = meta.get("arxiv")
    raw_pdf = meta.get("raw_pdf")
    if not (arxiv_id and raw_pdf):
        return 0, 0
    target = vault / raw_pdf
    if target.exists():
        return 0, 0
    info(f"paper {arxiv_id} -> {raw_pdf}")
    if dry_run:
        return 1, 0
    ok = _stream_to_file(f"https://arxiv.org/pdf/{arxiv_id}.pdf", target)
    return 1, (1 if ok else 0)


def recover_article(meta: dict, vault: Path, dry_run: bool) -> tuple[int, int]:
    raw_md = meta.get("raw_md")
    url = meta.get("url")
    if not (raw_md and url):
        return 0, 0
    target = vault / raw_md
    if target.exists():
        return 0, 0
    warn(f"article raw_md missing: {raw_md} (URL: {url})")
    warn("article recovery is best-effort and not implemented in slice 1")
    warn("re-run Web Clipper against the original URL and ingest_article.py")
    return 1, 0


def recover_youtube(meta: dict, vault: Path, dry_run: bool) -> tuple[int, int]:
    raw_audio = meta.get("raw_audio")
    if not raw_audio:
        return 0, 0
    target = vault / raw_audio
    if target.exists():
        return 0, 0
    # Audio fetch is slice-2; in slice 1 we report and skip.
    return 0, 0


HANDLERS = {
    "paper": recover_paper,
    "article": recover_article,
    "youtube": recover_youtube,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", choices=SOURCE_KINDS,
                   help="restrict to a single source_kind")
    p.add_argument("--dry-run", action="store_true",
                   help="report planned fetches without downloading")
    args = p.parse_args(argv)

    vault = find_vault().path
    info(f"vault: {vault}")

    total_planned = 0
    total_recovered = 0
    for sub in ("inbox", "sources"):
        root = vault / sub
        if not root.is_dir():
            continue
        for md in root.rglob("*.md"):
            try:
                meta, _ = read_frontmatter(md)
            except Exception as exc:
                warn(f"skipping unparseable {md}: {exc}")
                continue
            if meta.get("type") != "source":
                continue
            kind = meta.get("source_kind")
            if not isinstance(kind, str):
                continue
            if args.kind and kind != args.kind:
                continue
            handler = HANDLERS.get(kind)
            if handler is None:
                continue
            planned, recovered = handler(meta, vault, args.dry_run)
            total_planned += planned
            total_recovered += recovered

    if args.dry_run:
        info(f"would recover {total_planned} item(s) (dry-run)")
    else:
        info(f"recovered {total_recovered}/{total_planned} item(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
