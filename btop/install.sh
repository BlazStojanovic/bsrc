#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_supported_os

case "$(os_id)" in
  macos)
    bootstrap_homebrew_shellenv
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
    ;;
  ubuntu)
    apt_install btop
    ;;
esac

link_file "$ROOT_DIR/btop/monokai-bsrc-dark.theme" "$HOME/.config/btop/themes/monokai-bsrc-dark.theme"
link_file "$ROOT_DIR/btop/monokai-bsrc-light.theme" "$HOME/.config/btop/themes/monokai-bsrc-light.theme"
link_file "$ROOT_DIR/btop/btop.conf" "$HOME/.config/btop/btop.conf"

# The bundled wrapper uses `defaults` (macOS) to flip light/dark themes and
# assumes the real btop binary lives at /opt/homebrew/bin/btop. Skip linking
# it on Ubuntu — system `btop` reads the themes/config directly.
if [[ "$(os_id)" == "macos" ]]; then
  link_file "$ROOT_DIR/btop/btop" "$HOME/.local/bin/btop"
fi
