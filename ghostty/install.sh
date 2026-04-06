#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

link_file "$ROOT_DIR/ghostty/ghostty.conf" "$HOME/.config/ghostty/config"
link_file "$ROOT_DIR/ghostty/monokai-custom.theme" "$HOME/.config/ghostty/themes/monokai-custom.theme"
link_file "$ROOT_DIR/ghostty/monokai-custom-light.theme" "$HOME/.config/ghostty/themes/monokai-custom-light.theme"
