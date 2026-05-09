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

# Ensure brew (we rely on it for the system deps below).
bootstrap_homebrew_shellenv
if ! have_cmd brew; then
  err "knowledge-smith requires Homebrew for system deps."
  err "Install: https://brew.sh"
  exit 1
fi

# System CLIs the agent relies on for the LLM-native ingest pipeline.
# Each is opt-in at runtime: only the path the agent picks fires the cost.
brew_install() {
  local pkg="$1"
  if brew list --formula "$pkg" >/dev/null 2>&1; then
    log "brew package present: $pkg"
  else
    log "Installing brew package: $pkg"
    brew install "$pkg"
  fi
}

brew_install poppler        # pdftotext for tier-2 PDF body extraction
brew_install ffmpeg         # audio re-sampling for whisper-cpp
brew_install whisper-cpp    # local YouTube transcription
brew_install yt-dlp         # YouTube metadata + audio download

# Whisper base.en model (~150 MB) — small enough to be ergonomic, plenty
# good for podcast-style audio.
WHISPER_DIR="$HOME/.cache/whisper"
WHISPER_MODEL="$WHISPER_DIR/ggml-base.en.bin"
ensure_dir "$WHISPER_DIR"
if [[ -f "$WHISPER_MODEL" ]]; then
  log "Whisper model present: $WHISPER_MODEL"
else
  log "Downloading Whisper base.en model -> $WHISPER_MODEL"
  curl -L --fail --progress-bar \
    -o "$WHISPER_MODEL" \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
fi

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

# Make the runner scripts (and helper shell scripts) executable so the
# uv shebang fires.
chmod +x "$KS_SKILL_SRC"/scripts/*.py
if [[ -d "$KS_SKILL_SRC/scripts/helpers" ]]; then
  chmod +x "$KS_SKILL_SRC"/scripts/helpers/*
fi

log "knowledge-smith skill linked into ~/.claude and ~/.codex."
log "To create a new vault anywhere:"
log "  uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py --init <path>"
log "Tier-3 PDF parsing (--docling) downloads layout/OCR models on first use."
