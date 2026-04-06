# nvim in bsrc

This is the Neovim configuration managed by `bsrc`.

## Current direction

- `lazy.nvim` for plugin management
- built-in Neovim LSP support
- Monokai-aligned theme to match Ghostty and tmux
- a small set of high-signal editing plugins
- in-editor help via `:BsrcHelp` or `<leader>?`

## Current plugins

- `tanvirtin/monokai.nvim`
- `nvim-telescope/telescope.nvim`
- `nvim-treesitter/nvim-treesitter`
- `nvim-tree/nvim-tree.lua`
- `akinsho/bufferline.nvim`
- `mbbill/undotree`
- `tpope/vim-fugitive`
- `numToStr/Comment.nvim`
- `rmagatti/auto-session`
- `neovim/nvim-lspconfig`

## Current LSP setup

Enabled servers:

- `lua_ls`
- `pyright`
- `clangd`
- `ruff`
- `gopls`
- `rust_analyzer`
- `ts_ls`

## Current Treesitter setup

Installed grammars:

- `lua`
- `vim`
- `vimdoc`
- `bash`
- `markdown`
- `python`
- `javascript`
- `typescript`
- `tsx`
- `go`
- `rust`

This list now reflects the languages you said you actively use.

## Help

Use either of these inside Neovim:

- `:BsrcHelp`
- `<leader>?`

The popup includes the current keymaps, plugin entrypoints, and a few notes
about the setup. It is meant to be a real quick-reference, not just a reminder.

## LSP navigation

The most important LSP navigation bindings are:

- `gd` for go to definition
- `gD` for go to declaration
- `gr` for references
- `K` for hover documentation

## Installer

The Neovim installer is [install.sh](/Users/blazstojanovic/Developer/bsrc/nvim/install.sh).
It currently does four things:

- links this config to `~/.config/nvim`
- creates Neovim state/cache directories
- installs core CLI dependencies via Homebrew
- installs LSP dependencies via `npm` and `go` when those tools are available

Current Homebrew packages:

- `neovim`
- `ripgrep`
- `fd`
- `go`
- `tree-sitter`
- `lua-language-server`
- `ruff`
- `rust-analyzer`

Current npm packages:

- `pyright`
- `typescript`
- `typescript-language-server`

Current Go tools:

- `gopls`

`clangd` is checked separately. On macOS it often comes from Xcode Command Line
Tools or a separate LLVM install.

After running the installer, the first Neovim launch will bootstrap
`lazy.nvim` and install the configured plugins.
