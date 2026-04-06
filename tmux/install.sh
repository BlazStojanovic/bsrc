#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT_DIR/lib/common.sh"

link_file "$ROOT_DIR/tmux/tmux.conf" "$HOME/.tmux.conf"
link_file "$ROOT_DIR/tmux/tmux-pane-label" "$HOME/.local/bin/tmux-pane-label"
link_file "$ROOT_DIR/tmux/tmux-git-badge" "$HOME/.local/bin/tmux-git-badge"
link_file "$ROOT_DIR/tmux/tmux-ssh-host" "$HOME/.local/bin/tmux-ssh-host"
link_file "$ROOT_DIR/tmux/tmux-help" "$HOME/.local/bin/tmux-help"
link_file "$ROOT_DIR/tmux/tmux-apply-theme" "$HOME/.local/bin/tmux-apply-theme"
