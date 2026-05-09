# Working rules for this knowledge-smith vault

Read this before editing anything in the vault.

## Purpose

This vault is the **indexing tier** of a personal research knowledge base.
It captures sources from many channels (papers, web articles, YouTube videos,
blog pointers, GitHub repos) and stores **one summary note per source** —
1-to-1, never many-to-many.

Concept-level synthesis (cross-source reasoning, distilled prose, writing
work) lives elsewhere. This vault does data indexing only.

Two kinds of artifact live here:

- **Notes** (`notes/<kind>/`) — one file per source. Title, metadata, a short
  summary, links to raw assets. Marked `read: false` until you've processed
  them.
- **Reading lists** (`reading-list/<kind>.md`) — generated indexes of unread
  notes per kind. Re-render with `ks_reading_list.py`.

The vault is markdown only. The frontend is Obsidian. Tooling lives outside
the vault (in `bsrc/`) and is invoked via the knowledge-smith skill.

## Pipeline

```
[arxiv | PDF | Web Clipper | YouTube | github | blog]
                 │
                 ▼
        notes/<kind>/<slug>.md          read: false
                 │
                 ▼   (generate / regenerate)
        reading-list/<kind>.md          (auto)
                 │
                 ▼   (you read it; flip read: true)
        notes/<kind>/<slug>.md          read: true   ← drops out of reading-list
```

There is no inbox tier. Ingest writes the note in its final location. The
reading list is the queue.

## Folder roles

| Folder | Role | Committed? |
|---|---|---|
| `notes/papers/<year>-<slug>.md` | Paper summary notes | yes |
| `notes/articles/<year>-<slug>.md` | Web-article summary notes | yes |
| `notes/youtube/<year>-<slug>.md` | YouTube-video summary notes | yes |
| `notes/blogs/<slug>.md` | Lightweight blog bookmarks (timeless) | yes |
| `notes/github/<owner>-<repo>.md` | Lightweight GitHub bookmarks (timeless) | yes |
| `reading-list/<kind>.md` | Generated index of unread notes (regen with `ks_reading_list.py`) | yes |
| `raw/papers/<id>.md` | Parsed paper text (ar5iv or docling output) | yes |
| `raw/papers/<id>.pdf` | Original paper PDF | **NO** (gitignored) |
| `raw/articles/<slug>.md` | Web Clipper output | yes |
| `raw/youtube/<id>.transcript.md` | Auto-subs flattened to text | yes |
| `raw/youtube/<id>.metadata.json` | yt-dlp metadata dump | yes |
| `raw/youtube/<id>.audio.*` | Audio file | **NO** (gitignored) |
| `templates/` | Note templates | yes |

Anything large and binary lives under `raw/<kind>/` and is gitignored. The
parsed-text equivalent (always markdown) is committed and serves as recovery
insurance if the original source disappears.

## Required common-core frontmatter

Every committed file in `notes/` carries:

```yaml
---
type: note
kind: paper | article | youtube | blog | github
slug: <kebab-case>
title: <string>
created: YYYY-MM-DD
updated: YYYY-MM-DD
read: false                # drives reading-list inclusion
tags: []                   # ks_tag.py + user-curated
---
```

Reading-list pages are generated and carry:

```yaml
---
type: reading-list
kind: papers | articles | youtube | blogs | github
generated: <iso8601>
unread_count: <int>
---
```

## Per-kind frontmatter

Additive on top of the common core.

### `kind: paper`
```yaml
year: <int>
authors: [<list>]
arxiv: <id> | null         # null for books / non-arxiv
doi: <doi> | null
url: <url>                 # arxiv.org/abs/... or publisher URL
venue: <str> | null
raw_pdf: raw/papers/<id>.pdf | null
raw_md:  raw/papers/<id>.md  | null
parser:  ar5iv | docling | none
```

### `kind: article`
```yaml
year: <pub year>
url: <url>
author: <name> | null
publication: <outlet>
retrieved: YYYY-MM-DD
raw_md: raw/articles/<year>-<slug>.md
clipper: obsidian-web-clipper
```

### `kind: youtube`
```yaml
year: <upload year>
youtube_id: <id>
url: https://youtu.be/<id>
channel: <name>
channel_id: UC...
duration_seconds: <int>
upload_date: YYYY-MM-DD
raw_audio: raw/youtube/<id>.audio.m4a | null   # gitignored, slice-2 fetch
raw_transcript: raw/youtube/<id>.transcript.md
raw_metadata:   raw/youtube/<id>.metadata.json
transcript_source: yt-auto | whisper
```

### `kind: blog`
```yaml
url: <url>
author: <name> | null
description: <one sentence>
```
No raw, no recovery.

### `kind: github`
```yaml
url: https://github.com/<owner>/<repo>
description: <one sentence>
```
No API metadata, no recovery — note + URL is the artifact.

## Stable identifiers

Recovery uses these identifiers when refetching binaries:

| `kind` | Recovery key | Method |
|---|---|---|
| paper (arxiv) | `arxiv` field | re-download via arxiv |
| paper (PDF only) | `sha1(file)[:10]` (in `raw_pdf` filename) | none — local-only, warn if PDF missing |
| paper (book / no PDF) | none | none |
| article | `sha1(url)[:10]` | best-effort URL refetch |
| youtube | `youtube_id` | yt-dlp |
| blog | none | pointer only |
| github | none | note + URL is sufficient |

## Naming

- **Folders carry kind.** Don't prefix filenames with `paper-`, `article-`,
  etc.
- **Kebab-case slugs.**
- **Year prefix on dated kinds.** `paper`, `article`, `youtube` use
  `YYYY-slug.md` (publication or upload year).
- **No year prefix on bookmarks.** `blog` and `github` use just `<slug>.md`
  — these are timeless pointers.
- Avoid generic names (`notes.md`, `misc.md`).

## Core rules

1. **One note per source.** No many-to-many synthesis here. If you find
   yourself writing about multiple sources together, that prose belongs in
   your writing vault, not here.
2. **Don't commit binaries.** Anything under `raw/` that is not `*.md` or
   `*.json` is gitignored. `ks_doctor.py` flags slips.
3. **Frontmatter is load-bearing.** `type`, `kind`, `read`, `created`,
   `updated`, plus the kind-specific identifiers, must be accurate. Recovery,
   reading-list rendering, and tagging all depend on it.
4. **`read:` is a boolean, not a process.** Default `false`. Flip to `true`
   once you've processed the source. The reading list filters on this field.
5. **Recover, don't archive.** If a binary disappears, refetch with
   `recover_raw.py`. Don't unignore the gitignored path.
6. **Update `updated:`** whenever you edit a note.
7. **Don't invent metadata.** Unknown fields → `null` (or omit if optional).
   Authors, dates, venues — if not present in the source, leave blank.
8. **GitHub and blog notes are minimal.** URL + description. No API fetching,
   no stars/language tracking, no recovery.
9. **Tags drive search.** Run `ks_tag.py` on freshly-ingested notes; it adds
   2–5 tags from a controlled vocabulary plus free-form additions. Edit by
   hand whenever the suggestion is wrong.
10. **Reading-list pages are generated.** Don't hand-edit `reading-list/*.md`
    — `ks_reading_list.py` will overwrite. If you need a curated reading map,
    keep it elsewhere (your writing vault).

## Scripts

| Command (under `~/.claude/skills/knowledge-smith/scripts/`) | Purpose |
|---|---|
| `ingest_arxiv.py <id-or-url>` | Capture an arXiv paper → `notes/papers/` |
| `ingest_pdf.py <path-or-url> --title T --year Y` | Non-arXiv PDF via docling → `notes/papers/` |
| `ingest_article.py <clipper-md-path>` | Normalize Web Clipper output → `notes/articles/` |
| `ingest_youtube.py <url-or-id>` | yt-dlp metadata + auto-subs → `notes/youtube/` |
| `ingest_bookmark.py <url> [--description D]` | github or blog (auto-detected) → `notes/{github,blogs}/` |
| `ks_reading_list.py [--kind K] [--all]` | (Re)generate `reading-list/<kind>.md` |
| `ks_tag.py [--kind K] [--force] [--model haiku\|sonnet\|opus]` | LLM-suggest tags for un-tagged notes (uses `ANTHROPIC_API_KEY`) |
| `recover_raw.py [--kind K] [--dry-run]` | Refetch gitignored binaries from frontmatter |
| `ks_doctor.py [--init <path>]` | Health check; `--init` scaffolds a new vault |

For Codex, swap `~/.claude` for `~/.codex` in the path.

**First docling run** downloads ~hundreds of MB of layout/OCR models. This is
expected. Subsequent runs are fast.

## Vault discovery

Scripts find this vault by:

1. `$KNOWLEDGE_SMITH_VAULT` env var (must point to a directory containing
   `.knowledge-smith`).
2. Walking the current working directory upward for `.knowledge-smith`.
3. Otherwise the script hard-fails with an init hint.

There is **no default vault path**. Multiple vaults coexist trivially — `cd`
into the one you mean, or set the env var.

## Collaboration with agents

- Agents may write into `notes/<kind>/` and `raw/` only via the `ingest_*.py`
  scripts. Direct writes to `raw/` are forbidden.
- Agents may edit frontmatter (`read`, `tags`, `updated`, descriptions) and
  the body of a note.
- Agents may run `ks_tag.py` and `ks_reading_list.py` to keep search and the
  reading list current.
- Agents must preserve user-written prose in note bodies. Additions go in new
  sections; corrections via `## Update (YYYY-MM-DD)` blocks rather than
  silent rewrites.
- Agents must update `updated:` on every file they touch.
- Agents must not hand-edit `reading-list/*.md`. Regenerate via the script.
