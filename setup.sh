#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_macos

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

log "Setup complete."
log "Open a new terminal or run: source ~/.zshrc"
