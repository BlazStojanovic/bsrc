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
Usage: ./claude/install.sh [--with-mcps]

Options:
  --with-mcps  Also add the managed user-scope Claude Code MCP servers.
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

add_claude_mcp() {
  local name="$1"
  shift

  local output
  if output="$(claude mcp add --scope user "$@" 2>&1)"; then
    log "Configured Claude MCP: ${name}"
    return 0
  fi

  if [[ "$output" == *"already exists"* ]]; then
    log "Claude MCP already configured: ${name}"
    return 0
  fi

  err "$output"
  return 1
}

print_claude_mcp_summary() {
  log "Claude MCP summary: notion, coda, linear, grafana configured"
  warn "Claude still needs /mcp authentication for notion, coda, and linear."

  if have_cmd mcp-grafana; then
    log "Grafana binary ready for Claude: $(command -v mcp-grafana)"
  else
    warn "Grafana binary still missing for Claude: mcp-grafana"
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

ensure_dir "$HOME/.claude"
link_file "$ROOT_DIR/claude/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
link_file "$ROOT_DIR/claude/settings.json" "$HOME/.claude/settings.json"
link_file "$ROOT_DIR/claude/statusline.sh" "$HOME/.claude/statusline.sh"

if [[ "$with_mcps" == "1" ]]; then
  if ! command -v claude >/dev/null 2>&1; then
    warn "Skipping Claude MCP install because the 'claude' CLI is not available."
    exit 0
  fi

  install_grafana_mcp_binary
  add_claude_mcp notion --transport http notion https://mcp.notion.com/mcp
  add_claude_mcp coda --transport http coda https://coda.io/apis/mcp
  add_claude_mcp linear --transport http linear https://mcp.linear.app/mcp
  add_claude_mcp grafana grafana -- mcp-grafana
  print_claude_mcp_summary
fi
