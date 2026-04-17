#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

INSTALL_URL="https://feynman.is/install-skills"

if ! command -v curl >/dev/null 2>&1; then
  err "curl is required to install Feynman skills."
  exit 1
fi

install_feynman_skills_to_dir() {
  local agent="$1"
  local target_dir="$2"

  log "Installing Feynman skills for ${agent}: ${target_dir}"
  curl -fsSL "$INSTALL_URL" | bash -s -- --dir "$target_dir"
}

install_feynman_skills_for_claude() {
  local skills_root="$HOME/.claude/skills"
  local staging_dir
  local skill_dir
  local skill_name

  staging_dir="$(mktemp -d)"

  install_feynman_skills_to_dir "Claude staging" "$staging_dir"

  ensure_dir "$skills_root"

  # Claude discovers skills at ~/.claude/skills/<skill>/SKILL.md.
  for skill_dir in "$staging_dir"/*; do
    [[ -d "$skill_dir" && -f "$skill_dir/SKILL.md" ]] || continue

    skill_name="$(basename "$skill_dir")"
    rm -rf "$skills_root/$skill_name"
    cp -R "$skill_dir" "$skills_root/$skill_name"
    log "Installed Feynman skill for Claude: $skill_name"
  done

  if [[ -d "$skills_root/feynman" && ! -f "$skills_root/feynman/SKILL.md" ]]; then
    rm -rf "$skills_root/feynman"
    log "Removed legacy nested Claude Feynman skills directory"
  fi

  rm -rf "$staging_dir"
}

install_feynman_skills_to_dir "Codex" "${CODEX_HOME:-$HOME/.codex}/skills/feynman"
install_feynman_skills_for_claude
