#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_macos

bootstrap_homebrew_shellenv

if ! command -v brew >/dev/null 2>&1; then
  warn "Homebrew not found. Skipping gcx installation."
  exit 0
fi

if command -v gcx >/dev/null 2>&1; then
  log "gcx already installed: $(command -v gcx)"
else
  log "Installing brew package: gcx"
  brew install grafana/grafana/gcx
fi

if ! command -v gcx >/dev/null 2>&1; then
  warn "gcx installation finished but the binary is not on PATH."
  exit 0
fi

if gcx config check >/dev/null 2>&1; then
  log "gcx config check passed"
else
  warn "gcx is installed but not authenticated. Run the manual login:"
  warn "  gcx login poolside --server https://poolside.grafana.net --token '<token>' --yes"
  warn "  gcx config set contexts.poolside.grafana.org-id 1"
fi
