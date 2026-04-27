#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_macos

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

if ! command -v brew >/dev/null 2>&1; then
  warn "Homebrew not found. Skipping peon-ping installation."
  exit 0
fi

if brew list peon-ping >/dev/null 2>&1; then
  log "brew package already installed: peon-ping"
else
  log "Installing brew package: peon-ping"
  brew install PeonPing/tap/peon-ping
fi

peon_prefix="$(brew --prefix peon-ping 2>/dev/null || true)"
runtime_installer="$peon_prefix/libexec/install.sh"

if [[ -x "$runtime_installer" ]]; then
  log "Installing peon-ping runtime for Codex and Claude adapters"
  bash "$runtime_installer" --no-rc
else
  warn "peon-ping runtime installer not found at $runtime_installer"
fi
