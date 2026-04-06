#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

if [[ ! -d "$HOME/.oh-my-zsh/.git" ]]; then
  log "Installing oh-my-zsh"
  git clone https://github.com/ohmyzsh/ohmyzsh.git "$HOME/.oh-my-zsh"
else
  log "oh-my-zsh already present: $HOME/.oh-my-zsh"
fi

link_file "$ROOT_DIR/zsh/zshrc" "$HOME/.zshrc"
link_file "$ROOT_DIR/zsh/zprofile" "$HOME/.zprofile"
