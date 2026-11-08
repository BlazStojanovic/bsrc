#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_supported_os

with_mcps=0
ubuntu=0

usage() {
  cat <<'EOF'
Usage: ./setup.sh [--with-mcps] [--ubuntu]

Options:
  --with-mcps  Also install the managed Claude Code and Codex MCP servers.
  --ubuntu     Install the Ubuntu component subset (tmux, nvim, claude,
               codex, git, zsh, yazi, btop, devpod, obsidian-skills).
               Skips macOS-only components (ghostty, peonping, fonts,
               anki, knowledge-smith).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-mcps)
      with_mcps=1
      ;;
    --ubuntu)
      ubuntu=1
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

if [[ "$ubuntu" == "0" && "$(os_id)" != "macos" ]]; then
  err "Detected non-macOS host. Re-run with --ubuntu."
  exit 1
fi

export BSRC_WITH_MCPS="$with_mcps"

if [[ "$ubuntu" == "1" ]]; then
  components=(
    zsh
    git
    tmux
    nvim
    btop
    yazi
    codex
    claude
    devpod
    obsidian-skills
  )
else
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
    devpod
    knowledge-smith
    anki
    obsidian-skills
    grafana
  )
fi

for component in "${components[@]}"; do
  log "Installing ${component}"
  "$ROOT_DIR/$component/install.sh"
done

if [[ "$with_mcps" == "1" ]]; then
  log "Managed MCP install summary:"
  printf '  - Claude: /mcp auth required for notion and coda\n'
  printf '  - Codex: run codex mcp login notion\n'
  printf '  - Coda for Codex: export CODA_MCP_AUTH_TOKEN\n'
fi

log "Setup complete."
if [[ "$(os_id)" == "ubuntu" ]] && [[ "${SHELL:-}" != *zsh ]]; then
  log "Start a zsh session: exec zsh"
else
  log "Open a new terminal or run: source ~/.zshrc"
fi
