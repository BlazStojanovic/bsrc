# Working rules for this knowledge-smith vault

Read this before editing anything in the vault.

## Purpose

This vault is the **indexing tier** of a personal research knowledge base.
It captures sources from many channels (papers, web articles, YouTube videos,
blog pointers, GitHub repos) and turns them into concept-level synthesis
notes that compound over time.

Three kinds of artifact live here:

- **Sources** (`sources/<kind>/`) — one file per source. Immutable facts about
  a paper / article / video / bookmark, plus a brief summary. Linked to raw
  content under `raw/`.
- **Notes** (`notes/`) — concept-oriented synthesis. A note can pull from
  many sources; a source can be indexed into many notes. Many-to-many.
- **Topics** (`topics/`) — user-curated reading maps and taxonomy.

`inbox/` is transient. Fresh ingests land there with `status: captured` until
the user/agent decides to register them under `sources/<kind>/`.

The vault is markdown only. The frontend is Obsidian. Tooling lives outside
the vault (in `bsrc/`) and is invoked via the knowledge-smith skill.

## Pipeline

```
[arxiv | PDF | Web Clipper | YouTube | github | blog]
                 │
                 ▼
              inbox/                  status: captured
                 │
                 ▼   (user/agent decides to keep)
        sources/<kind>/<slug>.md      status: registered
                 │
                 ▼   (user/agent extracts concepts)
            notes/<slug>.md           status: stub | active
                 │
                 ▼   (organic taxonomy)
            topics/<slug>.md          (user-curated reading maps)
```

A source can be registered without ever being indexed (still useful — it's
a searchable record). A note can stay a stub until a second source corroborates
or contests it.

## Folder roles

| Folder | Role | Committed? |
|---|---|---|
| `inbox/` | Transient — newly ingested sources awaiting registration | yes (md only) |
| `sources/papers/` | Registered paper sources | yes |
| `sources/articles/` | Registered web articles | yes |
| `sources/youtube/` | Registered YouTube videos | yes |
| `sources/blogs/` | Lightweight blog bookmarks | yes |
| `sources/github/` | Lightweight GitHub repo bookmarks | yes |
| `notes/` | Concept-oriented synthesis (flat, cross-source) | yes |
| `topics/` | Reading maps and taxonomy (user-curated only) | yes |
| `raw/papers/<id>.md` | Parsed paper text (ar5iv or docling) | yes |
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

Every file in `inbox/`, `sources/`, `notes/`, and `topics/` carries:

```yaml
---
type: source | note | topic
status: captured | registered | indexed | active | archived
slug: <kebab-case>
title: <string>
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
---
```

`status` progression:
- `captured` — fresh in `inbox/`, not yet decided.
- `registered` — promoted to `sources/<kind>/`, not yet referenced from a note.
- `indexed` — registered AND referenced from at least one `notes/` file.
- `active` — for notes / topics actively being maintained.
- `archived` — superseded or no longer relevant; kept for history.

## Per-type frontmatter

### `type: source` (additive on top of common core)

```yaml
source_kind: paper | article | youtube | blog | github
id: <stable identifier>     # see Stable identifiers below
indexed_in: []              # ["[[notes/<slug>]]", ...]; agent maintains
```

Then one of the following kind-specific blocks:

#### `source_kind: paper`
```yaml
arxiv: 1706.03762           # null if PDF-only
doi: null
url: https://arxiv.org/abs/1706.03762
authors: ["Vaswani A.", "Shazeer N.", "Parmar N."]
year: 2017
venue: NeurIPS              # null OK
raw_pdf: raw/papers/1706.03762.pdf       # gitignored
raw_md:  raw/papers/1706.03762.md        # committed
parser:  ar5iv | docling | ar5iv-failed
```

#### `source_kind: article`
```yaml
url: https://example.com/post
author: Jane Doe            # null OK
publication: Some Substack
retrieved: YYYY-MM-DD
raw_md: raw/articles/<year>-<slug>.md
clipper: obsidian-web-clipper
```

#### `source_kind: youtube`
```yaml
youtube_id: dQw4w9WgXcQ
url: https://youtu.be/dQw4w9WgXcQ
channel: Channel Name
channel_id: UC...
duration_seconds: 218
upload_date: YYYY-MM-DD
raw_audio:      raw/youtube/<id>.audio.m4a       # gitignored
raw_transcript: raw/youtube/<id>.transcript.md   # committed
raw_metadata:   raw/youtube/<id>.metadata.json   # committed
transcript_source: yt-auto | whisper
```

#### `source_kind: blog` (aggregate-level pointer)
```yaml
url: https://somesubstack.com/
author: Person Name         # null OK
description: <one sentence>
# no raw_*, no recovery
```

#### `source_kind: github` (minimal bookmark)
```yaml
url: https://github.com/owner/repo
description: <one sentence>
# no API metadata, no recovery — note + URL is the artifact
```

### `type: note` (concept synthesis)

```yaml
type: note
status: stub | active | archived
slug: <kebab-case>
title: <string>
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: ["[[sources/papers/2017-attention-is-all-you-need]]", ...]
tags: []
topics: ["[[transformers]]"]    # backlinks to topics/<slug>.md
```

Body: free-form markdown synthesis with `[[wikilinks]]` to sources and
inline citations.

### `type: topic` (reading map)

```yaml
type: topic
status: active
slug: <kebab-case>
title: <string>
description: <one sentence>
created: YYYY-MM-DD
updated: YYYY-MM-DD
```

Body: user-curated map with `[[wikilinks]]` to notes and sources, organized
by sub-theme.

## Stable identifiers

The `id:` field on each source is what `recover_raw.py` uses (where applicable)
to refetch missing binaries.

| `source_kind` | `id:` value | Recovery method |
|---|---|---|
| paper (arxiv) | arxiv id (e.g. `1706.03762`) | re-download via arxiv |
| paper (PDF only) | `sha1(file)[:10]` | none — local-only, warn if PDF missing |
| article | `sha1(url)[:10]` | best-effort URL refetch |
| youtube | `youtube_id` | yt-dlp |
| blog | `sha1(url)[:10]` | none — pointer only |
| github | `<owner>-<repo>` | **none** — note + URL is sufficient |

## Naming

- **Folders carry kind.** Don't prefix filenames with `paper-`, `article-`,
  etc.
- **Kebab-case slugs.**
- **Year prefix on dated kinds.** `paper`, `article`, `youtube` files use
  `YYYY-slug.md` (publication or upload year).
- **No year prefix on bookmarks.** `blog` and `github` files use just `<slug>.md`
  — these are timeless pointers.
- **Notes and topics**: bare slug, no year.
- Avoid generic names (`notes.md`, `misc.md`).

## Core rules

1. **Don't commit binaries.** Anything under `raw/` that is not `*.md` or
   `*.json` is gitignored. If a binary slipped past, `ks_doctor.py` flags it.
2. **Frontmatter is load-bearing.** `type`, `status`, `id`, `created`, and
   `updated` must be accurate. Recovery and reporting depend on it.
3. **`inbox/` is transient.** Promote with `mv inbox/<f>.md sources/<kind>/`
   and bump `status:` from `captured` to `registered`.
4. **One source per file in `sources/`. One concept per file in `notes/`.**
   If a note starts describing two concepts, split it.
5. **Recover, don't archive.** If a binary disappears, refetch with
   `recover_raw.py`. Don't unignore the gitignored path to "preserve" it.
6. **Topics are user-curated.** Scripts never write into `topics/`. Agents
   suggest, the user decides.
7. **Update `updated:`** whenever you edit a note.
8. **Don't invent metadata.** Unknown fields → `null` (or omit if optional).
   Authors, dates, venues — if not present in the source, leave blank.
9. **GitHub sources are minimal.** URL + description. The note + URL is the
   artifact; no API fetching, no stars/language tracking, no recovery.
10. **Concept notes pull from many sources.** Maintain both directions:
    `sources:` on the note, `indexed_in:` on each source. `ks_doctor.py`
    flags one-sided links.

## Scripts

| Command (under `~/.claude/skills/knowledge-smith/scripts/`) | Purpose |
|---|---|
| `ingest_arxiv.py <id-or-url>` | Capture an arXiv paper (metadata + ar5iv md + PDF) |
| `ingest_pdf.py <path-or-url> --title T --year Y` | Non-arXiv PDF via docling |
| `ingest_article.py <clipper-md-path>` | Normalize a Web Clipper output file |
| `ingest_youtube.py <url-or-id>` | yt-dlp metadata + auto-subs (no Whisper in slice 1) |
| `ingest_bookmark.py <url> [--description D]` | github or blog (auto-detected) |
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

- Agents may write into `inbox/` and `raw/` only via the `ingest_*.py` scripts.
  Direct writes to `raw/` are forbidden.
- Agents may move files from `inbox/` to `sources/<kind>/` and edit
  frontmatter (`status`, `tags`, `indexed_in`).
- Agents may create `notes/<slug>.md` when discussing concepts that synthesize
  across sources, after surfacing the proposal to the user.
- Agents must not auto-create `topics/` pages without user input.
- Agents must preserve user-written prose in `sources/`, `notes/`, and
  `topics/`. Additions go in new sections; corrections via
  `## Update (YYYY-MM-DD)` blocks rather than silent rewrites.
- Agents must update `updated:` on every file they touch.
