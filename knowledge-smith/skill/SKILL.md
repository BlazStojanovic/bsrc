---
name: knowledge-smith
description: Capture and index research sources (papers, model cards, articles, YouTube videos, blogs, posts, GitHub repos, courses) into a knowledge-smith vault. One summary note per source, marked unread until read. Use when the user wants to add, ingest, capture, save, bookmark, remember, tag, or list a paper / arXiv ID / video / blog / repo / article URL / model card.
---

# Knowledge Smith

Index research sources into the user's active knowledge-smith vault as
**one summary note per source**. The vault is a data index, not a
synthesis tier — concept-level cross-source writing belongs elsewhere.

## When to use

Triggers: "add this paper", "save this video", "bookmark this repo",
"ingest <url>", "throw this in my knowledge base", "save the GLM-4 model
card", "tag my notes", "what's on my reading list?", a bare arXiv id
like `1706.03762`.

## Vault discovery

Scripts find the active vault by:

1. `$KNOWLEDGE_SMITH_VAULT` (must point to a directory containing
   `.knowledge-smith`)
2. Walking the cwd upward for the `.knowledge-smith` marker
3. Otherwise: hard fail with an init hint.

There is **no default vault**. Run `ks_doctor.py` to confirm which one
resolved. To start a new vault:

```
uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py --init <path>
```

## How the pipeline works

**Scripts are I/O plumbing.** They write notes + raw assets, run
subprocess fetches (httpx, pdftotext, docling, yt-dlp, whisper), and
do schema-driven validation. They do **not** derive slugs, pick parser
tiers, infer years from upload dates, scrape HTML, or assemble note
bodies.

**You — the agent — own the intelligence.** For every ingest:

1. **Identify** the source. Verify the title matches the user's request
   (catch typo'd arXiv IDs, wrong-paper API resolutions).
2. **Fetch** what you need. Use the `helpers/` CLIs (or invoke them via
   the orchestrator's built-ins).
3. **Compose the note body markdown verbatim.** Follow the matching
   `templates/<kind>-note.md` shape inside the vault.
4. **Write** by calling the orchestrator (`ingest_<kind>.py`) with
   `--metadata-json`, `--links-json`, `--body-md-path`.

Re-ingest is safe: `merge_frontmatter` preserves the existing body and
user-curated fields (`tags`, `read`, `owner`, `status`) unless `--force`.

The path for `<script>` below is `~/.claude/skills/knowledge-smith/scripts/<script>.py`
(swap `~/.claude` for `~/.codex` under Codex). Always invoke via `uv run`.

## Source-type dispatch

| Input | Script | Lands in |
|---|---|---|
| arXiv id or `arxiv.org/abs/...` | `ingest_arxiv.py` | `notes/papers/<year>-<slug>.md` |
| Local PDF or non-arXiv PDF URL | `ingest_pdf.py` | `notes/papers/<year>-<slug>.md` |
| Model card / system card / Raschka diagram source | `ingest_model_card.py` | `notes/model-cards/<year>-<slug>.md` |
| Web Clipper `.md` path | `ingest_article.py` | `notes/articles/<year>-<slug>.md` |
| `youtube.com/watch` or `youtu.be` URL | `ingest_youtube.py` | `notes/youtube/<year>-<slug>.md` |
| `github.com/owner/repo` URL | `ingest_bookmark.py --kind github` | `notes/github/<owner>-<repo>.md` |
| Course / lecture-series homepage | `ingest_bookmark.py --kind course` | `notes/courses/<slug>.md` |
| Blog homepage / newsletter / research-blog landing page | `ingest_bookmark.py --kind blog` | `notes/blogs/<slug>.md` |
| Individual blog post / web article | `ingest_bookmark.py --kind post` | `notes/posts/<slug>.md` |

## Common metadata shape

The orchestrators accept a single `--metadata-json` object plus an
optional `--links-json`. Both feed into a schema-validated frontmatter
write. The common-core fields the agent always supplies:

```jsonc
{
  "title": "...",                 // required
  "slug":  "kebab-case-stem",     // required (agent's choice)
  "year":  2024,                  // required for dated kinds
  "tags":  ["domain/llm", "scaling-laws"], // optional, additive to defaults
  "owner": "blaz"                 // optional, defaults from schema
}
```

Per-kind extensions (paper: `arxiv`/`authors`/`doi`/`venue`,
model-card: `developer`/`family`/`model_type`/`variants`/etc.,
youtube: `youtube_id`/`channel`/etc.) are documented in
`<vault>/CLAUDE.md`.

The `links` block (`source`, `paper`, `code`, `raw`) goes in
`--links-json` for clarity, e.g.:

```
--links-json '{"source":"https://arxiv.org/abs/1706.03762",
                "paper":"https://arxiv.org/abs/1706.03762"}'
```

The script auto-fills `links.raw` (wikilink to the parsed-md sibling)
and the `raw_pdf` / `raw_md` / `raw_transcript` operational paths.

## Worked example — arXiv ingest

User: *"Save the Attention Is All You Need paper, 1706.03762."*

```
1. WebFetch https://arxiv.org/abs/1706.03762
   → JSON: {title, authors, year, abstract, primary_category}.

2. Verify the title matches the user's request. Bail if it's clearly
   a different paper than they meant.

3. Compute slug = "attention-is-all-you-need". Year = 2017.
   Basename = 2017-attention-is-all-you-need.

4. Compose the note body in /tmp/note-body.md following
   <vault>/templates/paper-note.md:

      # Attention Is All You Need

      > *Vaswani, Shazeer, Parmar et al.* — NeurIPS 2017

      ## TL;DR

      (stub — fill in after reading)

      ## Abstract

      <abstract from step 1>

      ## Notes

      (your synthesis)

      ## Source

      - Raw markdown: [[raw/papers/md/2017-attention-is-all-you-need]]
      - PDF: [[raw/papers/pdf/2017-attention-is-all-you-need.pdf]]
      - arXiv: <https://arxiv.org/abs/1706.03762>

5. Write:

   ingest_arxiv.py \
     --metadata-json '{"arxiv":"1706.03762",
                       "title":"Attention Is All You Need",
                       "slug":"attention-is-all-you-need",
                       "year":2017,
                       "authors":["Ashish Vaswani","Noam Shazeer", "..."],
                       "venue":"NeurIPS 2017"}' \
     --links-json '{"source":"https://arxiv.org/abs/1706.03762",
                     "paper":"https://arxiv.org/abs/1706.03762"}' \
     --body-md-path /tmp/note-body.md
```

The script downloads the PDF + ar5iv body, fills `links.raw` and the
`raw_*` operational paths, validates against the schema, and writes the
note via `merge_frontmatter`.

## Worked example — model-card ingest

User: *"Save the DeepSeek V3 model card."*

```
1. WebFetch the source the user pointed at (paper / blog / HF card /
   Raschka diagram). Extract: developer, family, variants, license,
   model_type, parameters, key architecture choices.

2. Verify the model name matches. Bail on ambiguity (V3 vs V3.1 vs V3.2).

3. Compute slug = "deepseek-v3". Year = 2024 (release / report year).

4. Compose the note body in /tmp/note-body.md following
   <vault>/templates/model-card-note.md — fill in the Model Family
   table, Architecture table, MoE sub-table (if applicable), Key
   Architecture Choices, Training, Reported Evals (placeholders OK),
   Related, Caveats.

5. Write:

   ingest_model_card.py \
     --metadata-json '{"title":"DeepSeek V3","slug":"deepseek-v3",
                       "year":2024,"developer":"DeepSeek",
                       "family":"DeepSeek-V3","model_type":"llm",
                       "variants":["V3-Base","V3-Chat"],
                       "license":"DeepSeek-LICENSE",
                       "parameters_total":"671B (37B active)"}' \
     --links-json '{"source":"https://github.com/deepseek-ai/DeepSeek-V3",
                     "paper":"https://arxiv.org/abs/2412.19437"}' \
     --body-md-path /tmp/note-body.md
```

If you have an official PDF (system card, technical report), pass it
via `--pdf-path /path/to.pdf` — the script archives it under
`raw/model-cards/pdf/` (gitignored). Use `helpers/pdftotext.sh` or
`helpers/run_docling.py` first if you want a parsed-md sibling.

## Worked example — non-arXiv PDF

```
1. Read the PDF (Claude Read tool, pages 1-5) → title/authors/year/abstract.

2. Pick parser tier:
   - tier 1 (default): rely on metadata only; no raw body extraction.
     Skip --raw-md-path; the raw md gets a placeholder.
   - tier 2: helpers/pdftotext.sh paper.pdf > /tmp/raw.md
   - tier 3: helpers/run_docling.py paper.pdf > /tmp/raw.md
     (warn the user — first run downloads layout/OCR models, hundreds of MB)

3. Compose note body /tmp/note-body.md following templates/paper-note.md.

4. Write:

   ingest_pdf.py --pdf-path /tmp/paper.pdf \
     --metadata-json '{"title":"...","slug":"...","year":2024,
                       "authors":[...],"venue":"..."}' \
     --links-json '{"source":"https://...","paper":"https://..."}' \
     --body-md-path /tmp/note-body.md \
     [--raw-md-path /tmp/raw.md --parser pdftotext]
```

## Worked example — YouTube

```
1. Bash: yt-dlp -j https://youtu.be/<id> > /tmp/<id>.metadata.json
   Parse metadata for title, channel, channel_id, duration, upload_date.

2. Pick transcription path:
   - whisper (default for substantive content):
       Bash: yt-dlp -x --audio-format mp3 -o "/tmp/<id>.audio.%(ext)s" https://youtu.be/<id>
       Bash: helpers/transcribe.sh /tmp/<id>.audio.mp3 > /tmp/<id>.transcript.md
   - yt-auto (fast / low quality):
       Bash: yt-dlp --write-auto-subs --skip-download --sub-format vtt --sub-langs en \
                    -o "/tmp/<id>" https://youtu.be/<id>
       Bash: helpers/vtt_flatten.py /tmp/<id>.en.vtt > /tmp/<id>.transcript.md
   - none: skip

3. Compose note body /tmp/note-body.md following templates/youtube-note.md.

4. Write:

   ingest_youtube.py \
     --metadata-json '{"youtube_id":"<id>","title":"...","slug":"...",
                       "year":2024,"channel":"...","channel_id":"UC...",
                       "duration_seconds":1234,"upload_date":"2024-05-01"}' \
     --links-json '{"source":"https://youtu.be/<id>"}' \
     --transcript-path /tmp/<id>.transcript.md \
     --transcript-source whisper \
     --metadata-path /tmp/<id>.metadata.json \
     --body-md-path /tmp/note-body.md
```

## Worked example — bookmarks (blog / post / github / course)

```
1. Detect kind:
   - github.com/<owner>/<repo>             → kind=github
   - course / lecture-series homepage      → kind=course
   - blog homepage (root URL of a source)  → kind=blog
   - specific article (URL with a path)    → kind=post

2. WebFetch the URL for title/author/description (skip for github —
   parse owner/repo from the URL yourself, no API call).

3. Compose note body /tmp/note-body.md following the matching template.

4. Write:

   # github
   ingest_bookmark.py --kind github \
     --metadata-json '{"title":"openai/whisper","slug":"openai-whisper",
                       "owner":"openai","repo":"whisper",
                       "description":"Robust speech recognition"}' \
     --links-json '{"source":"https://github.com/openai/whisper",
                     "code":"https://github.com/openai/whisper"}'

   # blog
   ingest_bookmark.py --kind blog \
     --metadata-json '{"title":"Eugene Yan","slug":"eugene-yan",
                       "author":"Eugene Yan",
                       "description":"Applied ML / recsys."}' \
     --links-json '{"source":"https://eugeneyan.com/"}'

   # post
   ingest_bookmark.py --kind post \
     --metadata-json '{"title":"Evaluating LLM-Evaluators",
                       "slug":"llm-evaluators","year":2024,
                       "author":"Eugene Yan","source":"Eugene Yan",
                       "description":"..."}' \
     --links-json '{"source":"https://eugeneyan.com/writing/llm-evaluators/"}'

   # course
   ingest_bookmark.py --kind course \
     --metadata-json '{"title":"CS336","slug":"cs336",
                       "instructor":"Percy Liang & Tatsunori Hashimoto",
                       "institution":"Stanford","year":2024,
                       "description":"Hands-on LLM course."}' \
     --links-json '{"source":"https://stanford-cs336.github.io/spring2024/"}'
```

## Composing the body

Read `<vault>/templates/<kind>-note.md` once per session to see the
canonical shape. Then assemble the body for each ingest yourself —
filling in the title, citation line, TL;DR, body sections, and the
Source block. Aim for these always:

- A `# <Title>` H1 first.
- A `> *<authors / channel / instructor>* — <venue / publication / year>`
  citation hint immediately under the H1.
- `## TL;DR` (a stub if you haven't read it yet — do not invent content).
- `## Notes` (empty unless the user is asking you to add synthesis).
- `## Source` block with wikilinks to the raw artifacts the script
  produced.

For model-cards specifically: fill in the Model Family + Architecture
tables verbatim from the source. Use `[needs verification]` literally for
fields not disclosed; the user wants to grep for those later.

## Helpers — composable building blocks

Every helper is a standalone CLI under `~/.claude/skills/knowledge-smith/scripts/helpers/`:

| Helper | Purpose |
|---|---|
| `download_pdf.py [--arxiv ID] URL DEST` | Stream a PDF to DEST (atomic) |
| `fetch_ar5iv.py <id>` | Print ar5iv-rendered markdown for an arXiv id |
| `pdftotext.sh [--layout] PDF` | Quick PDF→text (poppler) |
| `run_docling.py PDF` | High-fidelity PDF→markdown (heavy first run) |
| `vtt_flatten.py VTT` | Flatten WebVTT auto-subs into prose |
| `transcribe.sh AUDIO` | Whisper transcription (local model) |
| `clipper_copy.py SRC DEST` | Copy a Web Clipper file into raw/articles/ |

The orchestrators wrap these for the canonical flow; reach for the
helpers directly when you want piecewise control.

## Reading list

```
uv run ~/.claude/skills/knowledge-smith/scripts/ks_reading_list.py --all
uv run ~/.claude/skills/knowledge-smith/scripts/ks_reading_list.py --kind paper
```

Generates `reading-list/<kind>.md` listing every `read: false` note for
that kind. Dated kinds (paper/model-card/article/youtube) are grouped
by year, descending; blog/post/github/course are flat lists.
Regenerate after any ingest or read-flip.

## Tagging — agent-driven (subagents return tags)

`ks_tag.py` does the I/O only. The LLM call is **your** responsibility
as the orchestrating agent: spawn sonnet subagents in parallel, collect
their JSON output, and write it back via the script. No external API
key needed.

Step-by-step (when the user asks to tag, retag, or "make notes
searchable"):

1. **List untagged notes:**
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ks_tag.py list --kind paper > /tmp/ks-tag-plan.jsonl
   ```
   Output begins with a `# vocab: t1, t2, ...` comment header (the
   controlled vocabulary; vault may override via
   `<vault>/.ks-tag-vocab`), followed by one JSON object per untagged
   note: `{"file": "/abs/path.md", "kind": "paper", "slug": "...",
   "title": "...", "year": YYYY, "abstract": "..."}`

2. **Read the plan**, parse the vocab, parse the JSONL.

3. **Batch into groups of 15–20 papers.**

4. **Dispatch parallel subagents** — one Agent tool call per batch, all
   in a single message so they run concurrently. Use:
   - `subagent_type: "general-purpose"`
   - `model: "sonnet"`
   - prompt template:
     ```
     You are tagging research sources for a knowledge-smith vault.

     CONTROLLED VOCABULARY (prefer these — only invent free-form tags
     when none of these fit):
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

5. **Parse** each subagent's JSON-lines response.

6. **Apply tags** — one `apply` call per note:
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ks_tag.py apply /abs/path.md tag1 tag2 tag3
   ```

7. **Refresh the reading list:**
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ks_reading_list.py --all
   ```

For a quick sanity check, pass `--limit 3` to `list` and tag just three
papers first.

## Recovery

After a fresh clone, gitignored binaries (PDFs, audio) are missing.
Run:

```
uv run ~/.claude/skills/knowledge-smith/scripts/recover_raw.py
```

Walks `notes/<kind>/` and refetches `raw_pdf` for arxiv papers. GitHub
and blog notes are never recovered — the note + URL is the artifact.

## Inspecting and migrating

```
uv run ~/.claude/skills/knowledge-smith/scripts/ks_doctor.py
```

Reports vault root, schema sources, per-kind counts (total + unread),
schema-driven frontmatter validation, orphan raws, stale binary refs,
reading-list freshness, top tags.

For older vaults using flat `url:`/`arxiv:` fields and missing
`owner:`/`links:`:

```
uv run ks_doctor.py --migrate --dry-run    # preview
uv run ks_doctor.py --migrate              # apply
uv run ks_doctor.py --migrate --kind paper # one kind only
```

Idempotent: lifts `url`→`links.source`, `arxiv`→`links.paper`,
`raw_pdf`→`links.raw`, injects `owner: blaz`, prepends `type/<kind>`
namespaced tag, converts `read/read|unread` tags into the `read:`
boolean.

## Schema

Authoritative spec lives in `<vault>/CLAUDE.md`. The data-driven
schema is at
`bsrc/knowledge-smith/skill/scripts/_ks_schema.yaml` (default), with
per-vault override at `<vault>/.ks-schema.yaml`. Read both before
generating files. Common-core fields (`type`, `kind`, `slug`, `title`,
`created`, `updated`, `read`, `owner`, `tags`, `links`) plus per-`kind`
extensions.

## Conventions

- **Paper notes always carry a PDF wikilink.** Every
  `notes/papers/<stem>.md` has a Source-section line like
  `- PDF: [[raw/papers/pdf/<stem>.pdf]]`, even when the PDF isn't on
  disk (book stubs, failed downloads). The unresolved link is
  intentional — the user can drop a PDF at the canonical path later.
- **`raw/papers/` and `raw/model-cards/` are split.** `.md` text lives
  at `raw/<plural>/md/<stem>.md` (committed); `.pdf` binaries at
  `raw/<plural>/pdf/<stem>.pdf` (gitignored).
- **`links` block first, flat fields second.** When both exist, the
  `links` block is canonical. `ks_doctor --migrate` collapses the old
  shape into the new.
- **`read:` boolean is the source of truth.** Legacy `read/unread` and
  `read/read` tags are obsolete; `ks_doctor --migrate` strips them.

## Don'ts

- **Do not invent metadata.** If a fetch step fails (WebFetch returns
  garbage, yt-dlp errors, PDF unreadable), surface the failure to the
  user — never fall back to filename-derived guesses.
- **Verify titles** against the user's request before writing. The most
  common bug class (typo'd arxiv ID → wrong paper resolved → wrong
  note filed) is caught here.
- **Never invent slugs.** The agent picks the slug deterministically
  from the canonical title; do not accept the script silently choosing
  one for you (it won't — scripts hard-fail on missing `slug`).
- Do not write under `raw/` by hand. Always go through the scripts or
  the helpers/ CLIs.
- Do not commit binaries. The vault `.gitignore` is the source of truth.
- Do not hand-edit `reading-list/<kind>.md` —
  `ks_reading_list.py` overwrites.
- Do not fetch GitHub API metadata. Github bookmarks stay minimal.
- Do not assume a default vault path. If discovery fails, ask the user.

## System dependencies

Installed by `bsrc/knowledge-smith/install.sh`:

- `uv` — PEP 723 script runner
- `poppler` — `pdftotext` for tier-2 PDF body extraction
- `ffmpeg` — audio resampling for whisper
- `whisper-cpp` — local YouTube transcription
- `yt-dlp` — YouTube metadata + audio fetch
- Whisper `ggml-base.en.bin` model in `~/.cache/whisper/`

The Python scripts declare their own PEP 723 deps (httpx, markdownify,
python-frontmatter, pyyaml) — `uv` resolves them on first invocation.
