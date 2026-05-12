#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

require_supported_os

bootstrap_homebrew_shellenv

link_file "$ROOT_DIR/nvim" "$HOME/.config/nvim"
ensure_dir "$HOME/.local/state/nvim/undo"
ensure_dir "$HOME/.local/share/nvim"
ensure_dir "$HOME/.cache/nvim"
ensure_dir "$HOME/.local/bin"

export NPM_CONFIG_PREFIX="${NPM_CONFIG_PREFIX:-$HOME/.local}"
export PATH="$HOME/.local/bin:$PATH"

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

add_neovim_ppa() {
  if ls /etc/apt/sources.list.d/ 2>/dev/null | grep -qi 'neovim'; then
    log "neovim-ppa already configured"
    return 0
  fi

  if ! have_cmd add-apt-repository; then
    apt_install software-properties-common
  fi

  local sudo_cmd=()
  if [[ "$(id -u)" -ne 0 ]]; then
    if have_cmd sudo; then
      sudo_cmd=(sudo)
    else
      err "Need root or sudo to add ppa:neovim-ppa/unstable"
      return 1
    fi
  fi

  log "Adding ppa:neovim-ppa/unstable"
  "${sudo_cmd[@]}" add-apt-repository -y ppa:neovim-ppa/unstable
  "${sudo_cmd[@]}" apt-get update
}

upgrade_neovim_to_ppa() {
  local installed
  installed="$(dpkg-query -W -f='${Version}' neovim 2>/dev/null || true)"
  if [[ -z "$installed" ]]; then
    return 0
  fi

  # The config requires nvim 0.11+. Anything older needs an upgrade from the PPA.
  if [[ "$installed" =~ ^0\.([0-9]|10)\. ]]; then
    local sudo_cmd=()
    if [[ "$(id -u)" -ne 0 ]] && have_cmd sudo; then
      sudo_cmd=(sudo)
    fi
    log "Upgrading neovim from $installed to PPA build"
    "${sudo_cmd[@]}" apt-get install -y --only-upgrade neovim
  fi
}

install_apt_packages() {
  add_neovim_ppa
  apt_install neovim ripgrep fd-find clangd golang-go
  upgrade_neovim_to_ppa

  # Availability varies across releases (rust-analyzer/ruff/lua-language-server
  # are missing on older Ubuntu). tree-sitter-cli is never in apt; npm install
  # picks it up below.
  apt_install_optional rust-analyzer ruff lua-language-server

  if have_cmd fdfind && ! have_cmd fd; then
    ln -sf "$(command -v fdfind)" "$HOME/.local/bin/fd"
    log "Linked fd -> fdfind in $HOME/.local/bin"
  fi
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

  if [[ "$(os_id)" == "macos" ]] && have_cmd xcrun && xcrun --find clangd >/dev/null 2>&1; then
    log "clangd is available via xcrun"
    return 0
  fi

  warn "clangd was not found. Install via apt (clangd), brew (llvm), or Xcode CLT."
}

case "$(os_id)" in
  macos)
    install_brew_packages
    ;;
  ubuntu)
    install_apt_packages
    ;;
esac
install_npm_packages
install_go_tools
check_clangd

log "Neovim install finished."
log "First launch will bootstrap lazy.nvim and install plugins."
