#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

if [[ "$(os_id)" == "ubuntu" ]]; then
  apt_install zsh
fi

if ! have_cmd zsh; then
  warn "zsh binary not found on PATH. oh-my-zsh + rc files will be linked, but interactive zsh sessions won't work until zsh is installed."
fi

if [[ ! -d "$HOME/.oh-my-zsh/.git" ]]; then
  log "Installing oh-my-zsh"
  git clone https://github.com/ohmyzsh/ohmyzsh.git "$HOME/.oh-my-zsh"
else
  log "oh-my-zsh already present: $HOME/.oh-my-zsh"
fi

link_file "$ROOT_DIR/zsh/zshrc" "$HOME/.zshrc"
link_file "$ROOT_DIR/zsh/zprofile" "$HOME/.zprofile"

# Offer to set zsh as the default login shell. Opt-in via BSRC_SET_ZSH_DEFAULT=1
# so we never silently flip a user's shell.
if [[ "${BSRC_SET_ZSH_DEFAULT:-0}" == "1" ]] && have_cmd zsh; then
  zsh_path="$(command -v zsh)"
  current_shell="$(getent passwd "$(id -un)" 2>/dev/null | cut -d: -f7 || echo "")"
  if [[ "$current_shell" == "$zsh_path" ]]; then
    log "Default shell already zsh: $zsh_path"
  elif have_cmd chsh; then
    log "Setting default shell to zsh: $zsh_path"
    if ! grep -qxF "$zsh_path" /etc/shells 2>/dev/null; then
      warn "$zsh_path not listed in /etc/shells; chsh may refuse. Add it manually if needed."
    fi
    chsh -s "$zsh_path" || warn "chsh failed. Set the shell manually: chsh -s $zsh_path"
  else
    warn "chsh not available. Set the shell manually."
  fi
fi
