# knowledge-smith

A bsrc component that installs a personal **research-indexing skill** for
Claude Code and Codex, plus the runner scripts that feed it.

## What it does

`knowledge-smith` lets you capture sources from many channels (papers,
articles, YouTube videos, blog pointers, GitHub repos) into a markdown-only
Obsidian-frontended vault. Each source becomes **one note** in
`notes/<kind>/`, marked `read: false` until you process it. A generated
`reading-list/<kind>.md` page indexes everything still unread. Tags come
from an LLM pass over title + abstract, drawn from a controlled vocabulary.

```
[arxiv | PDF | Web Clipper | YouTube | github | blog]
                  │
                  ▼
   ks scripts (uv PEP 723; live here, symlinked into agent skill homes)
                  │
                  ▼
<some-vault>/
   notes/<kind>/<slug>.md       one note per source, read:false
   reading-list/<kind>.md       generated index of unread notes
   raw/                         parsed md committed; binaries gitignored
   CLAUDE.md                    schema contract
   .knowledge-smith             marker
```

Tooling lives in this repo (`bsrc/knowledge-smith/`). Vaults live wherever
the user puts them — multi-vault is first-class. Discovery is via the
`.knowledge-smith` marker file or the `KNOWLEDGE_SMITH_VAULT` env var; there
is **no default vault path**.

This vault is the **indexing tier**. Cross-source synthesis, distilled prose,
and writing work belong elsewhere (e.g. a separate Obsidian vault).

## Layout

```
knowledge-smith/
├── install.sh                 # links skill/ into ~/.claude and ~/.codex
├── skill/
│   ├── SKILL.md               # what Claude/Codex read at top level
│   └── scripts/
│       ├── _ks_common.py      # shared helpers
│       ├── ingest_arxiv.py
│       ├── ingest_pdf.py      # docling
│       ├── ingest_article.py  # Web Clipper input
│       ├── ingest_youtube.py  # yt-dlp auto-subs (Whisper deferred)
│       ├── ingest_bookmark.py # github + blog (lightweight)
│       ├── recover_raw.py     # refetch gitignored binaries
│       ├── ks_reading_list.py # regen reading-list/<kind>.md
│       ├── ks_tag.py          # `list` / `apply` plumbing for subagent-driven tagging
│       └── ks_doctor.py       # health check + --init <path>
└── vault-template/            # copied (not symlinked) by ks_doctor --init
    ├── CLAUDE.md
    ├── .gitignore
    ├── .knowledge-smith       # marker
    ├── README.md
    ├── templates/             # 5 *-note.md + 1 reading-list.md
    ├── notes/{papers,articles,youtube,blogs,github}/.gitkeep
    ├── reading-list/.gitkeep
    └── raw/{papers,articles,youtube}/.gitkeep
```

## Requirements

- `uv` (PEP 723 script runner). `brew install uv`.
- macOS (matches the rest of bsrc).
- For `ks_tag.py`: an LLM-capable agent harness (Claude Code, Codex). The
  script handles I/O; the harness dispatches sonnet subagents to actually
  produce the tags. No external API key required.

Each Python script declares its own deps in a PEP 723 header — uv resolves
and caches them on first invocation. No venv to manage.

## Usage

```bash
# Install the skill + scripts (or use bsrc's setup.sh)
./install.sh

# Scaffold a new vault somewhere — anywhere you like
uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py --init ~/Desktop/research-vault
cd ~/Desktop/research-vault
git init && git add -A && git commit -m "init knowledge-smith vault"

# Capture sources (each lands directly in notes/<kind>/, read:false)
uv run ~/.claude/skills/knowledge-smith/scripts/ingest_arxiv.py 1706.03762
uv run ~/.claude/skills/knowledge-smith/scripts/ingest_bookmark.py https://github.com/karpathy/nanoGPT
uv run ~/.claude/skills/knowledge-smith/scripts/ingest_youtube.py https://youtu.be/dQw4w9WgXcQ

# Refresh the reading list
uv run ~/.claude/skills/knowledge-smith/scripts/ks_reading_list.py --all

# Tag — say "tag my paper notes" to your agent (Claude Code / Codex);
# the skill orchestrates sonnet subagents, applies tags, and refreshes
# the reading list. No API key required.

# Inspect
uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py

# Recover gitignored binaries after a fresh clone
uv run ~/.claude/skills/knowledge-smith/scripts/recover_raw.py
```

The skill is auto-discovered by Claude Code and Codex when you say things
like "save this paper" or "ingest this URL".

## Slice-3 deferrals

- Whisper-on-promote for YouTube transcripts (slice 1 ships auto-subs only).
- Audio download flag for `ingest_youtube.py`.
- Auto-regenerate reading-list as a post-ingest hook.
- Tag-grouped reading-list view (`reading-list/by-tag/<tag>.md`).
- `--read` TUI on `ks_doctor` for batch flipping read/unread.
- Watch jobs (cron arXiv RSS, GitHub stars sync).
- Search infrastructure (qmd / SQLite FTS) when a vault outgrows the index.
