---
name: knowledge-smith
description: Capture and index research sources (papers, articles, YouTube videos, blogs, GitHub repos) into a multi-vault knowledge-smith system. Use when the user wants to add, ingest, capture, save, bookmark, or remember a paper / arXiv ID / video / blog / repo / article URL.
---

# Knowledge Smith

Index research sources into the user's active knowledge-smith vault.

## When to use
Triggers: "add this paper", "save this video", "bookmark this repo",
"ingest <url>", "throw this in my knowledge base", a bare arXiv id like
`1706.03762`.

## Vault discovery
Scripts find the active vault by:

1. `$KNOWLEDGE_SMITH_VAULT` (must point to a directory containing `.knowledge-smith`)
2. Walking the cwd upward for the `.knowledge-smith` marker
3. Otherwise: hard fail with an init hint.

There is **no default vault**. The user keeps vaults wherever they want
(personal, work, nested in another vault). Run `ks_doctor.py` to confirm
which one resolved.

To start a new vault:
```
uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py --init <path>
```

## Source-type dispatch

| Input shape | Script |
|---|---|
| arXiv id or `arxiv.org/abs/...` | `ingest_arxiv.py` |
| Local PDF or non-arXiv PDF URL | `ingest_pdf.py` |
| Web Clipper `.md` path | `ingest_article.py` |
| `youtube.com/watch` or `youtu.be` URL | `ingest_youtube.py` |
| `github.com/owner/repo` URL | `ingest_bookmark.py` (lightweight) |
| Any other web URL | `ingest_bookmark.py` (treated as blog) |

Invocation form:
```
uv run ~/.claude/skills/knowledge-smith/scripts/<script>.py <args>
```
For Codex, swap `~/.claude` for `~/.codex` in the path.

## Workflow
1. **Ingest** writes a stub source to `inbox/`, raw assets to `raw/<kind>/`.
2. Read the inbox file. Surface its contents to the user.
3. Discuss whether to **register**: optionally
   `mv inbox/<f>.md sources/<kind>/` and flip `status:` from `captured` to
   `registered`. Update `updated:`.
4. Optionally **derive concept note(s)** in `notes/` referencing this source.
   A source can map to many notes; a note can pull from many sources. Update
   `indexed_in:` on the source and `sources:` on the note.
5. **Never edit `raw/`** files by hand. Use the scripts.

## Recovery
After a fresh clone, gitignored binaries (PDFs, audio) are missing. Run:
```
uv run ~/.claude/skills/knowledge-smith/scripts/recover_raw.py
```
GitHub is never recovered — the note + URL is the artifact.

## Inspecting
```
uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py
```
Reports vault root, counts, frontmatter validation, orphan raws, stale
binary refs (run recover_raw to fix), unindexed registered sources.

## Schema
Authoritative spec lives in `<vault>/CLAUDE.md`. Read before generating
files. Common-core fields (`type`, `status`, `slug`, `title`, `created`,
`updated`, `tags`) plus per-`source_kind` extensions.

## Don'ts
- Do not write under `raw/` by hand. Always go through the scripts.
- Do not invent metadata. Unknown fields → `null` (or omit if optional).
- Do not commit binaries. The vault `.gitignore` is the source of truth.
- Do not auto-create `topics/` pages — that layer is user-curated.
- Do not fetch GitHub API metadata. Github bookmarks stay minimal: URL + description.
- Do not assume a default vault path. If discovery fails, ask the user where
  the vault is (or to `--init` one).

## First-run notes
- `ingest_pdf.py` first invocation downloads ~hundreds of MB of docling
  layout/OCR models. Subsequent runs are cached.
- `ingest_youtube.py` uses YouTube auto-subs in slice 1; full Whisper
  transcription is a slice-2 follow-up.
