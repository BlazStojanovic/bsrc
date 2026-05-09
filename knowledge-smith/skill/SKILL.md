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

## How the pipeline works

**Scripts are I/O plumbing.** They write notes + raw assets given
already-extracted metadata as JSON. They don't fetch, parse, or judge.

**You — the agent — own metadata extraction.** For each ingest:

1. **Fetch** the source with the right tool (WebFetch / Read / Bash).
2. **Extract** title, authors, year, abstract, etc. — whatever the kind needs.
3. **Verify** the extracted title matches the user's request (catch typo'd
   IDs, wrong-paper API resolutions, etc.) before writing.
4. **Call** the ingest script with `--metadata-json` carrying your JSON.

The path for `<script>` below is `~/.claude/skills/knowledge-smith/scripts/<script>.py`
(swap `~/.claude` for `~/.codex` under Codex). Always invoke via `uv run`.

## Source-type dispatch

| Input | Script | Lands in |
|---|---|---|
| arXiv id or `arxiv.org/abs/...` | `ingest_arxiv.py` | `notes/papers/<year>-<slug>.md` |
| Local PDF or non-arXiv PDF URL | `ingest_pdf.py` | `notes/papers/<year>-<slug>.md` |
| Web Clipper `.md` path | `ingest_article.py` | `notes/articles/<year>-<slug>.md` |
| `youtube.com/watch` or `youtu.be` URL | `ingest_youtube.py` | `notes/youtube/<year>-<slug>.md` |
| `github.com/owner/repo` URL | `ingest_bookmark.py --kind github` | `notes/github/<owner>-<repo>.md` |
| Any other web URL | `ingest_bookmark.py --kind blog` | `notes/blogs/<slug>.md` |

## How to ingest — arXiv

For input like `1706.03762`, `https://arxiv.org/abs/1706.03762`, or
`arxiv.org/pdf/1706.03762`:

1. **Fetch metadata** (different host than the rate-limited API):
   ```
   WebFetch:
     url: https://arxiv.org/abs/<id>
     prompt: "Return JSON with keys: title (string),
              authors (list of full names), year (int),
              abstract (full paragraph), primary_category (string).
              No commentary, JSON only."
   ```

2. **Verify the title** matches the user's intent. If they said "the
   Hopular paper" and you got "Hopular: Modern Hopfield Networks for
   Tabular Data" — proceed. If you got something unrelated, the ID is
   probably wrong; ask the user to confirm before writing.

3. **Run the ingest script**:
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ingest_arxiv.py \
     --metadata-json '{"arxiv":"<id>","title":"...","authors":[...],"year":...,
                       "abstract":"...","url":"https://arxiv.org/abs/<id>"}'
   ```

4. The script downloads the PDF + ar5iv body. Surface the new note path.

## How to ingest — PDF (non-arxiv)

For a local PDF or non-arXiv PDF URL:

1. **Fetch metadata** by reading the PDF directly:
   ```
   Read:
     file_path: /path/to/paper.pdf
     pages: "1-5"
   ```
   Extract title, authors, year, abstract from the first pages.

2. **Decide the body extraction tier:**
   - **Tier 1 (default)** — metadata only. The note's `## Abstract`
     section gets what you saw via `Read`; no full-body markdown
     written. Cheapest.
   - **Tier 2** — quick body via `pdftotext`. Run
     `Bash("pdftotext '/path/to/paper.pdf' /tmp/body.txt")` first, then
     pass `--body-md-path /tmp/body.txt` to the script.
   - **Tier 3** — high-fidelity via docling. Pass `--docling`. Warn the
     user first: first run pulls hundreds of MB of layout/OCR models.
     Only worth it for PDFs with rich tables/figures the user cares about.

3. **Run the ingest script**:
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ingest_pdf.py \
     --metadata-json '{"title":"...","authors":[...],"year":...,"abstract":"..."}' \
     --pdf-path /path/to/paper.pdf [--body-md-path /tmp/body.txt | --docling]
   ```

   For URL inputs use `--pdf-url <url>` instead of `--pdf-path`.

## How to ingest — article (Web Clipper)

For a Web Clipper `.md` file path:

1. **Read the clipper file** (frontmatter holds url/title/author; body
   is the article prose).

2. **Extract** title, url, author, publication, year from the
   frontmatter. **Distill a real TL;DR** (1-2 sentences from reading
   the body) — this replaces the old auto-truncated excerpt.

3. **Run the ingest script**:
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ingest_article.py \
     --metadata-json '{"title":"...","url":"...","author":"...",
                       "publication":"...","year":...,"tldr":"..."}' \
     --clipper-path /path/to/clipper.md
   ```

## How to ingest — YouTube

For `youtube.com/watch?v=<id>` or `youtu.be/<id>`:

1. **Fetch metadata** with yt-dlp:
   ```
   Bash: yt-dlp -j https://youtu.be/<id> > /tmp/yt-meta.json
   ```
   Parse `/tmp/yt-meta.json` for `title`, `channel`, `channel_id`,
   `duration`, `upload_date` (YYYYMMDD).

2. **Decide the transcription path:**
   - **High-quality (default for substantive content)** — Whisper:
     ```
     Bash: yt-dlp -x --audio-format mp3 \
                  -o "/tmp/<id>.audio.%(ext)s" https://youtu.be/<id>
     Bash: ~/.claude/skills/knowledge-smith/scripts/helpers/transcribe.sh \
                  /tmp/<id>.audio.mp3 > /tmp/<id>.transcript.md
     ```
     Then pass `--transcript-path /tmp/<id>.transcript.md
     --transcript-source whisper`.
   - **Fast/low-quality** — yt-dlp auto-subs:
     ```
     Bash: yt-dlp --write-auto-subs --skip-download \
                  --sub-format vtt --sub-langs en \
                  -o "/tmp/<id>" https://youtu.be/<id>
     ```
     Then pass `--vtt-path /tmp/<id>.en.vtt --transcript-source yt-auto`.

3. **Run the ingest script** (also pass the metadata JSON file you saved):
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ingest_youtube.py \
     --metadata-json '{"youtube_id":"<id>","title":"...","channel":"...",
                       "duration_seconds":...,"upload_date":"YYYYMMDD"}' \
     --metadata-path /tmp/yt-meta.json \
     --transcript-path /tmp/<id>.transcript.md \
     --transcript-source whisper
   ```

The user owns the audio file in `raw/youtube/<id>.audio.mp3` if they
want it; that's gitignored.

## How to ingest — bookmarks (blog or github)

For any URL:

1. **Detect kind** — `github.com/<owner>/<repo>` → kind=github; else
   kind=blog.

2. **For github**: parse owner+repo from the URL. The user's
   `--description` (if given) is the hook. No fetching.

3. **For blog**: WebFetch the URL:
   ```
   WebFetch:
     url: <url>
     prompt: "Return JSON with keys: title (string),
              author (string or null),
              description (one sentence, or null)."
   ```

4. **Run the ingest script**:
   ```
   # github
   uv run ~/.claude/skills/knowledge-smith/scripts/ingest_bookmark.py \
     --kind github \
     --metadata-json '{"url":"https://github.com/<owner>/<repo>",
                       "owner":"<owner>","repo":"<repo>",
                       "title":"<owner>/<repo>","description":"..."}'

   # blog
   uv run ~/.claude/skills/knowledge-smith/scripts/ingest_bookmark.py \
     --kind blog \
     --metadata-json '{"url":"...","title":"...","author":"...",
                       "description":"..."}'
   ```

## Reading list

```
uv run ~/.claude/skills/knowledge-smith/scripts/ks_reading_list.py --all
uv run ~/.claude/skills/knowledge-smith/scripts/ks_reading_list.py --kind paper
```
Generates `reading-list/<kind>.md` listing every `read: false` note for that
kind. Dated kinds (paper/article/youtube) are grouped by year, descending;
blog/github are flat lists. Regenerate after any ingest or read-flip.

## Tagging — agent-driven (subagents return tags)

`ks_tag.py` does the I/O only. The LLM call is **your** responsibility as
the orchestrating agent: spawn sonnet subagents in parallel, collect their
JSON output, and write it back via the script. No external API key needed.

Step-by-step (when the user asks to tag, retag, or "make notes searchable"):

1. **List untagged notes:**
   ```
   uv run ~/.claude/skills/knowledge-smith/scripts/ks_tag.py list --kind paper > /tmp/ks-tag-plan.jsonl
   ```
   Output begins with a `# vocab: t1, t2, ...` comment header (the
   controlled vocabulary; vault may override via `<vault>/.ks-tag-vocab`),
   followed by one JSON object per untagged note:
   `{"file": "/abs/path.md", "kind": "paper", "slug": "...", "title": "...", "year": YYYY, "abstract": "..."}`

2. **Read the plan**, parse the vocab, parse the JSONL.

3. **Batch into groups of 15–20 papers.**

4. **Dispatch parallel subagents** — one Agent tool call per batch, all in a
   single message so they run concurrently. Use:
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
   - Ask the subagent to "respond ONLY with N JSON lines, one per entry."

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

## Conventions

- **Paper notes always carry a PDF wikilink.** Every `notes/papers/<stem>.md`
  has a Source section line of the form `- PDF: [[raw/papers/pdf/<stem>.pdf]]`,
  even when the PDF isn't on disk (book stubs, ingest with `--no-pdf`,
  failed downloads). The link is unresolved-but-present so the user
  can drop a PDF at the canonical path later. Do not strip these
  unresolved links.
- **`raw/papers/` is split.** `.md` text lives at `raw/papers/md/<stem>.md`
  (committed); `.pdf` binaries at `raw/papers/pdf/<stem>.pdf` (gitignored).
  The `<stem>` mirrors the note basename.

## Don'ts
- **Do not invent metadata.** If a fetch step fails (WebFetch returns
  garbage, yt-dlp errors, PDF unreadable), surface the failure to the
  user — never fall back to filename-derived guesses.
- **Verify titles** against the user's request before writing. The most
  common bug class (typo'd arxiv ID → wrong paper resolved → wrong note
  filed) is caught here.
- Do not write under `raw/` by hand. Always go through the scripts.
- Do not commit binaries. The vault `.gitignore` is the source of truth.
- Do not hand-edit `reading-list/<kind>.md` — `ks_reading_list.py` overwrites.
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
