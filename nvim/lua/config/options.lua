vim.g.mapleader = " "
vim.g.maplocalleader = " "

for _, dir in ipairs({ "/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin", vim.fn.expand("~/.local/bin") }) do
  if vim.fn.isdirectory(dir) == 1 and not vim.env.PATH:find(dir, 1, true) then
    vim.env.PATH = dir .. ":" .. vim.env.PATH
  end
end

vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.tabstop = 4
vim.opt.shiftwidth = 4
vim.opt.softtabstop = 4
vim.opt.expandtab = true
vim.opt.smartindent = false
vim.opt.wrap = false
vim.opt.swapfile = false
vim.opt.backup = false
vim.opt.undofile = true
vim.opt.undodir = vim.fn.expand("~/.local/state/nvim/undo")
vim.opt.ignorecase = true
vim.opt.smartcase = true
vim.opt.hlsearch = false
vim.opt.incsearch = true
vim.opt.termguicolors = true
vim.opt.signcolumn = "yes"
vim.opt.scrolloff = 8
vim.opt.updatetime = 200
vim.opt.completeopt = { "menu", "menuone", "noselect", "popup" }
vim.opt.clipboard = "unnamedplus"
vim.opt.splitright = true
vim.opt.splitbelow = true
vim.opt.winborder = "rounded"
