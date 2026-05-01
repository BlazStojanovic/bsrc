#!/usr/bin/env bash

set -euo pipefail

log() {
  printf "\033[1;32m[+]\033[0m %s\n" "$*"
}

warn() {
  printf "\033[1;33m[!]\033[0m %s\n" "$*"
}

err() {
  printf "\033[1;31m[x]\033[0m %s\n" "$*" >&2
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

require_macos() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    err "bsrc currently supports macOS only."
    exit 1
  fi
}

ensure_dir() {
  mkdir -p "$1"
}

link_file() {
  local src="$1"
  local dest="$2"

  ensure_dir "$(dirname "$dest")"

  if [[ -L "$dest" ]]; then
    local current_target
    current_target="$(readlink "$dest")"
    if [[ "$current_target" == "$src" ]]; then
      log "Link already correct: $dest"
      return 0
    fi

    rm "$dest"
    ln -s "$src" "$dest"
    log "Updated link: $dest -> $src"
    return 0
  fi

  if [[ -e "$dest" ]]; then
    rm -rf "$dest"
    ln -s "$src" "$dest"
    log "Replaced existing path: $dest -> $src"
    return 0
  fi

  ln -s "$src" "$dest"
  log "Linked: $dest -> $src"
}

append_line_once() {
  local line="$1"
  local dest="$2"

  ensure_dir "$(dirname "$dest")"
  touch "$dest"

  if grep -qxF "$line" "$dest"; then
    log "Already present in $dest"
    return 0
  fi

  printf '%s\n' "$line" >> "$dest"
  log "Updated: $dest"
}

bootstrap_homebrew_shellenv() {
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
}

install_grafana_mcp_binary() {
  local gobin="${GOBIN:-$HOME/.local/bin}"

  ensure_dir "$gobin"
  export GOBIN="$gobin"
  export PATH="$GOBIN:$PATH"

  if have_cmd mcp-grafana; then
    log "Grafana MCP binary already installed: $(command -v mcp-grafana)"
    return 0
  fi

  bootstrap_homebrew_shellenv

  if ! have_cmd go; then
    if have_cmd brew; then
      if brew list go >/dev/null 2>&1; then
        log "brew package already installed: go"
      else
        log "Installing brew package: go"
        brew install go
      fi
    else
      warn "go not found and Homebrew not found. Skipping mcp-grafana installation."
      return 0
    fi
  fi

  log "Installing Grafana MCP binary: mcp-grafana"
  GOBIN="$GOBIN" go install github.com/grafana/mcp-grafana/cmd/mcp-grafana@latest

  if have_cmd mcp-grafana; then
    log "Installed Grafana MCP binary: $(command -v mcp-grafana)"
    return 0
  fi

  if [[ -x "$GOBIN/mcp-grafana" ]]; then
    log "Installed Grafana MCP binary: $GOBIN/mcp-grafana"
    return 0
  fi

  err "mcp-grafana installation completed without a usable binary on PATH."
  return 1
}
