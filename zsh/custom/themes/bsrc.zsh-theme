_bsrc_appearance() {
  if [[ "$(defaults read -g AppleInterfaceStyle 2>/dev/null)" == "Dark" ]]; then
    printf '%s\n' "dark"
  else
    printf '%s\n' "light"
  fi
}

_bsrc_python_env_prompt() {
  local env_name color

  [[ -n "${VIRTUAL_ENV:-}" ]] || return 0

  env_name="${VIRTUAL_ENV:t}"

  case "$(_bsrc_appearance)" in
    dark) color=186 ;;
    *) color=130 ;;
  esac

  printf ' %%F{%s}(%s)%%f' "$color" "$env_name"
}

_bsrc_apply_theme() {
  case "$(_bsrc_appearance)" in
    dark)
      PROMPT="%(?:%F{118}%1{➜%} :%F{197}%1{➜%} ) %F{81}%c%f"
      ZSH_THEME_GIT_PROMPT_PREFIX="%F{81}git:(%F{197}"
      ZSH_THEME_GIT_PROMPT_SUFFIX="%f"
      ZSH_THEME_GIT_PROMPT_DIRTY="%F{81}) %F{186}%1{✗%}%f "
      ZSH_THEME_GIT_PROMPT_CLEAN="%F{81})%f "
      ;;
    *)
      PROMPT="%(?:%F{34}%1{➜%} :%F{160}%1{➜%} ) %F{25}%c%f"
      ZSH_THEME_GIT_PROMPT_PREFIX="%F{31}git:(%F{124}"
      ZSH_THEME_GIT_PROMPT_SUFFIX="%f"
      ZSH_THEME_GIT_PROMPT_DIRTY="%F{31}) %F{130}%1{✗%}%f "
      ZSH_THEME_GIT_PROMPT_CLEAN="%F{31})%f "
      ;;
  esac

  PROMPT+=' $(_bsrc_python_env_prompt)'
  PROMPT+=' $(git_prompt_info)'
}

autoload -Uz add-zsh-hook
add-zsh-hook precmd _bsrc_apply_theme
_bsrc_apply_theme
