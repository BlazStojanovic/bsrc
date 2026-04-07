#!/usr/bin/env bash
# Claude Code statusLine script

input=$(cat)

RESET='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
FG_CYAN='\033[36m'
FG_YELLOW='\033[33m'
FG_GREEN='\033[32m'
FG_RED='\033[31m'
FG_BLUE='\033[34m'
FG_MAGENTA='\033[35m'
FG_WHITE='\033[97m'

SEP=" ${DIM}│${RESET} "

# Model
model=$(echo "$input" | jq -r '.model.display_name // .model.id // "unknown"')

# Worktree / branch
worktree_name=$(echo "$input" | jq -r '.worktree.name // empty')
worktree_branch=$(echo "$input" | jq -r '.worktree.branch // empty')
orig_branch=$(echo "$input" | jq -r '.worktree.original_branch // empty')
raw_cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')

git_branch=""
if [ -n "$raw_cwd" ]; then
  git_branch=$(git -C "$raw_cwd" symbolic-ref --short HEAD 2>/dev/null || true)
fi

# Context window used percentage
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Rate limits
five_hr=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
seven_day=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

# Lines added/removed (session total)
lines_added=$(echo "$input" | jq -r '.cost.total_lines_added // empty')
lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed // empty')

# --- Build output ---
out=""

# 1. Model
out+="${FG_MAGENTA}${BOLD}◆${RESET} ${FG_WHITE}${model}${RESET}"

# 2. Branch / worktree
if [ -n "$worktree_name" ]; then
  branch_display="${worktree_name}"
  [ -n "$orig_branch" ] && branch_display+=" ${DIM}(${orig_branch})${RESET}"
  out+="${SEP}${FG_CYAN}${BOLD}⎇ ${branch_display}${RESET}"
elif [ -n "$git_branch" ]; then
  out+="${SEP}${DIM}⎇${RESET} ${git_branch}"
fi

# 3. Context window
if [ -n "$used_pct" ]; then
  pct_int=$(printf '%.0f' "$used_pct")
  if [ "$pct_int" -ge 80 ]; then
    ctx_color="${FG_RED}"
  elif [ "$pct_int" -ge 50 ]; then
    ctx_color="${FG_YELLOW}"
  else
    ctx_color="${FG_GREEN}"
  fi
  out+="${SEP}${DIM}ctx${RESET} ${ctx_color}${pct_int}%${RESET}"
fi

# 4. Rate limits (5h / 7d)
rate_parts=""
if [ -n "$five_hr" ]; then
  fh_int=$(printf '%.0f' "$five_hr")
  if [ "$fh_int" -ge 80 ]; then rc="${FG_RED}"; elif [ "$fh_int" -ge 50 ]; then rc="${FG_YELLOW}"; else rc="${FG_GREEN}"; fi
  rate_parts+="${DIM}5h${RESET} ${rc}${fh_int}%${RESET}"
fi
if [ -n "$seven_day" ]; then
  sd_int=$(printf '%.0f' "$seven_day")
  if [ "$sd_int" -ge 80 ]; then rc="${FG_RED}"; elif [ "$sd_int" -ge 50 ]; then rc="${FG_YELLOW}"; else rc="${FG_GREEN}"; fi
  [ -n "$rate_parts" ] && rate_parts+=" ${DIM}·${RESET} "
  rate_parts+="${DIM}7d${RESET} ${rc}${sd_int}%${RESET}"
fi
[ -n "$rate_parts" ] && out+="${SEP}${rate_parts}"

# 5. Lines added / removed
if [ -n "$lines_added" ] || [ -n "$lines_removed" ]; then
  out+="${SEP}${FG_GREEN}+${lines_added:-0}${RESET} ${FG_RED}-${lines_removed:-0}${RESET}"
fi

printf "%b" "$out"
