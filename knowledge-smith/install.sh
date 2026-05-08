#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

if ! have_cmd uv; then
  err "knowledge-smith requires 'uv' (PEP 723 script runner)."
  err "Install with: brew install uv"
  exit 1
fi
log "uv detected: $(command -v uv)"

KS_SKILL_SRC="$ROOT_DIR/knowledge-smith/skill"

if [[ ! -f "$KS_SKILL_SRC/SKILL.md" ]]; then
  err "missing $KS_SKILL_SRC/SKILL.md — repo state corrupt?"
  exit 1
fi

# Symlink the entire skill/ directory into both agent skill homes.
# Single source of truth in bsrc; both agents see identical layout.
ensure_dir "$HOME/.claude/skills"
link_file "$KS_SKILL_SRC" "$HOME/.claude/skills/knowledge-smith"

ensure_dir "${CODEX_HOME:-$HOME/.codex}/skills"
link_file "$KS_SKILL_SRC" "${CODEX_HOME:-$HOME/.codex}/skills/knowledge-smith"

# Make the runner scripts executable so the uv shebang fires.
chmod +x "$KS_SKILL_SRC"/scripts/*.py

log "knowledge-smith skill linked into ~/.claude and ~/.codex."
log "To create a new vault anywhere:"
log "  uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py --init <path>"
log "First docling run will pull ~hundreds of MB of layout/OCR models."
