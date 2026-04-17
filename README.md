# bsrc

Personal macOS dotfiles and CLI/editor setup.

`bsrc` is the single source of truth for the configs that are still worth keeping:

- `fonts`
- `zsh`
- `ghostty`
- `tmux`
- `git`
- `nvim`
- `btop`
- `yazi`
- `codex`
- `claude`
- `feynman`

Explicitly excluded from this repo:

- VPN and Dropbox scripts
- GNOME and Linux-specific desktop config
- SSH/VM helper scripts
- Keyboard remaps
- Old Vim config
- Machine-specific one-off setup

## Structure

Each component owns:

- its config files
- an `install.sh` that links or installs those files

The repo root owns:

- `setup.sh` as the single entrypoint
- `lib/common.sh` for shared installer helpers

## Usage

```bash
cd ~/Developer/bsrc
./setup.sh
```

The setup script is idempotent. It updates symlinks, creates missing config
directories, and replaces managed paths so the repo stays the source of truth.

## Zsh

The Zsh config is intentionally small and portable. It currently provides:

- explicit `oh-my-zsh` installation and configuration
- the `git` plugin from `oh-my-zsh`
- Homebrew initialization from `zprofile`
- XDG, Go, and npm user-level paths
- optional `mise` activation
- a repo-owned `robbyrussell`-style theme with adaptive Monokai light/dark colors and active Python virtualenv display
- `y()` to enter `yazi` and `cd` into the chosen directory on exit
- Zsh-native completion for local `make` targets

Current shell aliases:

- `vim='nvim'`
- `vi='nvim'`
- `src='source ~/.zshrc'`
- `ls='ls -G'`
- `ll='ls -lh'`
- `la='ls -A'`
- `l='ls -CF'`
- `g='git'`
- `ga='git add .'`
- `ck='git switch'`
- `cm='git-commit-all'`
- `gd='git diff'`
- `gs='git status -sb'`
- `st='git status && git diff --stat'`
- `pl='git pull'`
- `ph='git push --force-with-lease'`
- `fh='git fetch'`
- `br='git log --graph --oneline --decorate --all'`
- `lg='lazygit'`

The intent is to keep only high-signal aliases in the base setup. Tool-specific
or workflow-specific shortcuts should be added deliberately.

`oh-my-zsh` is installed into `~/.oh-my-zsh` by the Zsh installer, and the
prompt is provided by the repo-owned theme at
[bsrc.zsh-theme](/Users/blazstojanovic/Developer/bsrc/zsh/custom/themes/bsrc.zsh-theme).

## Fonts

The font setup installs a Nerd Font for terminal tooling that uses glyphs in
tmux, Neovim, and related CLIs.

The current default is:

- `Hack Nerd Font`

Ghostty is configured to use:

- `Hack Nerd Font Mono Bsrc`

## Ghostty

The Ghostty config is macOS-specific and intentionally minimal. It currently
manages:

- the main config file
- custom Monokai light/dark theme files
- automatic light/dark theme switching
- explicit Nerd Font selection
- shell integration for local and SSH sessions

The theme pair is:

- `monokai-custom` for dark mode
- `monokai-custom-light` for light mode

## Tmux

The tmux setup keeps the stronger interactive pieces of this environment:

- process-aware window labels
- git-aware status badges
- SSH host display in the status line
- mouse support and clickable status bar actions
- pane navigation and resize bindings around `hjkl`
- a built-in tmux help popup

Run the tmux help script directly with:

```bash
~/.local/bin/tmux-help
```

Or inside tmux with `prefix + ?`.

The tmux helper scripts are documented in
[tmux/README.md](/Users/blazstojanovic/Developer/bsrc/tmux/README.md).

## btop

The `btop` component installs the `btop` binary via Homebrew and links the
config from [btop/btop.conf](/Users/blazstojanovic/Developer/bsrc/btop/btop.conf).
It also installs a custom Monokai-aligned theme so `btop` matches Ghostty,
tmux, and Neovim more closely.

## Git

Git setup is split between:

- [gitconfig](/Users/blazstojanovic/Developer/bsrc/git/gitconfig) for actual Git defaults
- the shell aliases in [zshrc](/Users/blazstojanovic/Developer/bsrc/zsh/zshrc) for command shortcuts
- [git-commit-all](/Users/blazstojanovic/Developer/bsrc/git/git-commit-all) for generated commit messages

The managed Git defaults currently include:

- `nvim` as the editor
- `push.default = current`
- `pull.rebase = true`
- `init.defaultBranch = main`
- `rerere.enabled = true`
- `fetch.prune = true`

The `git-commit-all` helper is installed into `~/.local/bin` and available as
the `cm` shell alias.

## Neovim

Neovim is now managed directly from
[nvim](/Users/blazstojanovic/Developer/bsrc/nvim) and uses:

- `lazy.nvim` instead of `packer`
- built-in LSP configuration
- a Monokai-aligned theme
- an in-editor help popup via `:BsrcHelp` or `<leader>?`
- LSP support for Lua, Python, C/C++, Go, Rust, and TypeScript

Neovim-specific documentation lives in
[nvim/README.md](/Users/blazstojanovic/Developer/bsrc/nvim/README.md).

## Feynman

The Feynman component installs the shared skills bundle for both agent homes:

- `~/.codex/skills/feynman`
- `~/.claude/skills/<skill-name>`

It uses the official installer. Codex receives the Feynman bundle in a grouped
directory, while Claude receives flattened skill directories because Claude
discovers skills at `~/.claude/skills/<skill-name>/SKILL.md`:

```bash
curl -fsSL https://feynman.is/install-skills | bash
```

## Current Direction

- macOS-only
- Zsh-first
- Neovim-first
- automatic symlink-based setup
- intentionally narrow scope

Some tool-level choices are intentionally left for follow-up discussion:

- final `zsh` alias/function set
- Neovim plugin choices and defaults
- what, if anything, should be managed under `~/.claude`
