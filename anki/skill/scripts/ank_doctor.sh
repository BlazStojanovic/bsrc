#!/usr/bin/env bash
# Health check for the bsrc anki integration. Reports each component
# with [+] / [×] markers. Exit 0 on all-green, 1 if anything is missing.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ank_common.sh
source "$SCRIPT_DIR/ank_common.sh"

red=0

check() {
  local label="$1"
  local ok="$2"
  local detail="${3:-}"

  if [[ "$ok" == "1" ]]; then
    ank_log "$label${detail:+: $detail}"
  else
    ank_err "$label${detail:+: $detail}"
    red=1
  fi
}

ank_log "bsrc anki doctor"
echo

# 1. Anki app installed.
if [[ -d "/Applications/Anki.app" ]]; then
  check "Anki desktop installed" 1 "/Applications/Anki.app"
else
  check "Anki desktop installed" 0 "/Applications/Anki.app missing"
fi

# 2. Cards dir resolves.
if cards_dir="$(ank_resolve_cards_dir 2>/dev/null)"; then
  check "cards dir resolves" 1 "$cards_dir"

  # 3. Marker present.
  if [[ -f "$cards_dir/$ANK_VAULT_MARKER" ]]; then
    check "marker present" 1 "$cards_dir/$ANK_VAULT_MARKER"
  else
    check "marker present" 0 "no $ANK_VAULT_MARKER yet — touch it in $cards_dir"
  fi

  # 4. Cards dir is a git repo with origin remote.
  if [[ -d "$cards_dir/.git" ]]; then
    if remote="$(git -C "$cards_dir" remote get-url origin 2>/dev/null)"; then
      check "cards repo has origin" 1 "$remote"
    else
      check "cards repo has origin" 0 "no 'origin' remote"
    fi
  else
    check "cards dir is a git repo" 0 "$cards_dir is not a git repo"
  fi
else
  check "cards dir resolves" 0 "set ANKI_CARDS_DIR or run bsrc/anki/install.sh"
fi

# 5. Anki MCP reachable (also serves as "Anki running" check).
if ank_mcp_reachable; then
  check "Anki MCP reachable" 1 "$ANK_MCP_URL"
else
  check "Anki MCP reachable" 0 "$ANK_MCP_URL — open Anki, install addon 124672614, restart"
fi

echo
if [[ "$red" == "0" ]]; then
  ank_log "all checks passed"
  exit 0
else
  ank_err "some checks failed"
  exit 1
fi
