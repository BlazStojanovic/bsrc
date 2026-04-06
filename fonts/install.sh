#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_macos

NERD_FONT_NAME="${NERD_FONT_NAME:-Hack}"
ASSETS_DIR="$ROOT_DIR/assets"
BUILD_SCRIPT="$ROOT_DIR/fonts/build-agent-icons.py"

if ! command -v brew >/dev/null 2>&1; then
  err "Homebrew is required to install Nerd Fonts."
  exit 1
fi

eval "$(/opt/homebrew/bin/brew shellenv)"

brew tap homebrew/cask-fonts >/dev/null 2>&1 || true

cask="font-$(printf '%s' "$NERD_FONT_NAME" | tr '[:upper:]' '[:lower:]')-nerd-font"

if brew info --cask "$cask" >/dev/null 2>&1; then
  if brew list --cask "$cask" >/dev/null 2>&1; then
    log "Nerd Font already installed: $NERD_FONT_NAME"
  else
    log "Installing Nerd Font: $NERD_FONT_NAME"
    brew install --cask "$cask"
  fi
else
  err "Unknown Nerd Font cask: $cask"
  exit 1
fi

if ! brew list fontforge >/dev/null 2>&1; then
  log "Installing FontForge"
  brew install fontforge
fi

if command -v fontforge >/dev/null 2>&1; then
  build_custom_font() {
    local src="$1"
    local out="$2"
    local tmp

    [[ -f "$src" ]] || return 0
    log "Building patched font: $(basename "$out")"
    tmp="$(mktemp "/tmp/$(basename "$out" .ttf).XXXXXX.ttf")"
    fontforge -lang=py -script "$BUILD_SCRIPT" "$src" "$tmp" "$ASSETS_DIR"
    mv "$tmp" "$out"
  }

  build_custom_font "$HOME/Library/Fonts/HackNerdFontMono-Regular.ttf" "$HOME/Library/Fonts/HackNerdFontMonoBsrc-Regular.ttf"
  build_custom_font "$HOME/Library/Fonts/HackNerdFontMono-Bold.ttf" "$HOME/Library/Fonts/HackNerdFontMonoBsrc-Bold.ttf"
  build_custom_font "$HOME/Library/Fonts/HackNerdFontMono-Italic.ttf" "$HOME/Library/Fonts/HackNerdFontMonoBsrc-Italic.ttf"
  build_custom_font "$HOME/Library/Fonts/HackNerdFontMono-BoldItalic.ttf" "$HOME/Library/Fonts/HackNerdFontMonoBsrc-BoldItalic.ttf"

  if command -v fc-cache >/dev/null 2>&1; then
    fc-cache -f "$HOME/Library/Fonts" >/dev/null 2>&1 || true
  fi
else
  log "fontforge not installed; skipping custom agent icon font build"
fi
