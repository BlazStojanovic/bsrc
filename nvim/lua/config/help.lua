local help_lines = {
  "bsrc Neovim Help",
  "================",
  "",
  "Open / Close",
  ":BsrcHelp",
  "<leader>?",
  "q",
  "<Esc>",
  "",
  "Leader",
  "<leader> = <Space>",
  "",
  "Files / Tree",
  "<leader>w",
  "<leader>q",
  "<leader>e",
  "<C-w>h",
  "<C-w>j",
  "<C-w>k",
  "<C-w>l",
  "",
  "Buffers",
  "<leader>n",
  "<leader>p",
  "<leader>x",
  "<leader>ml",
  "<leader>fb",
  "",
  "Search",
  "<leader>ff",
  "<leader>fg",
  "<leader>fb",
  "<leader>fh",
  "n",
  "N",
  "<C-d>",
  "<C-u>",
  "",
  "Code",
  "gd",
  "gD",
  "gr",
  "K",
  "<leader>rn",
  "<leader>ca",
  "",
  "Git / History / Sessions",
  "<leader>gs",
  "<leader>u",
  ":AutoSession save",
  ":AutoSession restore",
  ":AutoSession delete",
  "",
  "Edit",
  "<leader>y",
  "<leader>Y",
  "<leader>d",
  "<leader>p",
  "<leader>/",
  "J",
  "K",
  "<C-c>",
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
