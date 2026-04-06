return {
  {
    "hrsh7th/nvim-cmp",
    event = "InsertEnter",
    dependencies = {
      "hrsh7th/cmp-nvim-lsp",
      "hrsh7th/cmp-buffer",
      "hrsh7th/cmp-path",
      "L3MON4D3/LuaSnip",
      "saadparwaiz1/cmp_luasnip",
      "windwp/nvim-autopairs",
    },
    config = function()
      local cmp = require("cmp")
      local luasnip = require("luasnip")

      require("nvim-autopairs").setup({})

      cmp.setup({
        snippet = {
          expand = function(args)
            luasnip.lsp_expand(args.body)
          end,
        },
        completion = {
          completeopt = "menu,menuone,noinsert",
        },
        mapping = cmp.mapping.preset.insert({
          ["<C-Space>"] = cmp.mapping.complete(),
          ["<CR>"] = cmp.mapping.confirm({ select = false }),
          ["<Tab>"] = cmp.mapping(function(fallback)
            if cmp.visible() then
              cmp.select_next_item()
            elseif luasnip.expand_or_jumpable() then
              luasnip.expand_or_jump()
            else
              fallback()
            end
          end, { "i", "s" }),
          ["<S-Tab>"] = cmp.mapping(function(fallback)
            if cmp.visible() then
              cmp.select_prev_item()
            elseif luasnip.jumpable(-1) then
              luasnip.jump(-1)
            else
              fallback()
            end
          end, { "i", "s" }),
        }),
        sources = cmp.config.sources({
          { name = "nvim_lsp" },
          { name = "luasnip" },
          { name = "path" },
        }, {
          { name = "buffer" },
        }),
      })

      local cmp_autopairs = require("nvim-autopairs.completion.cmp")
      cmp.event:on("confirm_done", cmp_autopairs.on_confirm_done())
    end,
  },
  {
    "ray-x/lsp_signature.nvim",
    event = "LspAttach",
    opts = {
      hint_enable = false,
      floating_window = true,
      handler_opts = {
        border = "rounded",
      },
    },
  },
  {
    "neovim/nvim-lspconfig",
    config = function()
      local capabilities = vim.lsp.protocol.make_client_capabilities()
      local ok_cmp, cmp_nvim_lsp = pcall(require, "cmp_nvim_lsp")
      if ok_cmp then
        capabilities = cmp_nvim_lsp.default_capabilities(capabilities)
      end

      vim.api.nvim_create_autocmd("LspAttach", {
        callback = function(event)
          local opts = { buffer = event.buf }
          local client = vim.lsp.get_client_by_id(event.data.client_id)
          local telescope = function(method)
            return function()
              require("telescope.builtin")[method]()
            end
          end

          vim.keymap.set("n", "gd", telescope("lsp_definitions"), opts)
          vim.keymap.set("n", "gD", vim.lsp.buf.declaration, opts)
          vim.keymap.set("n", "gr", telescope("lsp_references"), opts)
          vim.keymap.set("n", "gi", telescope("lsp_implementations"), opts)
          vim.keymap.set("n", "gy", telescope("lsp_type_definitions"), opts)
          vim.keymap.set("n", "<leader>ds", telescope("lsp_document_symbols"), opts)
          vim.keymap.set("n", "<leader>ws", telescope("lsp_dynamic_workspace_symbols"), opts)
          vim.keymap.set("n", "K", vim.lsp.buf.hover, opts)
          vim.keymap.set("n", "<C-k>", vim.lsp.buf.signature_help, opts)
          vim.keymap.set("n", "<leader>rn", vim.lsp.buf.rename, opts)
          vim.keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, opts)

          if client and client:supports_method("textDocument/inlayHint", event.buf) then
            vim.lsp.inlay_hint.enable(true, { bufnr = event.buf })
            vim.keymap.set("n", "<leader>uh", function()
              local enabled = vim.lsp.inlay_hint.is_enabled({ bufnr = event.buf })
              vim.lsp.inlay_hint.enable(not enabled, { bufnr = event.buf })
            end, opts)
          end

          pcall(function()
            require("lsp_signature").on_attach({}, event.buf)
          end)
        end,
      })

      vim.lsp.config("lua_ls", {
        capabilities = capabilities,
        settings = {
          Lua = {
            diagnostics = {
              globals = { "vim" },
            },
            hint = {
              enable = true,
            },
          },
        },
      })

      vim.lsp.config("ruff", {
        capabilities = capabilities,
        init_options = {
          settings = {
            organizeImports = true,
          },
        },
      })

      vim.lsp.config("pyright", {
        capabilities = capabilities,
      })
      vim.lsp.config("clangd", {
        capabilities = capabilities,
      })
      vim.lsp.config("gopls", {
        capabilities = capabilities,
        settings = {
          gopls = {
            hints = {
              assignVariableTypes = true,
              compositeLiteralFields = true,
              compositeLiteralTypes = true,
              constantValues = true,
              functionTypeParameters = true,
              parameterNames = true,
              rangeVariableTypes = true,
            },
          },
        },
      })
      vim.lsp.config("rust_analyzer", {
        capabilities = capabilities,
        settings = {
          ["rust-analyzer"] = {
            inlayHints = {
              bindingModeHints = { enable = true },
              closureReturnTypeHints = { enable = "always" },
              discriminantHints = { enable = "always" },
              lifetimeElisionHints = { enable = "skip_trivial" },
              typeHints = { enable = true },
            },
          },
        },
      })
      vim.lsp.config("ts_ls", {
        capabilities = capabilities,
      })

      vim.lsp.enable("lua_ls")
      vim.lsp.enable("pyright")
      vim.lsp.enable("clangd")
      vim.lsp.enable("ruff")
      vim.lsp.enable("gopls")
      vim.lsp.enable("rust_analyzer")
      vim.lsp.enable("ts_ls")
    end,
  },
}
