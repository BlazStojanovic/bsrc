local help_lines = {
  "bsrc Neovim Help",
  "================",
  "",
  "How to open this help",
  "- :BsrcHelp",
  "- <leader>?",
  "- q or <Esc> closes the popup",
  "",
  "Leader",
  "- <leader> is <Space>",
  "",
  "General",
  "- <leader>? open this help popup",
  "- <leader>w write file",
  "- <leader>q quit window",
  "- <leader>e toggle file tree",
  "- <leader>gs open Fugitive",
  "- <leader>u toggle undotree",
  "",
  "Navigation",
  "- j / k / h / l normal Vim movement",
  "- <C-d> / <C-u> half-page jump and recenter",
  "- n / N next search result and recenter",
  "- gd go to definition",
  "- gD go to declaration",
  "- gr list references",
  "- K hover documentation",
  "- <leader>rn rename symbol",
  "- <leader>ca code action",
  "",
  "Buffers",
  "- Bufferline is enabled",
  "- <leader>n next buffer",
  "- <leader>p previous buffer",
  "- <leader>x delete current buffer",
  "- <leader>ml jump to alternate buffer",
  "- <leader>fb open Telescope buffer picker",
  "",
  "Editing",
  "- <leader>y yank to system clipboard",
  "- <leader>d delete without yanking",
  "- <leader>p paste over selection without yanking it",
  "- <leader>/ toggle comment",
  "- J in visual mode moves selected lines down",
  "- K in visual mode moves selected lines up",
  "- J in normal mode joins lines without losing cursor context",
  "- <C-c> in insert mode acts like <Esc>",
  "",
  "Search",
  "- <leader>ff find files",
  "- <leader>fg live grep",
  "- <leader>fb buffers",
  "- <leader>fh help tags",
  "",
  "File tree",
  "- <leader>e toggles NvimTree focused on the current file",
  "",
  "Git",
  "- <leader>gs opens Fugitive status",
  "- tmux status also shows Git state when relevant",
  "",
  "Sessions",
  "- Auto Session is enabled",
  "- sessions restore automatically for working directories",
  "- this is intended to make project resumes automatic rather than manual",
  "",
  "Languages",
  "- LSPs enabled: lua_ls, pyright, ruff, clangd, gopls, rust_analyzer, ts_ls",
  "- Treesitter grammars: lua, vim, vimdoc, bash, markdown, python, javascript, typescript, tsx, go, rust",
  "- definition and declaration navigation are first-class shortcuts in this setup",
  "",
  "Theme",
  "- Neovim uses a Monokai-aligned theme",
  "- Ghostty and tmux are intended to match the same visual direction",
  "",
  "Notes",
  "- Bufferline is kept for now",
  "- if something feels off, test :checkhealth and report the concrete failure",
}

local function open_help_popup()
  local width = math.floor(vim.o.columns * 0.72)
  local height = math.floor(vim.o.lines * 0.72)
  local row = math.floor((vim.o.lines - height) / 2)
  local col = math.floor((vim.o.columns - width) / 2)

  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, help_lines)
  vim.bo[buf].bufhidden = "wipe"
  vim.bo[buf].filetype = "markdown"
  vim.bo[buf].modifiable = false

  local win = vim.api.nvim_open_win(buf, true, {
    relative = "editor",
    width = width,
    height = height,
    row = row,
    col = col,
    style = "minimal",
    border = "rounded",
    title = " bsrc help ",
    title_pos = "center",
  })
  vim.wo[win].wrap = false

  vim.keymap.set("n", "q", "<cmd>close<cr>", { buffer = buf, silent = true })
  vim.keymap.set("n", "<Esc>", "<cmd>close<cr>", { buffer = buf, silent = true })
end

vim.api.nvim_create_user_command("BsrcHelp", open_help_popup, {})
