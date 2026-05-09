#!/usr/bin/env bash
# Shared helpers for the bsrc anki skill scripts. Sourceable, no side
# effects on import.

# shellcheck shell=bash

ANK_ENV_FILE="${ANK_ENV_FILE:-$HOME/.config/bsrc/anki.env}"
ANK_VAULT_MARKER=".anki-cards"
ANK_MCP_URL="${ANK_MCP_URL:-http://127.0.0.1:3141/}"

ank_log()  { printf "\033[1;32m[anki]\033[0m %s\n" "$*"; }
ank_warn() { printf "\033[1;33m[anki!]\033[0m %s\n" "$*" >&2; }
ank_err()  { printf "\033[1;31m[anki×]\033[0m %s\n" "$*" >&2; }

ank_have_cmd() { command -v "$1" >/dev/null 2>&1; }

# Resolve the cards dir. Echoes the absolute path on success; exits 10 on
# failure with a clear hint.
ank_resolve_cards_dir() {
  local candidate=""

  if [[ -n "${ANKI_CARDS_DIR:-}" ]]; then
    candidate="$ANKI_CARDS_DIR"
  elif [[ -f "$ANK_ENV_FILE" ]]; then
    candidate="$(grep -E '^ANKI_CARDS_DIR=' "$ANK_ENV_FILE" | tail -n1 | cut -d= -f2-)"
  fi

  candidate="${candidate/#\~/$HOME}"

  if [[ -n "$candidate" ]]; then
    if [[ ! -d "$candidate" ]]; then
      ank_err "ANKI_CARDS_DIR points to a non-existent directory: $candidate"
      exit 10
    fi
    if [[ ! -f "$candidate/$ANK_VAULT_MARKER" ]]; then
      ank_warn "$ANK_VAULT_MARKER marker missing in: $candidate"
    fi
    printf '%s\n' "$candidate"
    return 0
  fi

  local dir
  dir="$(pwd)"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/$ANK_VAULT_MARKER" ]]; then
      printf '%s\n' "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done

  ank_err "no anki cards dir found."
  ank_err "Set ANKI_CARDS_DIR, cd into a dir containing $ANK_VAULT_MARKER,"
  ank_err "or re-run bsrc/anki/install.sh to persist the path."
  exit 10
}

# Reachability probe for the Anki MCP server. Sends a real `initialize`
# JSON-RPC call with SSE-aware Accept headers — a bare GET or empty POST
# returns 406, which would falsely look like the server is down.
ank_mcp_reachable() {
  local resp
  resp="$(curl -fsS --max-time 3 -X POST "$ANK_MCP_URL" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"bsrc-doctor","version":"0.1"}}}' \
    2>/dev/null || true)"
  [[ "$resp" == *'"serverInfo"'* ]]
}

# True if Anki is currently running. Proxy: the MCP addon answers.
# pgrep is unreliable (Anki on macOS launches as python with argv[0]="Anki").
ank_anki_running() {
  ank_mcp_reachable
}
