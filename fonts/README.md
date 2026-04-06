# fonts in bsrc

This component installs the terminal font needed for glyph-heavy tooling.

## Current default

- `Hack Nerd Font`
- patched local variant: `Hack Nerd Font Mono Bsrc`

## Why this exists

Several tools in this setup use Nerd Font glyphs:

- tmux tab labels and status line
- Neovim UI elements from plugins
- terminal-oriented CLIs that use icon glyphs

If the Nerd Font is missing, those glyphs can render as raw codepoints or empty
boxes instead of icons.

## Installer

The installer uses Homebrew casks on macOS to install the configured Nerd Font
and installs `fontforge` so it can build the patched `Hack Nerd Font Mono Bsrc`
variant locally.

You can override the family with:

```bash
NERD_FONT_NAME=Hack ./fonts/install.sh
```

Ghostty is configured separately to use `Hack Nerd Font Mono`.

## Custom agent glyphs

This repo can build a patched mono font variant named `Hack Nerd Font Mono Bsrc`
that embeds private-use glyphs generated from:

- `assets/openai.svg`
- `assets/anthropic.svg`
- `assets/opencode.svg`
- `assets/poolside.svg`

Those glyphs are used by tmux pane labels for `codex`, `claude`, `opencode`,
and `pool`/`poolside`.

Codepoints:

- `U+E00B`: OpenAI / Codex
- `U+E00C`: Anthropic / Claude Code
- `U+E00D`: OpenCode
- `U+E00E`: Poolside / pool

`./fonts/install.sh` builds the patched font files into `~/Library/Fonts`.
