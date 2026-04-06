# tmux in bsrc

This tmux setup is intentionally richer than some of the other components.

## Included behavior

- process-aware window labels via `tmux-pane-label`
- Git-aware status output via `tmux-git-badge`
- SSH host detection via `tmux-ssh-host`
- clickable status bar actions
- `hjkl` pane movement
- `Ctrl-hjkl` pane resizing
- `Shift-Left` and `Shift-Right` for window switching
- reload binding
- built-in help popup
- a Monokai-aligned status palette to match Ghostty and Neovim

## Keybindings

- `prefix + c`: new window in current directory
- `prefix + s`: split pane vertically
- `prefix + v`: split pane horizontally
- `prefix + h/j/k/l`: move between panes
- `prefix + Ctrl-h/j/k/l`: resize panes
- `Shift-Left` / `Shift-Right`: previous / next window
- `prefix + r`: reload tmux config
- `prefix + ?`: open the tmux help popup

## Helper scripts

These are linked into `~/.local/bin` by the tmux installer:

- `tmux-pane-label`
- `tmux-git-badge`
- `tmux-ssh-host`
- `tmux-help`

### `tmux-pane-label`

Infers a useful window label from the active pane process and current path.

By default, tab labels are rendered as plain text. The helper still detects the
pane type internally, but it strips Nerd Font icon prefixes from the final tab
label unless you opt back in with:

```bash
TMUX_LABEL_ICONS=1
```

Examples:

- `nvim` or `vim` panes are labeled with the current file or directory context
- `yazi` panes are labeled as file-manager contexts
- `git`, `lazygit`, `docker`, `kubectl`, `terraform`, `node`, `python`, and
  other tool families get process-aware labels
- agent CLIs get per-tool icons from custom private-use glyphs:
  `codex` / OpenAI, `claude` / Anthropic, `opencode`, and `pool`
- SSH panes are labeled with the remote host

You can override those four agent glyphs with:

```bash
TMUX_ICON_CODEX="..."
TMUX_ICON_CLAUDE="..."
TMUX_ICON_OPENCODE="..."
TMUX_ICON_POOL="..."
```

This is what drives the window text shown in the tmux tab bar.

### `tmux-git-badge`

Builds the Git portion of the tmux status line for the current pane path.

It shows:

- current branch, tag, or revision
- ahead and behind counts relative to upstream
- repository name
- clean marker when the worktree is clean
- total inserted and deleted lines across staged and unstaged changes

It also uses a small cache so tmux can refresh often without rerunning the full
Git logic on every paint.

### `tmux-ssh-host`

Detects whether the active pane is running `ssh` or `mosh-client`, extracts the
target host from the foreground command, and prints the SSH badge shown in the
right side of the status line.

Like the Git badge helper, it caches recent results to keep status updates fast.

### `tmux-help`

Prints a concise reference for the tmux bindings and status-line behavior in
this setup. It is meant to be used either directly from the shell or via the
`prefix + ?` tmux popup binding.
