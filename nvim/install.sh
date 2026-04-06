#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_macos

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

link_file "$ROOT_DIR/nvim" "$HOME/.config/nvim"
ensure_dir "$HOME/.local/state/nvim/undo"
ensure_dir "$HOME/.local/share/nvim"
ensure_dir "$HOME/.cache/nvim"
ensure_dir "$HOME/.local/bin"

export NPM_CONFIG_PREFIX="${NPM_CONFIG_PREFIX:-$HOME/.local}"
export PATH="$HOME/.local/bin:$PATH"

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_brew_packages() {
  local packages=(
    neovim
    ripgrep
    fd
    go
    tree-sitter
    tree-sitter-cli
    lua-language-server
    ruff
    rust-analyzer
  )

  if ! have_cmd brew; then
    warn "Homebrew not found. Skipping package installation for: ${packages[*]}"
    return 0
  fi

  local package
  for package in "${packages[@]}"; do
    if brew list "$package" >/dev/null 2>&1; then
      log "brew package already installed: $package"
    else
      log "Installing brew package: $package"
      brew install "$package"
    fi
  done
}

install_npm_packages() {
  local packages=(
    pyright
    typescript
    typescript-language-server
  )

  if ! have_cmd npm; then
    warn "npm not found. Skipping npm LSP packages: ${packages[*]}"
    return 0
  fi

  npm config set prefix "$NPM_CONFIG_PREFIX"

  local package
  for package in "${packages[@]}"; do
    if npm list -g --depth=0 "$package" >/dev/null 2>&1; then
      log "npm package already installed: $package"
    else
      log "Installing npm package: $package"
      npm install -g "$package"
    fi
  done
}

install_go_tools() {
  if ! have_cmd go; then
    warn "go not found. Skipping Go tool installation: gopls"
    return 0
  fi

  log "Installing Go tool: gopls"
  go install golang.org/x/tools/gopls@latest
}

check_clangd() {
  if have_cmd clangd; then
    log "clangd is available on PATH"
    return 0
  fi

  if have_cmd xcrun && xcrun --find clangd >/dev/null 2>&1; then
    log "clangd is available via xcrun"
    return 0
  fi

  warn "clangd was not found. Install Xcode Command Line Tools or make an LLVM clangd available on PATH."
}

install_brew_packages
install_npm_packages
install_go_tools
check_clangd

log "Neovim install finished."
log "First launch will bootstrap lazy.nvim and install plugins."
