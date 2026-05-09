#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1"]
# ///
"""Write a blog, github, or course bookmark note into the active vault.

The agent extracts metadata (title, author/instructor, description)
by WebFetch'ing the URL itself, then passes it via --metadata-json.
This script just writes the note. No fetching, no regex.

For GitHub URLs the agent should also pass `owner` and `repo` (parsed
from the URL) so the basename is `<owner>-<repo>.md`.

Required JSON keys:
  blog:   title, url
  github: url   (title and owner/repo recommended)
  course: title, url   (instructor/institution/year recommended)

Examples:
  uv run ingest_bookmark.py --kind blog --metadata-json '{
    "url": "https://example.com/post",
    "title": "How X works",
    "author": "Jane Doe",
    "description": "Short hook"
  }'

  uv run ingest_bookmark.py --kind github --metadata-json '{
    "url": "https://github.com/openai/whisper",
    "owner": "openai",
    "repo": "whisper",
    "title": "openai/whisper",
    "description": "Robust speech recognition"
  }'

  uv run ingest_bookmark.py --kind course --metadata-json '{
    "url": "https://stanford-cs336.github.io/spring2024/",
    "title": "CS336: Language Models from Scratch",
    "instructor": "Percy Liang & Tatsunori Hashimoto",
    "institution": "Stanford",
    "year": 2024,
    "description": "Hands-on course building LLMs end-to-end."
  }'
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
    slugify,
    stub_filename,
    today,
    validate_metadata_json,
    write_frontmatter,
)

GITHUB_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/?#]+)/?", re.I)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", choices=("blog", "github", "course"), required=True)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--force", action="store_true", help="overwrite existing note")
    args = p.parse_args(argv)

    meta = validate_metadata_json(args.metadata_json, args.kind)
    url = meta["url"]
    parsed = urlparse(url)
    if not (parsed.scheme and parsed.netloc):
        die(2, f"not a usable URL: {url!r}")

    vault = find_vault().path
    info(f"vault: {vault}")
    info(f"kind:  {args.kind}")

    if args.kind == "github":
        owner = meta.get("owner")
        repo = meta.get("repo")
        if not (owner and repo):
            m = GITHUB_RE.match(url)
            if not m:
                die(2, f"github URL missing owner/repo and not parseable: {url}")
            owner = owner or m.group(1)
            repo = repo or m.group(2).rstrip(".git")
        slug = slugify(repo)
        basename = stub_filename(None, f"{slugify(owner)}-{slug}")
        title = meta.get("title") or f"{owner}/{repo}"
        note_meta = {
            "type": "note",
            "kind": "github",
            "slug": slug,
            "title": title,
            "created": today(),
            "updated": today(),
            "read": False,
            "tags": [],
            "url": url,
            "description": meta.get("description"),
        }
    elif args.kind == "course":
        title = meta["title"]
        slug = meta.get("slug") or slugify(title)
        basename = stub_filename(None, slug)
        note_meta = {
            "type": "note",
            "kind": "course",
            "slug": slug,
            "title": title,
            "created": today(),
            "updated": today(),
            "read": False,
            "tags": [],
            "url": url,
            "instructor": meta.get("instructor"),
            "institution": meta.get("institution"),
            "year": meta.get("year"),
            "description": meta.get("description"),
        }
    else:  # blog
        title = meta["title"]
        slug = meta.get("slug") or slugify(title)
        basename = stub_filename(None, slug)
        note_meta = {
            "type": "note",
            "kind": "blog",
            "slug": slug,
            "title": title,
            "created": today(),
            "updated": today(),
            "read": False,
            "tags": [],
            "url": url,
            "author": meta.get("author"),
            "description": meta.get("description"),
        }

    body = (
        f"# {title}\n\n"
        f"{meta.get('description') or '(no description)'}\n\n"
        "## Notes\n\n(stub)\n"
    )

    target = note_path(vault, args.kind, basename)
    refuse_if_exists(target, args.force)
    write_frontmatter(target, note_meta, body)
    info(f"wrote: {target.relative_to(vault)}")

    print(f"note={target}")
    print(f"kind={args.kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
