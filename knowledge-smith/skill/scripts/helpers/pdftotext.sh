#!/usr/bin/env bash
# Run `pdftotext <pdf> -` and print the result to stdout.
# Pass --layout as the first arg to preserve column layout (good for tables).
#
# Example:
#   helpers/pdftotext.sh paper.pdf > /tmp/body.txt
#   helpers/pdftotext.sh --layout paper.pdf > /tmp/body.txt

set -euo pipefail

usage() {
  echo "usage: pdftotext.sh [--layout] <pdf>" >&2
  exit 2
}

if [[ $# -lt 1 ]]; then usage; fi
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then usage; fi

if ! command -v pdftotext >/dev/null 2>&1; then
  echo "[ks×] pdftotext not found — install poppler (\`brew install poppler\`)" >&2
  exit 11
fi

if [[ "$1" == "--layout" ]]; then
  shift
  [[ $# -ge 1 ]] || usage
  exec pdftotext -layout "$1" -
else
  exec pdftotext "$1" -
fi
