# fonts in bsrc

This component installs the terminal font needed for glyph-heavy tooling.

## Current default

- `Hack Nerd Font`

## Why this exists

Several tools in this setup use Nerd Font glyphs:

- tmux tab labels and status line
- Neovim UI elements from plugins
- terminal-oriented CLIs that use icon glyphs

If the Nerd Font is missing, those glyphs can render as raw codepoints or empty
boxes instead of icons.

## Installer

The installer uses Homebrew casks on macOS to install the configured Nerd Font.

You can override the family with:

```bash
NERD_FONT_NAME=Hack ./fonts/install.sh
```

Ghostty is configured separately to use `Hack Nerd Font Mono`.
