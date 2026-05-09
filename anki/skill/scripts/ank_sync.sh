#!/usr/bin/env bash
# Snapshot the Anki collection to per-deck markdown and commit.
#
# Usage:
#   ank_sync.sh             # dump + commit (no push)
#   ank_sync.sh --remote    # dump + commit + git push
#   ank_sync.sh status      # cards repo git status + MCP reachability
#
# The sync flow is one-way: Anki -> markdown. AnkiWeb handles the
# "Anki on other devices" sync independently (in the Anki app). Editing
# the markdown does not push back to Anki — it would be silently
# overwritten on next dump. Author cards via the agent + MCP, or via
# Anki's UI, never by hand-editing the markdown.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ank_common.sh
source "$SCRIPT_DIR/ank_common.sh"

usage() {
  cat <<'EOF'
Usage: ank_sync.sh [--remote | status]

  (no args)   Run ank_dump.py, stage + commit any changes.
  --remote    Same as above, plus `git push`.
  status      Show git status of the cards repo and MCP reachability.
EOF
}

action="dump"
push_remote=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote) push_remote=1 ;;
    status)   action="status" ;;
    -h|--help) usage; exit 0 ;;
    *) ank_err "unknown arg: $1"; usage; exit 1 ;;
  esac
  shift
done

cards_dir="$(ank_resolve_cards_dir)"

if [[ "$action" == "status" ]]; then
  if [[ -d "$cards_dir/.git" ]]; then
    git -C "$cards_dir" status -sb
  else
    ank_warn "$cards_dir is not a git repo"
  fi
  if ank_mcp_reachable; then
    ank_log "MCP reachable: $ANK_MCP_URL"
  else
    ank_warn "MCP not reachable: $ANK_MCP_URL — open Anki"
  fi
  exit 0
fi

if ! ank_mcp_reachable; then
  ank_err "Anki MCP not reachable at $ANK_MCP_URL."
  ank_err "Open Anki and ensure the Anki MCP Server addon (124672614) is loaded."
  exit 1
fi

ank_log "running ank_dump.py"
"$SCRIPT_DIR/ank_dump.py"

cd "$cards_dir"

if ! [[ -d .git ]]; then
  ank_warn "$cards_dir is not a git repo; skipping commit"
  exit 0
fi

if git diff --quiet && git diff --cached --quiet; then
  ank_log "no changes to commit"
  if [[ "$push_remote" == "1" ]]; then
    ank_log "skipping git push (no changes)"
  fi
  exit 0
fi

git add -A
git commit -m "ank_dump: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
ank_log "committed snapshot"

if [[ "$push_remote" == "1" ]]; then
  git push
  ank_log "pushed to origin"
else
  ank_log "skipping git push (pass --remote to push)"
fi
