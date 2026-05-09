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

## Tagging — agent-driven (subagents return tags)

`ks_tag.py` does the I/O only. The LLM call is **your** responsibility as
the orchestrating agent: spawn sonnet subagents in parallel, collect their
JSON output, and write it back via the script. No external API key needed.

Step-by-step (do this when the user asks to tag, retag, or "make notes
searchable"):

1. **List untagged notes:**
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ks_tag.py list --kind paper > /tmp/ks-tag-plan.jsonl
   ```
   Output begins with a `# vocab: t1, t2, ...` comment header (the
   controlled vocabulary; vault may override via `<vault>/.ks-tag-vocab`),
   followed by one JSON object per untagged note:
   `{"file": "/abs/path.md", "kind": "paper", "slug": "...", "title": "...", "year": YYYY, "abstract": "..."}`

2. **Read the plan**, parse the vocab from the header, parse the JSONL.

3. **Batch into groups of 15–20 papers.**

4. **Dispatch parallel subagents** — one Agent tool call per batch, all in a
   single message so they run concurrently. Use:
   - `subagent_type: "general-purpose"`
   - `model: "sonnet"`
   - prompt template:
     ```
     You are tagging research sources for a knowledge-smith vault.

     CONTROLLED VOCABULARY (prefer these — only invent free-form tags when
     none of these fit):
     <comma-separated vocab from header>

     For each entry below, output a single JSON line of the form:
     {"file": "<absolute file path>", "tags": ["tag-one", "tag-two", ...]}

     Rules:
     - 2–5 tags per entry
     - lowercase, kebab-case (a-z 0-9 -)
     - prefer specific over generic ("transformer" over "ml")
     - no commentary, no Markdown fences — JSON lines only

     ENTRIES:
     1. file: /path/to/note1.md
        title: <title>
        year: <year>
        abstract: <abstract>
     2. file: /path/to/note2.md
        ...
     ```
   - Ask the subagent to "respond ONLY with N JSON lines, one per entry."

5. **Parse** each subagent's JSON-lines response.

6. **Apply tags** — one `apply` call per note:
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ks_tag.py apply /abs/path.md tag1 tag2 tag3
   ```
   You can run these in parallel via Bash.

7. **Refresh the reading list** afterwards:
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ks_reading_list.py --all
   ```

For a quick sanity check before tagging in bulk, pass `--limit 3` to `list`
and tag just three papers first.

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
- Tagging happens via subagents within Claude Code / Codex (the
  orchestrating agent dispatches them) — no external API key required.
