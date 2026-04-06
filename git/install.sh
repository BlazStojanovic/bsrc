#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

link_file "$ROOT_DIR/git/gitconfig" "$HOME/.gitconfig"
link_file "$ROOT_DIR/git/git-commit-all" "$HOME/.local/bin/git-commit-all"
