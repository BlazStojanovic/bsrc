#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1", "pyyaml>=6.0"]
# ///
"""Copy an Obsidian Web Clipper markdown file into the vault's raw/articles/.

Preserves the clipper's original frontmatter under a `clipper:` block so
the agent can inspect it later. Prints the destination path on success.

Example:
  helpers/clipper_copy.py /tmp/clipper.md \\
      ~/Desktop/poolside-kb/raw/articles/2024-evals.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _ks_helpers import copy_clipper  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("src", help="path to the clipper .md file")
    p.add_argument("dest", help="destination path inside the vault's raw/articles/")
    p.add_argument("--force", action="store_true", help="overwrite existing dest")
    args = p.parse_args(argv)

    src = Path(args.src).expanduser().resolve()
    dest = Path(args.dest).expanduser()
    copy_clipper(src, dest, force=args.force)
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
