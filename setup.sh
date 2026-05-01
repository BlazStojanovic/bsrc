#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_macos

with_mcps=0

usage() {
  cat <<'EOF'
Usage: ./setup.sh [--with-mcps]

Options:
  --with-mcps  Also install the managed Claude Code and Codex MCP servers.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-mcps)
      with_mcps=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

export BSRC_WITH_MCPS="$with_mcps"

components=(
  fonts
  zsh
  git
  ghostty
  tmux
  nvim
  btop
  yazi
  peonping
  codex
  claude
  feynman
)

for component in "${components[@]}"; do
  log "Installing ${component}"
  "$ROOT_DIR/$component/install.sh"
done

if [[ "$with_mcps" == "1" ]]; then
  log "Managed MCP install summary:"
  printf '  - Claude: /mcp auth required for notion, coda, and linear\n'
  printf '  - Codex: run codex mcp login notion and codex mcp login linear\n'
  printf '  - Coda for Codex: export CODA_MCP_AUTH_TOKEN\n'
  printf '  - Grafana: ensure GRAFANA_URL and GRAFANA_SERVICE_ACCOUNT_TOKEN are set\n'
fi

log "Setup complete."
log "Open a new terminal or run: source ~/.zshrc"
