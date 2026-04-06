return {
  {
    "nvim-telescope/telescope.nvim",
    dependencies = { "nvim-lua/plenary.nvim" },
    keys = {
      { "<leader>ff", "<cmd>Telescope find_files<cr>", desc = "Find files" },
      { "<leader>fg", "<cmd>Telescope live_grep<cr>", desc = "Live grep" },
      { "<leader>fb", "<cmd>Telescope buffers<cr>", desc = "Buffers" },
      { "<leader>fh", "<cmd>Telescope help_tags<cr>", desc = "Help tags" },
    },
    opts = {
      defaults = {
        layout_strategy = "horizontal",
        layout_config = {
          preview_width = 0.4,
          horizontal = {
            width = 0.95,
            height = 0.95,
          },
        },
      },
    },
  },
  {
    "nvim-treesitter/nvim-treesitter",
    lazy = false,
    build = ":TSUpdate",
    opts = {
      install_dir = vim.fn.stdpath("data") .. "/site",
      ensure_installed = {
        "lua",
        "vim",
        "vimdoc",
        "bash",
        "markdown",
        "python",
        "javascript",
        "typescript",
        "tsx",
        "go",
        "rust",
      },
    },
    config = function(_, opts)
      local ts = require("nvim-treesitter")
      local languages = opts.ensure_installed

      ts.setup({
        install_dir = opts.install_dir,
      })

      vim.schedule(function()
        ts.install(languages, { summary = true })
      end)

      vim.api.nvim_create_autocmd("FileType", {
        pattern = {
          "lua",
          "vim",
          "markdown",
          "python",
          "javascript",
          "typescript",
          "typescriptreact",
          "go",
          "rust",
          "sh",
        },
        callback = function(event)
          pcall(vim.treesitter.start, event.buf)
          vim.bo[event.buf].indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
        end,
      })
    end,
  },
  {
    "mbbill/undotree",
    keys = {
      { "<leader>u", "<cmd>UndotreeToggle<cr>", desc = "Undotree" },
    },
  },
  {
    "tpope/vim-fugitive",
    keys = {
      { "<leader>gs", "<cmd>Git<cr>", desc = "Git status" },
    },
  },
  {
    "numToStr/Comment.nvim",
    opts = {},
    keys = {
      { "<leader>/", mode = { "n", "v" }, desc = "Toggle comment" },
    },
    config = function(_, opts)
      require("Comment").setup(opts)
      vim.keymap.set({ "n", "v" }, "<leader>/", "<cmd>CommentToggle<cr>", { silent = true })
    end,
  },
  {
    "rmagatti/auto-session",
    opts = {
      auto_restore = true,
      auto_save = true,
      auto_session_suppress_dirs = { "~/" },
    },
  },
}
