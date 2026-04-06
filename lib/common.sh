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
