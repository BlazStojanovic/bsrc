#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

with_mcps="${BSRC_WITH_MCPS:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-mcps)
      with_mcps=1
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./codex/install.sh [--with-mcps]

Options:
  --with-mcps  Also include the managed Codex MCP servers in ~/.codex/config.toml.
EOF
      exit 0
      ;;
    *)
      err "Unknown option: $1"
      exit 1
      ;;
  esac
  shift
done

render_codex_config() {
  local dest="$HOME/.codex/config.toml"
  local tmp

  tmp="$(mktemp)"

  cat "$ROOT_DIR/codex/config.toml" > "$tmp"

  if [[ "$with_mcps" == "1" ]]; then
    printf '\n' >> "$tmp"
    cat "$ROOT_DIR/codex/mcp-servers.toml" >> "$tmp"
  fi

  ensure_dir "$(dirname "$dest")"

  if [[ -e "$dest" || -L "$dest" ]]; then
    if cmp -s "$tmp" "$dest"; then
      rm -f "$tmp"
      log "Codex config already up to date: $dest"
      return 0
    fi

    rm -f "$dest"
  fi

  mv "$tmp" "$dest"
  log "Installed Codex config: $dest"
}

render_codex_config

if [[ "$with_mcps" == "1" ]]; then
  if ! command -v mcp-grafana >/dev/null 2>&1; then
    warn "Grafana MCP is configured for Codex, but 'mcp-grafana' is not currently in PATH."
  fi

  warn "Run 'codex mcp login notion' and 'codex mcp login linear' to finish OAuth setup."
  warn "Export CODA_MCP_AUTH_TOKEN before using the Codex Coda MCP."
fi
