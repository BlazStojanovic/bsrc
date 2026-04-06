#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

ensure_dir "$HOME/.claude"
link_file "$ROOT_DIR/claude/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
