#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27",
#   "python-frontmatter>=1.1",
# ]
# ///
"""Ingest a URL as a lightweight bookmark.

Auto-detects:
  - github.com/<owner>/<repo>  -> notes/github/<owner>-<repo>.md
  - everything else            -> notes/blogs/<slug>.md

GitHub bookmarks are intentionally minimal: url + description only. No API
metadata fetching, no recovery — the note + URL is the artifact.

Blog bookmarks try a best-effort <title> extraction from the page; otherwise
fall back to host name. --description supplies the user's one-sentence hook.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    die,
    find_vault,
    info,
    note_path,
    refuse_if_exists,
    sha1_short,
    slugify,
    stub_filename,
    today,
    warn,
    write_frontmatter,
)


GITHUB_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/?#]+)/?", re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def detect_kind(url: str) -> tuple[str, dict]:
    m = GITHUB_RE.match(url)
    if m:
        owner, repo = m.group(1), m.group(2).rstrip(".git")
        return "github", {"owner": owner, "repo": repo}
    return "blog", {}


def fetch_page_title(url: str) -> str | None:
    import httpx  # type: ignore[import-not-found]

    try:
        with httpx.Client(follow_redirects=True, timeout=20.0,
                          headers={"User-Agent": "knowledge-smith/0.1"}) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                warn(f"page fetch returned {resp.status_code}")
                return None
            text = resp.text
    except httpx.HTTPError as exc:
        warn(f"page fetch failed: {exc}")
        return None

    m = TITLE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Decode common HTML entities cheaply.
    raw = raw.replace("&amp;", "&").replace("&#39;", "'")
    raw = raw.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", raw)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("url", help="bookmark URL")
    p.add_argument("--description", default="", help="one-sentence hook")
    p.add_argument("--force", action="store_true", help="overwrite existing note")
    p.add_argument("--no-title-fetch", action="store_true",
                   help="skip best-effort page <title> fetch (blogs only)")
    args = p.parse_args(argv)

    parsed = urlparse(args.url)
    if not (parsed.scheme and parsed.netloc):
        die(2, f"not a usable URL: {args.url!r}")

    vault = find_vault().path
    info(f"vault: {vault}")

    kind, extras = detect_kind(args.url)
    info(f"kind:  {kind}")

    if kind == "github":
        owner = extras["owner"]
        repo = extras["repo"]
        slug = slugify(repo)
        bookmark_id = f"{slugify(owner)}-{slug}"
        title = f"{owner}/{repo}"
        stub = stub_filename(None, bookmark_id)
        body = (
            f"# {title}\n\n"
            f"{args.description or '(no description)'}\n\n"
            "## Notes\n\n"
            "(stub)\n"
        )
        meta = {
            "type": "note",
            "kind": "github",
            "slug": slug,
            "title": title,
            "created": today(),
            "updated": today(),
            "read": False,
            "tags": [],
            "url": args.url,
            "description": args.description or None,
        }
    else:
        title = None
        if not args.no_title_fetch:
            title = fetch_page_title(args.url)
        if not title:
            title = parsed.netloc
        slug = slugify(title)
        bookmark_id = sha1_short(args.url)
        stub = stub_filename(None, slug)
        body = (
            f"# {title}\n\n"
            f"{args.description or '(no description)'}\n\n"
            "## Notes\n\n"
            "(stub)\n"
        )
        meta = {
            "type": "note",
            "kind": "blog",
            "slug": slug,
            "title": title,
            "created": today(),
            "updated": today(),
            "read": False,
            "tags": [],
            "url": args.url,
            "author": None,
            "description": args.description or None,
        }

    target = note_path(vault, kind, stub)
    refuse_if_exists(target, args.force)
    write_frontmatter(target, meta, body)
    info(f"wrote: {target.relative_to(vault)}")

    print(f"note={target}")
    print(f"kind={kind}")
    # bookmark_id retained as identifier in the basename; not in frontmatter.
    _ = bookmark_id
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
