#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

# Upstream agent-skills bundle from kepano. We clone it into a cache dir
# and symlink each individual skill into both agent homes — same pattern
# bsrc uses for the local knowledge-smith skill, just sourced from a
# remote repo.
UPSTREAM_REPO="${OBSIDIAN_SKILLS_REPO:-https://github.com/kepano/obsidian-skills.git}"
UPSTREAM_REF="${OBSIDIAN_SKILLS_REF:-main}"
CACHE_DIR="${OBSIDIAN_SKILLS_CACHE:-$HOME/.cache/bsrc/skills/obsidian-skills}"

if ! have_cmd git; then
  err "git is required to install obsidian-skills"
  exit 1
fi

ensure_dir "$(dirname "$CACHE_DIR")"

if [[ -d "$CACHE_DIR/.git" ]]; then
  log "obsidian-skills cache present: $CACHE_DIR"
  git -C "$CACHE_DIR" fetch --quiet origin
  if [[ "$UPSTREAM_REF" == "main" ]]; then
    git -C "$CACHE_DIR" checkout --quiet main
    git -C "$CACHE_DIR" pull --ff-only --quiet origin main
  else
    git -C "$CACHE_DIR" checkout --quiet "$UPSTREAM_REF"
  fi
else
  log "Cloning obsidian-skills: $UPSTREAM_REPO -> $CACHE_DIR"
  git clone --quiet "$UPSTREAM_REPO" "$CACHE_DIR"
  if [[ "$UPSTREAM_REF" != "main" ]]; then
    git -C "$CACHE_DIR" checkout --quiet "$UPSTREAM_REF"
  fi
fi

if [[ ! -d "$CACHE_DIR/skills" ]]; then
  err "obsidian-skills cache has no skills/ directory: $CACHE_DIR"
  err "Upstream layout may have changed."
  exit 1
fi

# Each subdirectory of skills/ is one Agent-Skill bundle (SKILL.md +
# optional references/). Symlink each into Claude and Codex skill homes.
ensure_dir "$HOME/.claude/skills"
ensure_dir "${CODEX_HOME:-$HOME/.codex}/skills"

linked=0
skipped=0
for skill_path in "$CACHE_DIR"/skills/*/; do
  [[ -d "$skill_path" ]] || continue
  skill_path="${skill_path%/}"
  skill_name="$(basename "$skill_path")"

  if [[ ! -f "$skill_path/SKILL.md" ]]; then
    warn "skipping $skill_name: no SKILL.md"
    skipped=$((skipped + 1))
    continue
  fi

  link_file "$skill_path" "$HOME/.claude/skills/$skill_name"
  link_file "$skill_path" "${CODEX_HOME:-$HOME/.codex}/skills/$skill_name"
  linked=$((linked + 1))
done

log "obsidian-skills: ${linked} skills linked into Claude and Codex"
if [[ "$skipped" -gt 0 ]]; then
  warn "obsidian-skills: ${skipped} subdirectories skipped (no SKILL.md)"
fi
