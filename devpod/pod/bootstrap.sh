#!/usr/bin/env bash
# Runs inside a dev pod. Installs a userland that survives restarts under
# $HOME (=/persistent): pixi CLI tools, nvim, claude, codex, aws, bsrc.
# Idempotent; pass --upgrade to refresh the downloaded binaries.
set -euo pipefail

BSRC_REPO="${BSRC_REPO:-https://github.com/BlazStojanovic/bsrc.git}"
BSRC_REF="${BSRC_REF:-main}"
BSRC_COMPONENTS="${BSRC_COMPONENTS:-zsh git tmux nvim codex claude}"
PIXI_PACKAGES="${PIXI_PACKAGES:-zsh tmux ripgrep fd-find jq btop yazi lazygit nodejs}"
UPGRADE=0
[ "${1:-}" = "--upgrade" ] && UPGRADE=1

H="${HOME:-/persistent}"
BIN="$H/.local/bin"
OPT="$H/.local/opt"
DP="$H/.devpod"
export PIXI_HOME="$H/.pixi"
export PATH="$BIN:$PIXI_HOME/bin:$PATH"
mkdir -p "$BIN" "$OPT" "$DP" "$PIXI_HOME/bin"

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok() { printf '    \033[32mok\033[0m %s\n' "$*"; }
warn() { printf '    \033[1;33mwarn\033[0m %s\n' "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }
fetch() { curl -fsSL --retry 3 --connect-timeout 20 "$@"; }
need() { [ "$UPGRADE" = 1 ] || [ ! -x "$1" ]; }
add_line() { grep -qxF "$2" "$1" 2>/dev/null || printf '%s\n' "$2" >>"$1"; }

case "$(uname -m)" in
  aarch64 | arm64) NV=arm64 RUST=aarch64 AWSA=aarch64 ;;
  x86_64 | amd64) NV=x86_64 RUST=x86_64 AWSA=x86_64 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

step "Shell environment (~/.devpod/env.sh)"
cat >"$DP/env.sh" <<'EOF'
# Managed by bsrc/devpod; sourced by ~/.bashrc and ~/.zshenv.
# ~/.local/bin, then pixi, then the image: apt copies from bsrc's installers
# vanish on restart, so pixi's must win before and after.
case ":$PATH:" in *":$HOME/.pixi/bin:"*) ;; *) PATH="$HOME/.pixi/bin:$PATH" ;; esac
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) PATH="$HOME/.local/bin:$PATH" ;; esac
export PATH PIXI_HOME="$HOME/.pixi" DEVPOD=1
# The dev container is privileged and sees every GPU on the node; this pins
# CUDA to the GPU(s) the pod was allocated. `devpod pin-gpu` rewrites it.
[ -f "$HOME/.devpod/gpu.sh" ] && . "$HOME/.devpod/gpu.sh"
EOF
# Move the day-one inline pin out of ~/.bashrc into ~/.devpod/gpu.sh.
if grep -q 'BEGIN devpod-gpu-pin' "$H/.bashrc" 2>/dev/null; then
  old="$(grep -oE 'CUDA_VISIBLE_DEVICES=GPU-[0-9a-f-]+' "$H/.bashrc" | head -1 || true)"
  if [ -n "$old" ] && [ ! -f "$DP/gpu.sh" ]; then printf 'export %s\n' "$old" >"$DP/gpu.sh"; fi
  sed -i '/BEGIN devpod-gpu-pin/,/END devpod-gpu-pin/d' "$H/.bashrc"
fi
add_line "$H/.bashrc" '[ -f "$HOME/.devpod/env.sh" ] && . "$HOME/.devpod/env.sh"'
# Interactive bash (infractl dev connect, VS Code) hands over to zsh; set DEVPOD_BASH=1 to stay.
add_line "$H/.bashrc" 'case $- in *i*) [ -z "${ZSH_VERSION:-}${DEVPOD_BASH:-}" ] && [ -x "$HOME/.pixi/bin/zsh" ] && exec "$HOME/.pixi/bin/zsh" -l ;; esac'
add_line "$H/.zshenv" '[ -f "$HOME/.devpod/env.sh" ] && . "$HOME/.devpod/env.sh"'
add_line "$H/.profile" '[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"'
ok "PATH, GPU pin and zsh handover wired"

step "pixi and CLI tools ($PIXI_PACKAGES)"
if need "$PIXI_HOME/bin/pixi"; then
  fetch -o "$tmp/pixi.tgz" "https://github.com/prefix-dev/pixi/releases/latest/download/pixi-$RUST-unknown-linux-musl.tar.gz"
  mkdir -p "$tmp/pixi" && tar -xzf "$tmp/pixi.tgz" -C "$tmp/pixi"
  install -m 0755 "$(find "$tmp/pixi" -type f -name pixi | head -1)" "$PIXI_HOME/bin/pixi"
fi
ok "$("$PIXI_HOME/bin/pixi" --version)"
for p in $PIXI_PACKAGES; do
  # Idempotent: an existing environment is kept (or updated with --upgrade).
  if "$PIXI_HOME/bin/pixi" global install "$p" >"$tmp/pixi-$p.log" 2>&1; then
    ok "$p"
  else
    warn "pixi could not install $p:"
    tail -3 "$tmp/pixi-$p.log" >&2 || true
  fi
done
[ "$UPGRADE" = 1 ] && "$PIXI_HOME/bin/pixi" global update >/dev/null 2>&1 || true

step "Neovim (latest stable release)"
if need "$OPT/nvim/bin/nvim"; then
  fetch -o "$tmp/nvim.tgz" "https://github.com/neovim/neovim/releases/latest/download/nvim-linux-$NV.tar.gz"
  rm -rf "$OPT/nvim" && mkdir -p "$OPT/nvim"
  tar -xzf "$tmp/nvim.tgz" -C "$OPT/nvim" --strip-components=1
fi
ln -sfn "$OPT/nvim/bin/nvim" "$BIN/nvim"
ok "$("$BIN/nvim" --version | head -1)"

step "Codex CLI (official standalone installer)"
# The bare release binary is not enough: interactive codex starts a background
# app server and needs the full package (helpers, resources) the installer lays
# out under ~/.codex/packages/standalone, linked from ~/.local/bin/codex.
if [ "$UPGRADE" = 1 ] || [ ! -e "$H/.codex/packages/standalone/current" ]; then
  [ -L "$BIN/codex" ] || rm -f "$BIN/codex"  # bare binary from an older bootstrap
  fetch -o "$tmp/codex-install.sh" https://github.com/openai/codex/releases/latest/download/install.sh
  CODEX_NON_INTERACTIVE=1 sh "$tmp/codex-install.sh" >"$tmp/codex.log" 2>&1 \
    || { tail -5 "$tmp/codex.log" >&2; warn "codex install failed"; }
fi
[ -x "$BIN/codex" ] && ok "$("$BIN/codex" --version 2>/dev/null | head -1)"

step "Claude Code (official installer)"
if need "$BIN/claude"; then
  fetch -o "$tmp/claude-install.sh" https://claude.ai/install.sh
  bash "$tmp/claude-install.sh" >"$tmp/claude.log" 2>&1 || { tail -5 "$tmp/claude.log" >&2; warn "claude install failed"; }
fi
[ -x "$BIN/claude" ] && ok "$("$BIN/claude" --version 2>/dev/null | head -1)"

step "AWS CLI v2"
if need "$BIN/aws"; then
  fetch -o "$tmp/awscli.zip" "https://awscli.amazonaws.com/awscli-exe-linux-$AWSA.zip"
  unzip -q "$tmp/awscli.zip" -d "$tmp"
  "$tmp/aws/install" -i "$H/.local/aws-cli" -b "$BIN" --update >/dev/null
fi
mkdir -p "$H/.aws"
if [ -f "$DP/aws-config" ] && [ ! -f "$H/.aws/config" ]; then
  cp "$DP/aws-config" "$H/.aws/config"
  ok "copied SSO profiles from the laptop into ~/.aws/config"
fi
ok "$("$BIN/aws" --version 2>&1 | head -1)"

step "bsrc dotfiles ($BSRC_REF)"
if [ ! -d "$H/bsrc/.git" ]; then git clone --quiet "$BSRC_REPO" "$H/bsrc"; fi
if git -C "$H/bsrc" fetch --quiet origin && git -C "$H/bsrc" checkout --quiet "$BSRC_REF" 2>/dev/null; then
  git -C "$H/bsrc" pull --quiet --ff-only || warn "bsrc has local changes; left as is"
else
  warn "could not check out bsrc ref '$BSRC_REF'; using what is there"
fi
# bsrc's Ubuntu installers also apt-install packages; those land outside
# /persistent and vanish on restart, which is fine: pixi provides the same tools.
apt-get update -qq >/dev/null 2>&1 || warn "apt-get update failed; bsrc apt steps may warn"
for c in $BSRC_COMPONENTS; do
  [ -x "$H/bsrc/$c/install.sh" ] || continue
  if (cd "$H/bsrc" && DEBIAN_FRONTEND=noninteractive "./$c/install.sh") >"$DP/bsrc-$c.log" 2>&1; then
    ok "bsrc $c"
  else
    warn "bsrc $c failed; see ~/.devpod/bsrc-$c.log"
  fi
done

step "Pod-specific Claude and Codex config"
# bsrc's Claude settings run macOS-only hooks (peon-ping); keep everything else.
if [ -L "$H/.claude/settings.json" ] && have jq; then
  src="$(readlink "$H/.claude/settings.json")"
  jq 'del(.hooks)' "$src" >"$tmp/settings.json" && rm "$H/.claude/settings.json" && mv "$tmp/settings.json" "$H/.claude/settings.json"
  ok "~/.claude/settings.json generated from bsrc without hooks"
fi
if [ -d "$DP/skill" ]; then
  mkdir -p "$H/.claude/skills" "$H/.codex/skills"
  ln -sfn "$DP/skill" "$H/.claude/skills/devpod"
  ln -sfn "$DP/skill" "$H/.codex/skills/devpod"
  ok "devpod skill linked for claude and codex"
fi
if [ -f "$H/.codex/config.toml" ]; then
  python3 - "$H/.codex/config.toml" <<'PY'
import glob, os, re, sys
path = sys.argv[1]
text = open(path).read()
text = re.sub(r"(?m)^notify\s*=.*\n", "", text)  # macOS notifier
text = re.sub(r'(?ms)^\[projects\."/Users/[^"]*"\]\n(?:(?!\[).*\n?)*', "", text)
repos = sorted(os.path.dirname(g) for g in glob.glob("/persistent/*/.git"))
for project in ["/persistent", *repos]:
    if f'[projects."{project}"]' not in text:
        text = text.rstrip("\n") + f'\n\n[projects."{project}"]\ntrust_level = "trusted"\n'
open(path, "w").write(text)
PY
  ok "~/.codex/config.toml: dropped macOS notify and paths, trusted /persistent and its repos"
fi

step "SQL helper (lake-sql)"
cat >"$BIN/lake-sql" <<'EOF'
#!/usr/bin/env bash
# One SELECT through the query script and AWS profile set in ~/.config/bsrc/devpod.env.
# Usage: lake-sql "SELECT ... LIMIT 10" [script args]
set -euo pipefail
[ -f "$HOME/.config/bsrc/devpod.env" ] && . "$HOME/.config/bsrc/devpod.env"
: "${LAKE_PROFILE:?set LAKE_PROFILE in ~/.config/bsrc/devpod.env}"
: "${LAKE_SQL_SCRIPT:?set LAKE_SQL_SCRIPT in ~/.config/bsrc/devpod.env}"
[ $# -ge 1 ] || { echo "usage: lake-sql \"SELECT ... LIMIT 10\" [script args]" >&2; exit 2; }
[ -f "$LAKE_SQL_SCRIPT" ] || { echo "lake-sql: missing $LAKE_SQL_SCRIPT" >&2; exit 1; }
if ! aws sts get-caller-identity --profile "$LAKE_PROFILE" >/dev/null 2>&1; then
  echo "lake-sql: sign in first: aws sso login --profile $LAKE_PROFILE --use-device-code --no-browser" >&2
  exit 1
fi
sql="$1"; shift
exec uv run --script "$LAKE_SQL_SCRIPT" --profile "$LAKE_PROFILE" --sql "$sql" "$@"
EOF
chmod 0755 "$BIN/lake-sql"
ok "lake-sql installed"

lake_profile="$( (. "$H/.config/bsrc/devpod.env" 2>/dev/null; printf %s "${LAKE_PROFILE:-<profile>}") )"
cat <<EOF

Done. One-time sign-ins inside the pod (each prints a URL or code for your browser):
  claude                          then /login
  codex login --device-auth
  aws sso login --profile $lake_profile --use-device-code --no-browser
EOF
