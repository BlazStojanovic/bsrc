#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1", "pyyaml>=6.0"]
# ///
"""Flatten a WebVTT auto-subs file into prose markdown on stdout.

Strips timing cues, HTML, and consecutive duplicate lines. Deterministic.

Example:
  helpers/vtt_flatten.py /tmp/<id>.en.vtt > /tmp/<id>.transcript.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _ks_helpers import vtt_to_markdown  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("vtt_path", help="path to a .vtt file (or '-' for stdin)")
    args = p.parse_args(argv)

    if args.vtt_path == "-":
        vtt = sys.stdin.read()
    else:
        vtt = Path(args.vtt_path).expanduser().read_text(encoding="utf-8")
    sys.stdout.write(vtt_to_markdown(vtt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
