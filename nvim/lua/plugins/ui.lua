return {
  {
    "RRethy/base16-nvim",
    lazy = false,
    priority = 1000,
    config = function()
      local theme = require("config.theme")
      theme.apply(true)
      vim.api.nvim_create_autocmd({ "FocusGained", "VimResume" }, {
        callback = function()
          theme.apply(false)
        end,
      })
    end,
  },
  {
    "nvim-tree/nvim-tree.lua",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    keys = {
      {
        "<leader>e",
        function()
          for _, buf in ipairs(vim.api.nvim_list_bufs()) do
            local name = vim.api.nvim_buf_get_name(buf)
            if name:match("NvimTree_%d+$") then
              pcall(vim.api.nvim_buf_delete, buf, { force = true })
            end
          end

          require("nvim-tree.api").tree.find_file({ open = true, focus = true })
        end,
        desc = "File tree",
      },
    },
    opts = {
      sort_by = "case_sensitive",
      view = {
        width = 55
      },
      renderer = {
        group_empty = true,
      },
      filters = {
        custom = { ".DS_Store" },
      },
    },
  },
  {
    "folke/trouble.nvim",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    cmd = { "Trouble" },
    opts = {
      focus = true,
    },
  },
  {
    "stevearc/aerial.nvim",
    dependencies = { "nvim-treesitter/nvim-treesitter", "nvim-tree/nvim-web-devicons" },
    cmd = { "AerialToggle", "AerialOpen", "AerialNavToggle" },
    opts = {
      attach_mode = "window",
      layout = {
        min_width = 28,
        default_direction = "right",
      },
      show_guides = true,
    },
  },
  {
    "akinsho/bufferline.nvim",
    version = "*",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      options = {
        diagnostics = "nvim_lsp",
        always_show_bufferline = true,
      },
    },
  },
}
