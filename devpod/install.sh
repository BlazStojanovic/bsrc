#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

skill_src="$ROOT_DIR/devpod/skill"

# The laptop drives the pod; inside a pod only the skill is useful.
if [[ "$(os_id)" == "macos" ]]; then
  ensure_dir "$HOME/.local/bin"
  link_file "$ROOT_DIR/devpod/bin/devpod" "$HOME/.local/bin/devpod"
  for tool in infractl kubectl aws jq; do
    have_cmd "$tool" || warn "devpod needs $tool on PATH"
  done
fi

ensure_dir "$HOME/.claude/skills"
link_file "$skill_src" "$HOME/.claude/skills/devpod"
ensure_dir "${CODEX_HOME:-$HOME/.codex}/skills"
link_file "$skill_src" "${CODEX_HOME:-$HOME/.codex}/skills/devpod"

if [[ "$(os_id)" == "macos" ]]; then
  log "devpod installed. Try: devpod status"
fi
