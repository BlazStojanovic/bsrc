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
- `peonping`
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

To also install the managed Claude Code and Codex MCP entries for Notion, Coda,
Linear, and Grafana, use:

```bash
./setup.sh --with-mcps
```

The setup script is idempotent. It updates symlinks, creates missing config
directories, and replaces managed paths so the repo stays the source of truth.

## MCPs

The repo can optionally install four managed MCPs for both Claude Code and
Codex:

- `notion`
- `coda`
- `linear`
- `grafana`

This is opt-in only. The default install path does not add them. You can enable
them from the root installer with `./setup.sh --with-mcps`, or directly via:

```bash
./claude/install.sh --with-mcps
./codex/install.sh --with-mcps
```

Implementation details:

- Claude keeps the normal repo-managed files under `~/.claude`, and the opt-in installer adds missing user-scope MCP entries through the `claude` CLI.
- Codex renders `~/.codex/config.toml` from the base repo config plus the optional fragment at [codex/mcp-servers.toml](/Users/blazstojanovic/Developer/bsrc/codex/mcp-servers.toml).
- The Grafana MCP binary is also installed automatically on the opt-in path. The installer uses Grafana's documented `go install` flow and installs Homebrew `go` first if needed.

Post-install auth and runtime requirements:

- Notion for Codex still needs `codex mcp login notion`.
- Linear for Codex still needs `codex mcp login linear`.
- Notion, Coda, and Linear for Claude still need to be authenticated inside Claude Code via `/mcp`.
- Coda for Codex expects `CODA_MCP_AUTH_TOKEN` in your environment. This uses Codex's native remote MCP support rather than baking a bearer token into the repo config.
- Grafana for both clients expects `GRAFANA_URL` and `GRAFANA_SERVICE_ACCOUNT_TOKEN` in your environment. The installer prints a lightweight readiness summary for these requirements when `--with-mcps` is used.

Official docs:

- Notion: https://developers.notion.com/guides/mcp/get-started-with-mcp
- Coda: https://help.coda.io/hc/en-us/articles/44722661982989-Connect-to-the-Coda-MCP
- Linear: https://linear.app/docs/mcp
- Grafana MCP overview: https://grafana.com/docs/grafana/latest/developer-resources/mcp/
- Grafana binary install: https://grafana.com/docs/grafana/latest/developer-resources/mcp/set-up/install-the-binary/
- Grafana for Claude Code: https://grafana.com/docs/grafana/latest/developer-resources/mcp/clients/claude-code/
- Grafana for Codex: https://grafana.com/docs/grafana/latest/developer-resources/mcp/clients/codex/

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

- Homebrew installation of the Ghostty app
- the main config file
- custom Monokai light/dark theme files
- automatic light/dark theme switching
- explicit Nerd Font selection
- shell integration for local and SSH sessions

The theme pair is:

- `monokai-custom` for dark mode
- `monokai-custom-light` for light mode

The installer writes both `~/.config/ghostty/config.ghostty` and the legacy
`~/.config/ghostty/config` symlink so current and older Ghostty builds read the
same managed config.

## PeonPing

The `peonping` component installs `peon-ping` from the official Homebrew tap
and runs the bundled runtime installer so the shared adapter files exist under
`~/.claude/hooks/peon-ping` for both Claude Code and Codex.

The base managed Codex config also wires `notify` to the `peon-ping` Codex
adapter.

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
- mostly symlink-based setup, with generated config where optional install-time features need composition
- intentionally narrow scope

Some tool-level choices are intentionally left for follow-up discussion:

- final `zsh` alias/function set
- Neovim plugin choices and defaults
- whether more Claude user-level state should be repo-managed beyond the current linked files and optional MCP setup
