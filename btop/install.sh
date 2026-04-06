#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_macos

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

if command -v brew >/dev/null 2>&1; then
  if brew list btop >/dev/null 2>&1; then
    log "brew package already installed: btop"
  else
    log "Installing brew package: btop"
    brew install btop
  fi
else
  warn "Homebrew not found. Skipping btop installation."
fi

link_file "$ROOT_DIR/btop/monokai-bsrc-dark.theme" "$HOME/.config/btop/themes/monokai-bsrc-dark.theme"
link_file "$ROOT_DIR/btop/monokai-bsrc-light.theme" "$HOME/.config/btop/themes/monokai-bsrc-light.theme"
link_file "$ROOT_DIR/btop/btop.conf" "$HOME/.config/btop/btop.conf"
link_file "$ROOT_DIR/btop/btop" "$HOME/.local/bin/btop"
