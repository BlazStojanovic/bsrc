#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "python-frontmatter>=1.1", "pyyaml>=6.0"]
# ///
"""Download a PDF to a destination path. Streams + atomic rename.

Examples:
  helpers/download_pdf.py https://arxiv.org/pdf/1706.03762.pdf /tmp/p.pdf
  helpers/download_pdf.py --arxiv 1706.03762 /tmp/p.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _ks_helpers import download_arxiv_pdf, download_pdf  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("url", nargs="?", help="PDF URL (omit if --arxiv)")
    p.add_argument("dest", help="destination file path")
    p.add_argument("--arxiv", help="arXiv id (uses arxiv.org/pdf/<id>.pdf)")
    args = p.parse_args(argv)

    dest = Path(args.dest).expanduser()
    if args.arxiv:
        ok = download_arxiv_pdf(args.arxiv, dest)
    elif args.url:
        ok = download_pdf(args.url, dest)
    else:
        p.error("must pass URL or --arxiv")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
