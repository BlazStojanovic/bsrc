local M = {}

local current_appearance = nil

local palettes = {
  dark = {
    base00 = "#2d2a2e",
    base01 = "#4b464d",
    base02 = "#5b595c",
    base03 = "#a1a19f",
    base04 = "#c1c0c0",
    base05 = "#fcfcfa",
    base06 = "#dfd0ff",
    base07 = "#ffffff",
    base08 = "#ff6188",
    base09 = "#fc9867",
    base0A = "#ffd866",
    base0B = "#a9dc76",
    base0C = "#78dce8",
    base0D = "#78dce8",
    base0E = "#ab9df2",
    base0F = "#ff6188",
  },
  light = {
    base00 = "#faf4f2",
    base01 = "#d6d2d0",
    base02 = "#bfb9ba",
    base03 = "#998c9c",
    base04 = "#706b6e",
    base05 = "#29242a",
    base06 = "#3f2e78",
    base07 = "#000000",
    base08 = "#e14775",
    base09 = "#e16032",
    base0A = "#cc7a0a",
    base0B = "#269d69",
    base0C = "#1c8ca8",
    base0D = "#1c8ca8",
    base0E = "#7058be",
    base0F = "#8f1f43",
  },
}

local function get_appearance()
  local output = vim.fn.system("defaults read -g AppleInterfaceStyle 2>/dev/null")
  if vim.v.shell_error == 0 and output:match("Dark") then
    return "dark"
  end
  return "light"
end

function M.apply(force)
  local appearance = get_appearance()
  if not force and appearance == current_appearance then
    return
  end

  current_appearance = appearance
  vim.o.background = appearance
  require("base16-colorscheme").setup(palettes[appearance])
end

return M
