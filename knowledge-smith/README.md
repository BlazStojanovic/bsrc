# knowledge-smith

A bsrc component that installs a personal **research-aggregation and
indexing skill** for Claude Code and Codex, plus the runner scripts that
feed it.

## What it does

`knowledge-smith` lets you capture sources from many channels (papers,
articles, YouTube videos, blog pointers, GitHub repos) into a markdown-only
Obsidian-frontended vault and turn them into concept-level synthesis notes
that compound over time.

```
[arxiv | PDF | Web Clipper | YouTube | github | blog]
                  │
                  ▼
   ks scripts (uv PEP 723; live here, symlinked into agent skill homes)
                  │
                  ▼
<some-vault>/
   inbox/             fresh source captures, status: captured
   sources/<kind>/    registered sources
   notes/             concept-oriented synthesis (flat, cross-source)
   topics/            user-curated reading maps
   raw/               parsed md committed; binaries gitignored
   CLAUDE.md          schema contract
   .knowledge-smith   marker
```

Tooling lives in this repo (`bsrc/knowledge-smith/`). Vaults live wherever
the user puts them — multi-vault is first-class. Discovery is via the
`.knowledge-smith` marker file or the `KNOWLEDGE_SMITH_VAULT` env var; there
is **no default vault path**.

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
│       ├── recover_raw.py
│       └── ks_doctor.py       # health check + --init <path>
└── vault-template/            # copied (not symlinked) by ks_doctor --init
    ├── CLAUDE.md
    ├── .gitignore
    ├── .knowledge-smith       # marker
    ├── README.md
    ├── templates/             # 7 note templates
    ├── inbox/.gitkeep
    ├── sources/{papers,articles,youtube,blogs,github}/.gitkeep
    ├── notes/.gitkeep
    ├── topics/.gitkeep
    └── raw/{papers,articles,youtube}/.gitkeep
```

## Requirements

- `uv` (PEP 723 script runner). `brew install uv`.
- macOS (matches the rest of bsrc).

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

# Capture sources
uv run ~/.claude/skills/knowledge-smith/scripts/ingest_arxiv.py 1706.03762
uv run ~/.claude/skills/knowledge-smith/scripts/ingest_bookmark.py https://github.com/karpathy/nanoGPT
uv run ~/.claude/skills/knowledge-smith/scripts/ingest_youtube.py https://youtu.be/dQw4w9WgXcQ

# Triage from inbox into sources/<kind>/, then write concept notes by hand
# (or with the agent) in notes/.

# Inspect
uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py

# Recover gitignored binaries after a fresh clone
uv run ~/.claude/skills/knowledge-smith/scripts/recover_raw.py
```

The skill is auto-discovered by Claude Code and Codex when you say things
like "save this paper" or "ingest this URL".

## Slice 2 deferrals

- Whisper-on-promote for YouTube transcripts (slice 1 ships auto-subs only).
- Audio download flag for `ingest_youtube.py`.
- Concept-extraction skill that proposes `notes/` from a single source.
- Weekly digest skill, topic-taxonomy lint pass.
- Watch jobs (cron arXiv RSS, GitHub stars sync).
- Search infrastructure (qmd / SQLite FTS) when a vault outgrows the index.
