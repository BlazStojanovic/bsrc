#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27",
#   "markdownify>=0.13",
#   "python-frontmatter>=1.1",
#   "pyyaml>=6.0",
# ]
# ///
"""Fetch ar5iv HTML for an arXiv id and emit markdown to stdout.

Exit 1 (no output) if ar5iv has no version of the paper.

Example:
  helpers/fetch_ar5iv.py 1706.03762 > /tmp/attention.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _ks_helpers import fetch_ar5iv  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("arxiv_id", help="arXiv id (e.g. 1706.03762)")
    args = p.parse_args(argv)

    md = fetch_ar5iv(args.arxiv_id)
    if md is None:
        return 1
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
