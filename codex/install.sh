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

print_codex_mcp_summary() {
  log "Codex MCP summary: notion, coda, linear, grafana configured"

  if have_cmd codex; then
    warn "Codex still needs 'codex mcp login notion' and 'codex mcp login linear'."
  else
    warn "Codex CLI is not currently on PATH; config was written but login could not be verified."
  fi

  if [[ -n "${CODA_MCP_AUTH_TOKEN:-}" ]]; then
    log "Coda token env detected: CODA_MCP_AUTH_TOKEN"
  else
    warn "Coda token env missing: CODA_MCP_AUTH_TOKEN"
  fi

  if have_cmd mcp-grafana; then
    log "Grafana binary ready for Codex: $(command -v mcp-grafana)"
  else
    warn "Grafana binary still missing for Codex: mcp-grafana"
  fi

  if [[ -n "${GRAFANA_URL:-}" ]]; then
    log "Grafana URL env detected: GRAFANA_URL"
  else
    warn "Grafana URL env missing: GRAFANA_URL"
  fi

  if [[ -n "${GRAFANA_SERVICE_ACCOUNT_TOKEN:-}" ]]; then
    log "Grafana token env detected: GRAFANA_SERVICE_ACCOUNT_TOKEN"
  else
    warn "Grafana token env missing: GRAFANA_SERVICE_ACCOUNT_TOKEN"
  fi
}

render_codex_config

if [[ "$with_mcps" == "1" ]]; then
  install_grafana_mcp_binary
  print_codex_mcp_summary
fi
