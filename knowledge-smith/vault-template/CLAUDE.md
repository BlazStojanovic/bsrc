# Working rules for this knowledge-smith vault

Read this before editing anything in the vault.

## Purpose

This vault is the **indexing tier** of a personal research knowledge base.
It captures sources from many channels (papers, model cards, web articles,
YouTube videos, blog pointers, posts, GitHub repos, courses) and stores
**one summary note per source** — 1-to-1, never many-to-many.

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
[arxiv | model card | PDF | Web Clipper | YouTube | github | blog | post]
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
| `notes/papers/<year>-<slug>.md`        | Paper summary notes | yes |
| `notes/model-cards/<year>-<slug>.md`   | Model architecture / system-card snapshot notes | yes |
| `notes/articles/<year>-<slug>.md`      | Web-article summary notes | yes |
| `notes/youtube/<year>-<slug>.md`       | YouTube-video summary notes | yes |
| `notes/blogs/<slug>.md`                | Source-level blog bookmarks | yes |
| `notes/posts/<slug>.md`                | Individual blog-post / web-article bookmarks | yes |
| `notes/github/<owner>-<repo>.md`       | GitHub bookmarks (timeless) | yes |
| `notes/courses/<slug>.md`              | Course / lecture-series bookmarks (timeless) | yes |
| `reading-list/<kind>.md`               | Generated index of unread notes | yes |
| `raw/papers/md/<year>-<slug>.md`       | Parsed paper text (ar5iv / pdftotext / docling) | yes |
| `raw/papers/pdf/<year>-<slug>.pdf`     | Original paper PDF | **NO** (gitignored) |
| `raw/model-cards/md/<year>-<slug>.md`  | Parsed text of model cards / system cards | yes |
| `raw/model-cards/pdf/<year>-<slug>.pdf`| Original model/system card PDF | **NO** (gitignored) |
| `raw/articles/<year>-<slug>.md`        | Web Clipper output | yes |
| `raw/youtube/<id>.transcript.md`       | Auto-subs / whisper transcript | yes |
| `raw/youtube/<id>.metadata.json`       | yt-dlp metadata dump | yes |
| `raw/youtube/<id>.audio.*`             | Audio file | **NO** (gitignored) |
| `templates/`                           | Note templates | yes |

Anything large and binary lives under `raw/<kind>/` and is gitignored. The
parsed-text equivalent (always markdown) is committed and serves as recovery
insurance if the original source disappears.

## Required common-core frontmatter

Every committed file in `notes/` carries:

```yaml
---
type: note
kind: paper | model-card | article | youtube | blog | post | github | course
slug: <kebab-case>
title: <string>
created: YYYY-MM-DD
updated: YYYY-MM-DD
read: false                # boolean — drives reading-list inclusion
owner: blaz                # who curates this note
tags: [type/<kind>, status/<x>, domain/<x>, ...]   # namespaced
links:
  source: <canonical URL the user passed>
  paper:  <arxiv-or-doi-url> | null     # paper kinds
  code:   <repo-url> | null             # github / model-card kinds
  raw:    <wikilink-or-path> | null     # to the parsed raw asset
---
```

Reading-list pages are generated and carry:

```yaml
---
type: reading-list
kind: papers | model-cards | articles | youtube | blogs | posts | github | courses
generated: <iso8601>
unread_count: <int>
---
```

## Per-kind frontmatter

Additive on top of the common core. The schema lives at
`bsrc/knowledge-smith/skill/scripts/_ks_schema.yaml` (default). Override
per-vault by writing your own `<vault>/.ks-schema.yaml` — only the keys
you want to change; the merge is recursive.

### `kind: paper`
```yaml
year: <int>
authors: [<list>]
arxiv: <id> | null
doi: <doi> | null
venue: <str> | null
parser: ar5iv | docling | pdftotext | read | none
raw_pdf: raw/papers/pdf/<year>-<slug>.pdf | null
raw_md:  raw/papers/md/<year>-<slug>.md
links.paper required.
```

### `kind: model-card`
```yaml
year: <int>                        # release / report year
developer: <org or lab>
family: <model family name>
variants: [<flagship>, <small>, ...]
license: <license id or url>
model_type: llm | multimodal | system-card | world-model | vision | ...
parameters_total:  "<671B>" | null
parameters_active: "<37B>"  | null
raw_pdf: raw/model-cards/pdf/<year>-<slug>.pdf | null
raw_md:  raw/model-cards/md/<year>-<slug>.md   | null
links.source required.
```

Body shape is **architecture-rich**: Model Family table, Architecture
table (with optional MoE sub-table), Key Architecture Choices, Training,
Reported Evals, Related, Caveats. See `templates/model-card-note.md`.

### `kind: article`
```yaml
year: <pub year>
author: <name> | null
publication: <outlet>
retrieved: YYYY-MM-DD
clipper: obsidian-web-clipper
raw_md: raw/articles/<year>-<slug>.md
links.source required.
```

### `kind: youtube`
```yaml
year: <upload year>
youtube_id: <id>
channel: <name>
channel_id: UC...
duration_seconds: <int>
upload_date: YYYY-MM-DD
transcript_source: yt-auto | whisper | human | none
raw_audio: raw/youtube/<id>.audio.mp3 | null   # gitignored
raw_transcript: raw/youtube/<id>.transcript.md
raw_metadata:   raw/youtube/<id>.metadata.json
links.source required.
```

### `kind: blog`
A *source* you follow — a blog homepage / newsletter / research-blog
landing page (e.g. `eugeneyan.com`, `transformer-circuits.pub`).
```yaml
author: <name> | null
description: <one sentence>
links.source required (homepage URL).
```
No raw, no recovery. Use `kind: post` for an individual article.

### `kind: post`
An *individual* blog post or web article. Treated as a timeless
bookmark (no year prefix on filename), though `year` may be filled in
when the post date is known.
```yaml
year: <int> | null
author: <name> | null
source: <publication or blog title> | null
description: <one sentence>
links.source required (article URL).
```

### `kind: github`
```yaml
description: <one sentence>
links.source required (repo URL).
links.code typically mirrors links.source.
```

### `kind: course`
```yaml
year: <int> | null               # offering year
instructor: <name(s)> | null
institution: <university / school> | null
description: <one sentence>
links.source required (homepage URL).
```

## Tag conventions

Tags are namespaced strings (`type/...`, `status/...`, `read/...`,
`domain/...`, `model-type/...`). Default tags injected at ingest:

| Kind | Default tags |
|---|---|
| paper      | `type/paper, status/stub` |
| model-card | `type/model-card, status/stub, domain/models` |
| article    | `type/article, status/stub` |
| youtube    | `type/youtube, status/stub` |
| blog       | `type/blog, status/stub` |
| post       | `type/post, status/stub` |
| github     | `type/github, status/stub` |
| course     | `type/course, status/stub` |

Free-form tags are allowed in addition. `ks_tag.py` adds 2-5 specific
topical tags from the controlled vocabulary at `<vault>/.ks-tag-vocab`
(or the default vocab in `_ks_common.py` if the file is absent).

The **`read:` boolean** is the source of truth for reading-list filtering.
Older `read/unread` and `read/read` tags are obsolete; `ks_doctor --migrate`
strips them when it sees them.

## Stable identifiers

Recovery uses these identifiers when refetching binaries:

| `kind` | Recovery key | Method |
|---|---|---|
| paper (arxiv) | `arxiv` field | re-download via arxiv |
| paper (PDF only) | `<year>-<slug>` (in `raw_pdf` filename) | none — local-only |
| model-card | `<year>-<slug>` (in `raw_pdf`) | none — local-only |
| article | `links.source` | best-effort URL refetch |
| youtube | `youtube_id` | yt-dlp |
| blog | none | pointer only |
| post | none | pointer only |
| github | none | note + URL is sufficient |
| course | none | note + URL is sufficient |

## Naming

- **Folders carry kind.** Don't prefix filenames with `paper-`, etc.
- **Kebab-case slugs.**
- **Year prefix on dated kinds.** `paper`, `model-card`, `article`,
  `youtube` use `YYYY-slug.md` (publication / upload / release year).
- **No year prefix on bookmarks.** `blog`, `post`, `github`, `course`
  use just `<slug>.md`.
- Avoid generic names (`notes.md`, `misc.md`).

## Core rules

1. **One note per source.** No many-to-many synthesis here. If you find
   yourself writing about multiple sources together, that prose belongs in
   your writing vault, not here.
2. **Don't commit binaries.** Anything under `raw/` that is not `*.md` or
   `*.json` is gitignored. `ks_doctor.py` flags slips.
3. **Frontmatter is load-bearing.** `type`, `kind`, `read`, `created`,
   `updated`, `owner`, `links`, plus the kind-specific identifiers, must
   be accurate. Recovery, reading-list rendering, validation, and tagging
   all depend on it.
4. **`read:` is a boolean, not a process.** Default `false`. Flip to
   `true` once you've processed the source. The reading list filters on
   this field.
5. **Recover, don't archive.** If a binary disappears, refetch with
   `recover_raw.py`. Don't unignore the gitignored path.
6. **Update `updated:`** whenever you edit a note (the ingest scripts
   handle this automatically via `merge_frontmatter`).
7. **Don't invent metadata.** Unknown fields → `null` (or omit if optional).
   Authors, dates, venues — if not present in the source, leave blank.
8. **GitHub and blog notes are minimal.** URL + description. No API
   fetching, no stars/language tracking, no recovery.
9. **Tags drive search.** Run `ks_tag.py` on freshly-ingested notes; it
   adds 2–5 tags from a controlled vocabulary plus free-form additions.
   Edit by hand whenever the suggestion is wrong.
10. **Reading-list pages are generated.** Don't hand-edit
    `reading-list/*.md` — `ks_reading_list.py` will overwrite.
11. **Paper notes always carry a PDF wikilink** in the body's Source
    section: `- PDF: [[raw/papers/pdf/<stem>.pdf]]`, even when the PDF
    isn't on disk. The unresolved link is intentional — the user can
    drop a PDF at the canonical path later.

## Schema

The schema is data-driven. Default at
`bsrc/knowledge-smith/skill/scripts/_ks_schema.yaml`; per-vault override
at `<vault>/.ks-schema.yaml`. Both `ks_doctor` and the ingest scripts
load it. Extend by adding new kinds or new fields under `kinds.<kind>.optional`.

## Scripts

All ingest scripts take metadata via `--metadata-json '<json>'`. The
agent extracts metadata first; the script is I/O plumbing. The agent
also supplies the rendered note body via `--body-md-path` (or omits to
write a stub). See `SKILL.md` for the per-kind agent workflows.

| Command (under `~/.claude/skills/knowledge-smith/scripts/`) | Purpose |
|---|---|
| `ingest_arxiv.py --metadata-json '<json>' [--body-md-path P]`        | Capture an arXiv paper → `notes/papers/` |
| `ingest_pdf.py --metadata-json '<json>' --pdf-path P [--raw-md-path R --parser TIER]` | Non-arXiv PDF → `notes/papers/` |
| `ingest_model_card.py --metadata-json '<json>' [--pdf-path P --body-md-path B]` | Model architecture / system card → `notes/model-cards/` |
| `ingest_article.py --metadata-json '<json>' --clipper-path P` | Web Clipper article → `notes/articles/` |
| `ingest_youtube.py --metadata-json '<json>' [--transcript-path T --transcript-source S]` | YouTube → `notes/youtube/` |
| `ingest_bookmark.py --kind {blog,post,github,course} --metadata-json '<json>'` | Bookmark → `notes/{blogs,posts,github,courses}/` |
| `ks_reading_list.py [--kind K] [--all]` | (Re)generate `reading-list/<kind>.md` |
| `ks_tag.py list/apply` | I/O plumbing for subagent-driven tagging |
| `recover_raw.py [--kind K] [--dry-run]` | Refetch gitignored binaries from frontmatter |
| `ks_doctor.py [--init <path>] [--migrate [--dry-run] [--kind K]]` | Health check / scaffold / migrate |

Helpers under `helpers/` are composable building blocks the agent can
invoke directly: `download_pdf.py`, `fetch_ar5iv.py`, `pdftotext.sh`,
`run_docling.py`, `vtt_flatten.py`, `transcribe.sh`, `clipper_copy.py`.

For Codex, swap `~/.claude` for `~/.codex` in the path.

## Vault discovery

Scripts find this vault by:

1. `$KNOWLEDGE_SMITH_VAULT` env var (must point to a directory containing
   `.knowledge-smith`).
2. Walking the current working directory upward for `.knowledge-smith`.
3. Otherwise the script hard-fails with an init hint.

There is **no default vault path**. Multiple vaults coexist trivially —
`cd` into the one you mean, or set the env var.

## Collaboration with agents

- Agents may write into `notes/<kind>/` and `raw/` only via the
  `ingest_*.py` scripts. Direct writes to `raw/` are forbidden.
- Agents may edit frontmatter (`read`, `tags`, `updated`, descriptions,
  `links`) and the body of a note.
- Agents may run `ks_tag.py`, `ks_reading_list.py`, and
  `ks_doctor.py --migrate` to keep search, reading-list, and schema
  conformance current.
- Agents must preserve user-written prose in note bodies. Additions go in
  new sections; corrections via `## Update (YYYY-MM-DD)` blocks rather
  than silent rewrites. `merge_frontmatter` already preserves the body
  on re-ingest unless `--force`.
- Agents must update `updated:` on every file they touch (handled by the
  ingest scripts automatically).
- Agents must not hand-edit `reading-list/*.md`. Regenerate via the script.
