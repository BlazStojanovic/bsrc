local help_lines = {
  "bsrc Neovim Help",
  "================",
  "",
  "Open / Close",
  ":BsrcHelp            open this help popup",
  "<leader>?            open this help popup",
  "q                    close the popup",
  "<Esc>                close the popup",
  "",
  "Leader",
  "<leader> = <Space>   leader key",
  "",
  "Files / Tree",
  "<leader>w            write file",
  "<leader>q            quit window",
  "<leader>e            focus or toggle file tree",
  "<C-w>>               expand current split width",
  "<C-w><               contract current split width",
  ":vertical resize +5  make file tree wider",
  ":vertical resize -5  make file tree narrower",
  "<leader>o            toggle outline",
  "<C-w>h               move to left split",
  "<C-w>j               move to lower split",
  "<C-w>k               move to upper split",
  "<C-w>l               move to right split",
  "",
  "Buffers",
  "<leader>n            next buffer",
  "<leader>p            previous buffer",
  "<leader>x            delete current buffer",
  "<leader>ml           jump to alternate buffer",
  "<leader>L            move current buffer left in buffer line",
  "<leader>R            move current buffer right in buffer line",
  "<leader>fb           pick an open buffer by name",
  "",
  "Search",
  "<leader>ff           find files",
  "<leader>fg           live grep",
  "<leader>fB           grep across open buffers",
  "<leader>f/           fuzzy find in current buffer",
  "<leader>fh           search help tags",
  "n                    next search result",
  "N                    previous search result",
  "<C-d>                half-page down and recenter",
  "<C-u>                half-page up and recenter",
  "",
  "Code",
  "gd                   go to definition",
  "gD                   go to declaration",
  "gr                   list references",
  "gi                   go to implementation",
  "gy                   go to type definition",
  "K                    hover documentation",
  "<C-k>                signature help",
  "<leader>rn           rename symbol",
  "<leader>ca           code action",
  "<leader>ds           document symbols",
  "<leader>ws           workspace symbols",
  "<leader>uh           toggle inlay hints",
  "[d                   previous diagnostic",
  "]d                   next diagnostic",
  "<leader>vd           line diagnostics",
  "",
  "Git / History / Sessions",
  "<leader>gs           open Fugitive status",
  "<leader>u            toggle undotree",
  "<leader>xx           diagnostics list",
  "<leader>xr           references list",
  "<leader>xs           symbols list",
  ":AutoSession save    save current session",
  ":AutoSession restore restore current session",
  ":AutoSession delete  delete current session",
  "",
  "Edit",
  "<leader>y            yank to system clipboard",
  "<leader>Y            yank line to system clipboard",
  "<leader>d            delete without yanking",
  "<leader>p            paste over selection without yanking it",
  "<leader>/            toggle comment",
  "J                    join lines or move selection down",
  "K                    move selection up",
  "<Tab>                next completion or snippet jump",
  "<S-Tab>              previous completion or snippet jump",
  "<C-Space>            trigger completion",
  "<CR>                 confirm completion",
  "<C-c>                leave insert mode",
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
