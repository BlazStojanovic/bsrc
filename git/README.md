# git in bsrc

This component manages Git defaults and one commit helper script.

## Files

- `gitconfig`: linked to `~/.gitconfig`
- `git-commit-all`: linked to `~/.local/bin/git-commit-all`

## Git defaults

The current Git config sets:

- `core.editor = nvim`
- `push.default = current`
- `pull.rebase = true`
- `init.defaultBranch = main`
- `rerere.enabled = true`
- `fetch.prune = true`
- `color.ui = auto`

These are intentionally small, general-purpose defaults rather than a large
alias-heavy Git config.

## Shell shortcuts

Git command shortcuts are defined in the Zsh config rather than in `.gitconfig`.
The current Git-related shell aliases are:

- `g='git'`
- `ga='git add .'`
- `ck='git switch'`
- `cm='git-commit-all'`
- `gd='git diff'`
- `gs='git status -sb'`
- `st='git status && git diff --stat'`
- `pl='git pull'`
- `ph='git push --force-with-lease'`
- `fh='git fetch'`
- `br='git log --graph --oneline --decorate --all'`
- `lg='lazygit'`

## `git-commit-all`

`git-commit-all` is a commit helper that:

- stages modified and deleted tracked files with `git add -u`
- inspects the staged diff
- generates a concise commit message with an emoji and category
- tries to infer the dominant change type from the staged files

Examples of the kinds of categories it can produce:

- docs
- tests
- config
- deps
- version bump
- bugfix
- refactor
- feat
- remove
- rename

The generated message also includes a short list of the top changed files plus
basic diff volume information.

This is useful when you want quick local commits, but it is still heuristic. It
should not be treated as a substitute for writing a deliberate commit message
when the change deserves one.
