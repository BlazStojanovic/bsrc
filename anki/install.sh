#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

# -----------------------------------------------------------------------------
# Tunables.
# -----------------------------------------------------------------------------
# Remote URL of the GitHub repo holding your Anki cards markdown. bsrc
# clones it on each device when the cards dir is missing. Override
# per-machine by exporting CARDS_REPO_URL=... before running install.
# Set to an empty string to disable the auto-clone path.
CARDS_REPO_URL="${CARDS_REPO_URL:-git@github.com:BlazStojanovic/anki-cards.git}"

# Default local location for the cards repo.
CARDS_DIR_DEFAULT="${CARDS_DIR_DEFAULT:-$HOME/Developer/personalprojects/anki-cards}"

# Anki MCP Server addon code. Manual install via Anki UI.
ANKI_MCP_ADDON_CODE="124672614"

# Default localhost URL for the Anki MCP addon. The addon listens on
# 127.0.0.1:3141 by default; configurable via Anki Tools → Add-ons →
# AnkiMCP Server → Config (http_host / http_port / http_path).
ANKI_MCP_URL_DEFAULT="${ANKI_MCP_URL:-http://127.0.0.1:3141/}"

with_mcps="${BSRC_WITH_MCPS:-0}"
cards_dir=""

usage() {
  cat <<'EOF'
Usage: ./anki/install.sh [--with-mcps] [--cards-dir <path>]

Options:
  --with-mcps         Also wire the Anki MCP entry for Claude Code (the
                      Codex MCP fragment is composed from
                      bsrc/codex/mcp-servers.toml on its own install).
  --cards-dir <path>  Where the cards git repo lives. Defaults to
                      $HOME/Developer/personalprojects/anki-cards.
                      Persisted to ~/.config/bsrc/anki.env.

Environment overrides:
  CARDS_REPO_URL      git URL to clone if the cards dir is missing.
  CARDS_DIR_DEFAULT   override the default install path.
  ANKI_MCP_URL        override the localhost URL wired into MCP configs.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-mcps)
      with_mcps=1
      ;;
    --cards-dir)
      shift
      cards_dir="${1:-}"
      if [[ -z "$cards_dir" ]]; then
        err "--cards-dir requires a path argument"
        exit 1
      fi
      ;;
    --cards-dir=*)
      cards_dir="${1#--cards-dir=}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

if [[ -z "$cards_dir" ]]; then
  cards_dir="$CARDS_DIR_DEFAULT"
fi
cards_dir="${cards_dir/#\~/$HOME}"

# -----------------------------------------------------------------------------
# Step 1 — Anki desktop via Homebrew cask.
# -----------------------------------------------------------------------------
install_anki_app() {
  if [[ -d "/Applications/Anki.app" ]]; then
    log "Anki.app already installed"
    return 0
  fi

  bootstrap_homebrew_shellenv

  if ! have_cmd brew; then
    err "Homebrew not found; install brew first or install Anki manually"
    return 1
  fi

  log "Installing Anki via Homebrew cask"
  brew install --cask anki
}

# -----------------------------------------------------------------------------
# Step 2 — Cards repo bootstrap.
# -----------------------------------------------------------------------------
bootstrap_cards_dir() {
  ensure_dir "$(dirname "$cards_dir")"

  if [[ -d "$cards_dir/.git" ]]; then
    log "Cards repo already present: $cards_dir"
    return 0
  fi

  if [[ -e "$cards_dir" ]] && [[ -n "$(ls -A "$cards_dir" 2>/dev/null)" ]]; then
    err "Cards dir exists and is non-empty but not a git repo: $cards_dir"
    err "Move or remove it, or pass --cards-dir <other-path>."
    return 1
  fi

  if [[ -z "$CARDS_REPO_URL" ]]; then
    warn "CARDS_REPO_URL is not set. Skipping clone."
    warn "Create the GitHub repo, then re-run with CARDS_REPO_URL=...,"
    warn "or initialize $cards_dir manually."
    ensure_dir "$cards_dir"
    return 0
  fi

  log "Cloning cards repo: ${CARDS_REPO_URL} -> ${cards_dir}"
  git clone "$CARDS_REPO_URL" "$cards_dir"
}

# -----------------------------------------------------------------------------
# Step 3 — Persist resolved cards dir for the skill scripts.
# -----------------------------------------------------------------------------
persist_cards_dir() {
  local env_file="$HOME/.config/bsrc/anki.env"
  ensure_dir "$(dirname "$env_file")"

  local desired_line
  desired_line="ANKI_CARDS_DIR=${cards_dir}"

  if [[ -f "$env_file" ]] && grep -qxF "$desired_line" "$env_file"; then
    log "Cards dir env already correct: ${env_file}"
    return 0
  fi

  if [[ -f "$env_file" ]]; then
    local tmp
    tmp="$(mktemp)"
    grep -v '^ANKI_CARDS_DIR=' "$env_file" > "$tmp" || true
    printf '%s\n' "$desired_line" >> "$tmp"
    mv "$tmp" "$env_file"
  else
    printf '%s\n' "$desired_line" > "$env_file"
  fi
  log "Wrote ${env_file}"
}

# -----------------------------------------------------------------------------
# Step 4 — Skill symlinks (mirrors knowledge-smith).
# -----------------------------------------------------------------------------
link_skill() {
  local src="$ROOT_DIR/anki/skill"

  if [[ ! -f "$src/SKILL.md" ]]; then
    err "missing $src/SKILL.md — repo state corrupt?"
    return 1
  fi

  ensure_dir "$HOME/.claude/skills"
  link_file "$src" "$HOME/.claude/skills/anki"

  ensure_dir "${CODEX_HOME:-$HOME/.codex}/skills"
  link_file "$src" "${CODEX_HOME:-$HOME/.codex}/skills/anki"

  chmod +x "$src"/scripts/*.sh "$src"/scripts/*.py 2>/dev/null || true
}

# -----------------------------------------------------------------------------
# Step 5 — MCP wiring (gated on --with-mcps).
# -----------------------------------------------------------------------------
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

wire_mcps() {
  if [[ "$with_mcps" != "1" ]]; then
    log "Skipping MCP wiring (run with --with-mcps to enable)"
    return 0
  fi

  if have_cmd claude; then
    add_claude_mcp anki --transport http anki "$ANKI_MCP_URL_DEFAULT"
  else
    warn "'claude' CLI not on PATH; skipping Claude MCP wire-up for anki"
  fi

  if have_cmd codex; then
    log "Codex anki MCP entry will be picked up on next codex/install.sh"
  fi
}

# -----------------------------------------------------------------------------
# Step 6 — Final checklist.
# -----------------------------------------------------------------------------
print_checklist() {
  cat <<EOF

[+] anki component installed.

One-time per-device setup (manual):

  1. Open Anki. Tools → Add-ons → Get Add-ons → enter ${ANKI_MCP_ADDON_CODE}
     (Anki MCP Server). Restart Anki.

  2. Sign in to AnkiWeb inside Anki for cross-device review/state sync.

  3. Verify everything is wired up:
       bash ~/.claude/skills/anki/scripts/ank_doctor.sh

Daily workflow:
  - Author cards via Claude/Codex (uses Anki MCP at ${ANKI_MCP_URL_DEFAULT}).
  - Snapshot to git: bash ~/.claude/skills/anki/scripts/ank_sync.sh --remote
  - AnkiWeb syncs cards + review state to phone/web/other Macs separately.

EOF
}

# -----------------------------------------------------------------------------
# Run.
# -----------------------------------------------------------------------------
require_macos

install_anki_app
bootstrap_cards_dir
persist_cards_dir
link_skill
wire_mcps
print_checklist
