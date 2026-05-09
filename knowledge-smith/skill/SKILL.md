---
name: knowledge-smith
description: Capture and index research sources (papers, articles, YouTube videos, blogs, GitHub repos) into a knowledge-smith vault. One summary note per source, marked unread until read. Use when the user wants to add, ingest, capture, save, bookmark, remember, tag, or list a paper / arXiv ID / video / blog / repo / article URL.
---

# Knowledge Smith

Index research sources into the user's active knowledge-smith vault as
**one summary note per source**. The vault is a data index, not a
synthesis tier — concept-level cross-source writing belongs elsewhere.

## When to use
Triggers: "add this paper", "save this video", "bookmark this repo",
"ingest <url>", "throw this in my knowledge base", "tag my notes",
"what's on my reading list?", a bare arXiv id like `1706.03762`.

## Vault discovery
Scripts find the active vault by:

1. `$KNOWLEDGE_SMITH_VAULT` (must point to a directory containing `.knowledge-smith`)
2. Walking the cwd upward for the `.knowledge-smith` marker
3. Otherwise: hard fail with an init hint.

There is **no default vault**. The user keeps vaults wherever they want.
Run `ks_doctor.py` to confirm which one resolved.

To start a new vault:
```
uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py --init <path>
```

## Source-type dispatch

| Input shape | Script | Lands in |
|---|---|---|
| arXiv id or `arxiv.org/abs/...` | `ingest_arxiv.py` | `notes/papers/<year>-<slug>.md` |
| Local PDF or non-arXiv PDF URL | `ingest_pdf.py` | `notes/papers/<year>-<slug>.md` |
| Web Clipper `.md` path | `ingest_article.py` | `notes/articles/<year>-<slug>.md` |
| `youtube.com/watch` or `youtu.be` URL | `ingest_youtube.py` | `notes/youtube/<year>-<slug>.md` |
| `github.com/owner/repo` URL | `ingest_bookmark.py` | `notes/github/<owner>-<repo>.md` |
| Any other web URL | `ingest_bookmark.py` | `notes/blogs/<slug>.md` |

Invocation form:
```
uv run ~/.claude/skills/knowledge-smith/scripts/<script>.py <args>
```
For Codex, swap `~/.claude` for `~/.codex` in the path.

## Workflow
1. **Ingest** writes a note directly to `notes/<kind>/<slug>.md` with
   `read: false`, plus raw assets to `raw/<kind>/`.
2. Read the note. Surface its TL;DR / abstract to the user.
3. Optionally **tag** with `ks_tag.py` so it's searchable.
4. When the user has actually read it, flip `read: true` in frontmatter
   (and bump `updated:`).
5. **Regenerate the reading list** with `ks_reading_list.py` when notes
   change, so `reading-list/<kind>.md` stays current.
6. **Never edit `raw/`** files by hand. Use the ingest scripts.

## Reading list
```
uv run ~/.claude/skills/knowledge-smith/scripts/ks_reading_list.py --all
uv run ~/.claude/skills/knowledge-smith/scripts/ks_reading_list.py --kind paper
```
Generates `reading-list/<kind>.md` listing every `read: false` note for that
kind. Dated kinds (paper/article/youtube) are grouped by year, descending;
blog/github are flat lists.

## Tagging
```
uv run ~/.claude/skills/knowledge-smith/scripts/ks_tag.py --kind paper
uv run ~/.claude/skills/knowledge-smith/scripts/ks_tag.py --all --model haiku
uv run ~/.claude/skills/knowledge-smith/scripts/ks_tag.py --kind paper --force
```
Calls Claude (default `claude-sonnet-4-6`, override `--model`) with a cached
controlled-vocabulary system prompt. Writes 2–5 lowercase kebab-case tags
into the note's frontmatter. Idempotent — only touches notes whose `tags`
list is empty unless `--force`. Requires `ANTHROPIC_API_KEY` in the env.

The vocabulary lives in code (`_ks_common.DEFAULT_TAG_VOCAB`); a vault may
override by writing its own `<vault>/.ks-tag-vocab` (one tag per line).

## Recovery
After a fresh clone, gitignored binaries (PDFs, audio) are missing. Run:
```
uv run ~/.claude/skills/knowledge-smith/scripts/recover_raw.py
```
Walks `notes/<kind>/` and refetches `raw_pdf` for arxiv papers. GitHub and
blog notes are never recovered — the note + URL is the artifact.

## Inspecting
```
uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py
```
Reports vault root, per-kind counts (total + unread), frontmatter validation,
orphan raws, stale binary refs, reading-list freshness, top tags.

## Schema
Authoritative spec lives in `<vault>/CLAUDE.md`. Read before generating
files. Common-core fields (`type`, `kind`, `slug`, `title`, `created`,
`updated`, `read`, `tags`) plus per-`kind` extensions.

## Don'ts
- Do not write under `raw/` by hand. Always go through the scripts.
- Do not invent metadata. Unknown fields → `null` (or omit if optional).
- Do not commit binaries. The vault `.gitignore` is the source of truth.
- Do not hand-edit `reading-list/<kind>.md` — `ks_reading_list.py` overwrites.
- Do not fetch GitHub API metadata. Github bookmarks stay minimal: URL + description.
- Do not assume a default vault path. If discovery fails, ask the user where
  the vault is (or to `--init` one).

## First-run notes
- `ingest_pdf.py` first invocation downloads ~hundreds of MB of docling
  layout/OCR models. Subsequent runs are cached.
- `ingest_youtube.py` uses YouTube auto-subs in slice 1; full Whisper
  transcription is a slice-2 follow-up.
- `ks_tag.py` requires `ANTHROPIC_API_KEY` and incurs API cost (~sub-$1
  per ~150 papers on Sonnet 4.6 with prompt caching).
