#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_macos

NERD_FONT_NAME="${NERD_FONT_NAME:-Hack}"

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
