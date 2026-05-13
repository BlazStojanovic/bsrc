#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Batch-ingest blog/post/github/course bookmarks into the knowledge-smith vault.

Reads a TSV of `kind<TAB>url[<TAB>slug-override]` lines, fetches each
page via stdlib (no WebFetch), pulls `<title>` / OpenGraph metadata,
composes a stub bookmark body, and shells out to `ingest_bookmark.py`.

Why this exists: paired with `ks_batch_arxiv.py`, this lets you drain
an inbox of mixed URLs in one pass without driving per-URL WebFetch +
ingest in the agent loop. Useful when the inbox has 30+ bookmarks.

Limitations:
- JS-rendered sites (Notion homepages, x.com tweets, some
  framework-rendered docs) often return only the site-default
  `<title>` — the resulting note will get a generic slug. Either pass
  an explicit slug-override in the TSV third column, or fix the note
  by hand after import.
- Author / date heuristics rely on standard OpenGraph + meta tags. If
  the host doesn't emit them, the fields end up empty.

TSV format (kind must be `post`, `blog`, `github`, or `course`):
    post	https://example.com/article	optional-slug
    blog	https://example.com
    github	https://github.com/owner/repo
    course	https://stanford-cs336.github.io/spring2024/

Usage:
    uv run ks_batch_bookmarks.py --tsv inbox-bookmarks.tsv
    uv run ks_batch_bookmarks.py --tsv inbox.tsv --delay 1.5 --cwd /path/to/vault

Each entry produces a stub note: title + author/source line + OG
description (if available) + `(stub)` placeholders.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
INGEST_SCRIPT = SCRIPT_DIR / "ingest_bookmark.py"

UA = "Mozilla/5.0 (compatible; knowledge-smith/batch)"


def fetch_html(url: str, retries: int = 2) -> str | None:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.5"}
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                ct = r.headers.get("Content-Type", "")
                if "text" not in ct and "html" not in ct and "json" not in ct:
                    return None
                raw = r.read(1_000_000)  # cap at 1MB
                charset = "utf-8"
                m = re.search(r"charset=([\w\-]+)", ct)
                if m:
                    charset = m.group(1)
                return raw.decode(charset, errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    print(f"  FAIL fetch: {last}", file=sys.stderr)
    return None


def _meta(html_text: str, *names: str) -> str | None:
    for n in names:
        for attr in ("name", "property"):
            pat = rf'<meta\s+[^>]*?{attr}=["\']{re.escape(n)}["\'][^>]*?content=["\']([^"\']+)["\']'
            m = re.search(pat, html_text, re.I)
            if m:
                return html.unescape(m.group(1).strip())
            pat = rf'<meta\s+[^>]*?content=["\']([^"\']+)["\'][^>]*?{attr}=["\']{re.escape(n)}["\']'
            m = re.search(pat, html_text, re.I)
            if m:
                return html.unescape(m.group(1).strip())
    return None


def parse_metadata(url: str, html_text: str) -> dict:
    title = _meta(html_text, "og:title", "twitter:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.I | re.S)
        if m:
            title = html.unescape(re.sub(r"\s+", " ", m.group(1)).strip())
    description = _meta(html_text, "og:description", "twitter:description", "description")
    author = _meta(html_text, "article:author", "author", "og:article:author", "twitter:creator")
    site_name = _meta(html_text, "og:site_name", "application-name")
    published = _meta(
        html_text,
        "article:published_time", "og:article:published_time",
        "datePublished", "pubdate", "date",
    )
    year = None
    if published:
        m = re.search(r"(\d{4})", published)
        if m:
            year = int(m.group(1))
    if not year:
        m = re.search(r"/(\d{4})/\d{1,2}/", url)
        if m:
            year = int(m.group(1))

    parsed = urllib.parse.urlparse(url)
    if not site_name:
        site_name = parsed.netloc.replace("www.", "")

    return {
        "title": title,
        "description": description,
        "author": author,
        "source": site_name,
        "year": year,
        "host": parsed.netloc,
    }


_SLUG_STRIP_ARTICLES = {"a", "an", "the"}


def slugify(text: str, fallback: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s:
        s = fallback.lower()
        s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    parts = s.split("-")
    while parts and parts[0] in _SLUG_STRIP_ARTICLES:
        parts.pop(0)
    s = "-".join(parts)
    if len(s) > 80:
        s = s[:80].rsplit("-", 1)[0]
    return s


def compose_post_body(meta: dict, url: str) -> str:
    title = meta.get("title") or "(untitled)"
    author = meta.get("author") or "—"
    source = meta.get("source") or "—"
    year = meta.get("year") or "—"
    desc = (meta.get("description") or "").strip()
    desc_block = f"\n## TL;DR\n\n{desc}\n" if desc else "\n## TL;DR\n\n(stub — distill after reading)\n"
    return (
        f"# {title}\n\n"
        f"> *{author}* — {source}, {year}\n"
        f"{desc_block}"
        "\n## Notes\n\n(stub)\n"
        f"\n## Source\n\n- Original URL: <{url}>\n"
    )


def compose_blog_body(meta: dict, url: str) -> str:
    title = meta.get("title") or meta.get("source") or "(untitled)"
    desc = (meta.get("description") or "").strip()
    desc_block = f"\n{desc}\n" if desc else ""
    return (
        f"# {title}\n"
        f"{desc_block}"
        "\n## Why follow\n\n(stub)\n"
        "\n## Notable posts\n\n- (link individual posts as they're saved)\n"
        f"\n## Source\n\n- Homepage: <{url}>\n"
    )


def compose_github_body(meta: dict, url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    owner = parts[0] if parts else "unknown"
    repo = parts[1] if len(parts) > 1 else "unknown"
    desc = (meta.get("description") or "").strip()
    desc_block = f"\n{desc}\n" if desc else ""
    return (
        f"# {owner}/{repo}\n"
        f"{desc_block}"
        "\n## Why bookmark\n\n(stub)\n"
        "\n## Notes\n\n(stub)\n"
    )


def slug_for(url: str, kind: str, meta: dict, override: str | None) -> str:
    if override:
        return override
    if kind == "github":
        parts = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
        if len(parts) >= 2:
            return slugify(f"{parts[0]}-{parts[1]}", "github-repo")
        return slugify(parts[0] if parts else "unknown", "github-repo")
    if kind == "blog":
        title = meta.get("title") or meta.get("source") or urllib.parse.urlparse(url).netloc
        return slugify(title, urllib.parse.urlparse(url).netloc)
    title = meta.get("title")
    if not title:
        path = urllib.parse.urlparse(url).path.strip("/").replace("/", "-")
        return slugify(path, "post")
    return slugify(title, urllib.parse.urlparse(url).netloc)


def ingest_one(kind: str, url: str, slug_override: str | None,
               cwd: Path | None) -> tuple[bool, str]:
    html_text = fetch_html(url)
    if html_text is None:
        return False, f"{url} fetch-failed"
    meta = parse_metadata(url, html_text)
    if not meta.get("title") and kind != "github":
        meta["title"] = urllib.parse.urlparse(url).netloc

    slug = slug_for(url, kind, meta, slug_override)
    if not slug:
        return False, f"{url} empty-slug"

    metadata: dict = {
        "title": meta.get("title") or slug,
        "slug": slug,
    }
    if meta.get("year"):
        metadata["year"] = meta["year"]
    if meta.get("description"):
        metadata["description"] = meta["description"][:280]
    if meta.get("author"):
        metadata["author"] = meta["author"]
    if kind == "post":
        metadata["source"] = meta.get("source") or urllib.parse.urlparse(url).netloc
    if kind == "github":
        parts = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
        if len(parts) >= 2:
            metadata["owner"] = parts[0]
            metadata["repo"] = parts[1]
            metadata["title"] = f"{parts[0]}/{parts[1]}"

    if kind == "blog":
        body = compose_blog_body(meta, url)
    elif kind == "github":
        body = compose_github_body(meta, url)
    else:
        body = compose_post_body(meta, url)

    body_path = Path(f"/tmp/ks-body-{slug}.md")
    body_path.write_text(body, encoding="utf-8")

    links = {"source": url}
    if kind == "github":
        links["code"] = url

    cmd = [
        "uv", "run", str(INGEST_SCRIPT),
        "--kind", kind,
        "--metadata-json", json.dumps(metadata, ensure_ascii=False),
        "--links-json", json.dumps(links, ensure_ascii=False),
        "--body-md-path", str(body_path),
    ]
    try:
        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, timeout=60,
            cwd=str(cwd) if cwd else None,
        )
    except subprocess.TimeoutExpired:
        body_path.unlink(missing_ok=True)
        return False, f"{slug} timeout"
    body_path.unlink(missing_ok=True)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip().splitlines()
        tail = " | ".join(stderr[-3:]) if stderr else "(no stderr)"
        return False, f"{slug} exit={result.returncode}: {tail}"
    return True, slug


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--tsv", required=True,
                   help="tsv: kind<TAB>url[<TAB>slug-override]; '#' = comment")
    p.add_argument("--delay", type=float, default=1.0,
                   help="seconds between HTTP fetches (default 1.0)")
    p.add_argument("--cwd", help="working directory for the ingest subprocess "
                                  "(defaults to current dir; use to target a "
                                  "specific vault when the marker isn't in cwd)")
    args = p.parse_args(argv)

    rows: list[tuple[str, str, str | None]] = []
    for line in Path(args.tsv).read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        fields = line.split("\t")
        kind = fields[0].strip()
        url = fields[1].strip() if len(fields) > 1 else ""
        slug = fields[2].strip() if len(fields) > 2 and fields[2].strip() else None
        if kind and url:
            rows.append((kind, url, slug))

    if not rows:
        print("no rows in TSV", file=sys.stderr)
        return 2

    cwd = Path(args.cwd) if args.cwd else None
    ok: list[str] = []
    fail: list[str] = []
    for i, (kind, url, slug) in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {kind} {url}", flush=True)
        success, msg = ingest_one(kind, url, slug, cwd)
        if success:
            ok.append(f"{kind}/{msg}")
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
