#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_macos

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

ghostty_app="/Applications/Ghostty.app"

if command -v brew >/dev/null 2>&1; then
  if brew list --cask ghostty >/dev/null 2>&1; then
    log "brew cask already installed: ghostty"
  elif [[ -d "$ghostty_app" ]]; then
    warn "Ghostty app already exists at $ghostty_app; skipping Homebrew cask install."
  else
    log "Installing brew cask: ghostty"
    brew install --cask ghostty
  fi
else
  warn "Homebrew not found. Skipping Ghostty installation."
fi

link_file "$ROOT_DIR/ghostty/config.ghostty" "$HOME/.config/ghostty/config.ghostty"
link_file "$ROOT_DIR/ghostty/config.ghostty" "$HOME/.config/ghostty/config"
link_file "$ROOT_DIR/ghostty/monokai-custom.theme" "$HOME/.config/ghostty/themes/monokai-custom.theme"
link_file "$ROOT_DIR/ghostty/monokai-custom-light.theme" "$HOME/.config/ghostty/themes/monokai-custom-light.theme"
