#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

link_file "$ROOT_DIR/yazi/yazi.toml" "$HOME/.config/yazi/yazi.toml"
