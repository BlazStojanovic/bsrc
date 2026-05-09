#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""ank_dump.py — Snapshot the Anki collection to per-deck markdown.

Talks to the Anki MCP server addon (http://127.0.0.1:3141/) over HTTP
and writes one .md file per deck under $ANKI_CARDS_DIR. Q is the
heading, A is the body, identity goes in a single inline metadata
line. The output is a snapshot — never hand-edit; rerun the dump.

Discovery order for the cards dir:
    1. $ANKI_CARDS_DIR
    2. ~/.config/bsrc/anki.env (the file written by bsrc/anki/install.sh)
    3. walk cwd upward for the .anki-cards marker
Hard-fail with exit 10 if none resolve.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

DEFAULT_MCP_URL = os.environ.get("ANK_MCP_URL", "http://127.0.0.1:3141/")
ENV_FILE = Path(
    os.environ.get(
        "ANK_ENV_FILE", str(Path.home() / ".config" / "bsrc" / "anki.env")
    )
)
MARKER = ".anki-cards"
SKIP_DECKS = {"Default"}  # empty stub deck Anki ships with

# Media sync: after dumping decks, scan the .md files for <img src="..."> refs
# and copy any missing files from Anki's collection.media into the repo's
# media/ folder. This keeps the GitHub-rendered markdown self-contained.
ANKI_PROFILE = os.environ.get("ANK_ANKI_PROFILE", "User 1")
ANKI_COLLECTION_MEDIA = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Anki2"
    / ANKI_PROFILE
    / "collection.media"
)
SKIP_MEDIA_SYNC = os.environ.get("ANK_SKIP_MEDIA_SYNC", "0") == "1"
MEDIA_DIR_NAME = "media"

# find_notes is paginated server-side: default limit 100, max 500. We
# request the max per page to minimize round-trips. notes_info has no
# documented limit but bulk responses can be large; chunk for safety.
FIND_NOTES_PAGE = 500
NOTES_INFO_CHUNK = 100


# ---------------------------------------------------------------------------
# Logging.
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"\033[1;32m[ank-dump]\033[0m {msg}", file=sys.stderr)


def err(msg: str) -> None:
    print(f"\033[1;31m[ank-dump×]\033[0m {msg}", file=sys.stderr)


def die(code: int, msg: str) -> NoReturn:
    err(msg)
    raise SystemExit(code)


# ---------------------------------------------------------------------------
# Cards-dir discovery.
# ---------------------------------------------------------------------------

def resolve_cards_dir() -> Path:
    env = os.environ.get("ANKI_CARDS_DIR", "").strip()
    if env:
        path = Path(env).expanduser().resolve()
        if not path.is_dir():
            die(10, f"$ANKI_CARDS_DIR points to a non-existent directory: {path}")
        return path

    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("ANKI_CARDS_DIR="):
                path = Path(line.split("=", 1)[1].strip()).expanduser().resolve()
                if path.is_dir():
                    return path

    cwd = Path.cwd().resolve()
    for d in [cwd, *cwd.parents]:
        if (d / MARKER).exists():
            return d

    die(
        10,
        "no anki cards dir found. Set ANKI_CARDS_DIR, cd into a dir "
        f"containing {MARKER}, or run bsrc/anki/install.sh.",
    )


# ---------------------------------------------------------------------------
# MCP HTTP client.
# ---------------------------------------------------------------------------

class MCPClient:
    """Minimal MCP HTTP client. Speaks JSON-RPC over POST and parses
    server-sent-event responses (event: message / data: <json>).
    """

    def __init__(self, url: str = DEFAULT_MCP_URL):
        self.url = url
        self._session_id: str | None = None
        self._next_id = 0

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    def _post(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, str]]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.URLError as e:
            die(2, f"MCP server unreachable at {self.url}: {e}")

        # SSE-formatted body: lines starting with "data: " carry JSON.
        for line in raw.splitlines():
            if line.startswith("data: "):
                return json.loads(line[len("data: "):]), hdrs
        # Plain JSON fallback (some methods/notifications return empty body).
        if raw.strip():
            return json.loads(raw), hdrs
        return None, hdrs

    def initialize(self) -> dict[str, Any]:
        self._next_id += 1
        result, hdrs = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "bsrc-ank-dump", "version": "0.1"},
                },
            }
        )
        self._session_id = hdrs.get("mcp-session-id")
        # Per the spec, send notifications/initialized after the response.
        self._post(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        if not result or "result" not in result:
            die(2, f"MCP initialize failed: {result!r}")
        return result["result"]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self._next_id += 1
        envelope, _ = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if envelope is None:
            die(2, f"empty response for tool {name}")
        if "error" in envelope:
            die(2, f"MCP tool {name} failed: {envelope['error']}")

        result = envelope.get("result", {})
        # Tool result is a list of content blocks; we expect the first to
        # be JSON-encoded text.
        for block in result.get("content", []):
            if block.get("type") == "text":
                text = block.get("text", "")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
        return result


# ---------------------------------------------------------------------------
# Markdown rendering.
# ---------------------------------------------------------------------------

_ENT_REPLACEMENTS = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
}


def html_to_markdown(html: str) -> str:
    """Light cleanup of Anki's HTML-ish field content into markdown.

    Most stock Basic/Cloze fields are plain text or lightly-formatted; we
    convert <br>/<div> to newlines, decode common entities, and let the
    rest pass through. Anki's WYSIWYG output is already mostly readable.
    """
    s = html or ""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"</div>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<div[^>]*>", "", s, flags=re.IGNORECASE)
    for k, v in _ENT_REPLACEMENTS.items():
        s = s.replace(k, v)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def slugify_filename(name: str) -> str:
    """Filesystem-safe basename for a deck file. Spaces become underscores."""
    return re.sub(r"\s+", "_", name).strip(". _") or "deck"


def _field_value(fields: dict[str, Any], key: str) -> str:
    field = fields.get(key)
    if not field:
        return ""
    if isinstance(field, dict):
        return field.get("value", "")
    return str(field)


def _ordered_fields(fields: dict[str, Any]) -> list[tuple[str, str]]:
    """Return [(name, value)] sorted by Anki's per-note-type field order."""
    items: list[tuple[str, str, int]] = []
    for name, field in fields.items():
        order = field.get("order", 0) if isinstance(field, dict) else 0
        value = field.get("value", "") if isinstance(field, dict) else str(field)
        items.append((name, value, order))
    items.sort(key=lambda t: t[2])
    return [(name, value) for name, value, _ in items]


def split_q_a(model: str, fields: dict[str, Any]) -> tuple[str, str]:
    """Pick a (question, answer) pair from a note's fields based on model."""
    if model in {"Basic", "Basic (and reversed card)", "Basic (optional reversed card)", "Basic (type in the answer)"}:
        return _field_value(fields, "Front"), _field_value(fields, "Back")
    if model == "Cloze":
        # For Cloze, Text is the body; Back Extra (or Extra) is the explanation.
        return _field_value(fields, "Text"), _field_value(fields, "Back Extra") or _field_value(fields, "Extra")
    ordered = _ordered_fields(fields)
    q = ordered[0][1] if len(ordered) > 0 else ""
    a = ordered[1][1] if len(ordered) > 1 else ""
    return q, a


_TIMESTAMP_LINE_PREFIX = "*"


def render_deck(deck_name: str, notes: list[dict[str, Any]], timestamp: str) -> str:
    """Render one deck's notes as a markdown document. Timestamp is
    threaded in so callers can pin it (e.g. preserve the existing
    timestamp when the body hasn't changed)."""
    lines: list[str] = [
        f"# {deck_name}",
        f"*{len(notes)} cards · regenerated {timestamp} from Anki via MCP · do not hand-edit*",
        "",
    ]

    # Stable order: by noteId so re-dumps don't churn diffs.
    notes_sorted = sorted(notes, key=lambda n: n.get("noteId", 0))

    for i, note in enumerate(notes_sorted):
        if i > 0:
            lines.append("---")
            lines.append("")

        fields = note.get("fields", {})
        model = note.get("modelName", "?")
        note_id = note.get("noteId", "?")
        tags = [t for t in note.get("tags", []) if t]

        q_html, a_html = split_q_a(model, fields)
        q_md = html_to_markdown(q_html)
        a_md = html_to_markdown(a_html)

        # Q heading is the first line; any extra Q lines go above the answer.
        q_lines = [l for l in q_md.split("\n") if l.strip() != ""] or ["(empty)"]
        heading = q_lines[0].strip()
        rest_q = "\n".join(q_lines[1:]).strip()

        meta_bits = [model]
        if tags:
            meta_bits.append("tags: " + ", ".join(tags))
        meta_bits.append(f"id {note_id}")

        # Markdown headings can't contain unescaped #; replace defensively.
        heading_safe = heading.replace("\n", " ").strip()
        if heading_safe.startswith("#"):
            heading_safe = "\\" + heading_safe

        lines.append(f"## {heading_safe}")
        lines.append(f"*{' · '.join(meta_bits)}*")
        lines.append("")
        if rest_q:
            lines.append(rest_q)
            lines.append("")
        lines.append(a_md or "*(empty)*")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Driver.
# ---------------------------------------------------------------------------

def _normalize_decks(payload: Any) -> list[str]:
    """Coerce list_decks output into a flat list of deck names."""
    if isinstance(payload, list):
        out: list[str] = []
        for item in payload:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("deck") or item.get("deckName")
                if name:
                    out.append(name)
        return out
    if isinstance(payload, dict):
        for key in ("decks", "result", "names"):
            if key in payload and isinstance(payload[key], list):
                return _normalize_decks(payload[key])
    return []


def _normalize_note_ids(payload: Any) -> list[int]:
    if isinstance(payload, list):
        return [int(x) for x in payload]
    if isinstance(payload, dict):
        for key in ("noteIds", "notes", "result"):
            if key in payload:
                return _normalize_note_ids(payload[key])
    return []


def _normalize_notes(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [n for n in payload if isinstance(n, dict)]
    if isinstance(payload, dict):
        for key in ("notes", "result"):
            if key in payload and isinstance(payload[key], list):
                return _normalize_notes(payload[key])
    return []


_IMG_SRC_RE = re.compile(r"""<img\b[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def collect_media_refs(deck_files: list[Path]) -> set[str]:
    """Scan deck markdown for <img src="..."> filenames. Filters to bare
    filenames (Anki stores media as flat files; HTTP/relative-path src
    values are passed through to Anki as-is and shouldn't be copied)."""
    refs: set[str] = set()
    for path in deck_files:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in _IMG_SRC_RE.finditer(content):
            src = match.group(1).strip()
            # Skip absolute URLs and explicit paths — only Anki-collection
            # filenames (no slashes, no scheme) get media-synced.
            if "://" in src or src.startswith("/") or "/" in src:
                continue
            if src:
                refs.add(src)
    return refs


def sync_media(cards_dir: Path, deck_files: list[Path]) -> tuple[int, int]:
    """Copy any newly-referenced Anki media into the repo's media/ folder.
    Additive only — never deletes. Returns (copied, missing)."""
    if SKIP_MEDIA_SYNC:
        log("media sync skipped (ANK_SKIP_MEDIA_SYNC=1)")
        return (0, 0)

    if not ANKI_COLLECTION_MEDIA.is_dir():
        log(f"media sync skipped: {ANKI_COLLECTION_MEDIA} not found "
            f"(set ANK_ANKI_PROFILE if profile name differs from 'User 1')")
        return (0, 0)

    refs = collect_media_refs(deck_files)
    if not refs:
        return (0, 0)

    media_dir = cards_dir / MEDIA_DIR_NAME
    media_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    missing = 0
    for filename in sorted(refs):
        dest = media_dir / filename
        if dest.exists():
            continue
        src = ANKI_COLLECTION_MEDIA / filename
        if not src.is_file():
            missing += 1
            log(f"media missing in collection.media: {filename}")
            continue
        # Use shutil.copy2 to preserve mtime; copy by-bytes only.
        import shutil
        try:
            shutil.copy2(src, dest)
            copied += 1
        except OSError as e:
            log(f"media copy failed for {filename}: {e}")
            missing += 1
    if copied:
        log(f"media synced: {copied} new files into {media_dir}")
    if missing:
        log(f"media not synced: {missing} referenced files unavailable")
    return (copied, missing)


def _stable_body(md: str) -> str:
    """Return the deck's content with the regeneration timestamp masked
    out, so equality comparisons across runs ignore the header.
    """
    out = []
    for line in md.split("\n"):
        if line.startswith(_TIMESTAMP_LINE_PREFIX) and "regenerated " in line:
            out.append("<header>")
        else:
            out.append(line)
    return "\n".join(out)


def main() -> int:
    cards_dir = resolve_cards_dir()
    log(f"cards dir: {cards_dir}")

    client = MCPClient()
    info = client.initialize()
    server_name = info.get("serverInfo", {}).get("name", "?")
    server_ver = info.get("serverInfo", {}).get("version", "?")
    log(f"connected to MCP: {server_name} v{server_ver}")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    decks_raw = client.call_tool("list_decks", {})
    deck_names = _normalize_decks(decks_raw)
    if not deck_names:
        die(3, f"list_decks returned no decks. Raw: {decks_raw!r}")

    written = 0
    total_notes = 0
    seen_files: set[str] = set()
    deck_paths: list[Path] = []

    for name in deck_names:
        if name in SKIP_DECKS:
            continue

        # Paginate find_notes (limit/offset).
        note_ids: list[int] = []
        offset = 0
        while True:
            page = client.call_tool(
                "find_notes",
                {"query": f'deck:"{name}"', "limit": FIND_NOTES_PAGE, "offset": offset},
            )
            page_ids = _normalize_note_ids(page)
            if not page_ids:
                break
            note_ids.extend(page_ids)
            if len(page_ids) < FIND_NOTES_PAGE:
                break
            offset += FIND_NOTES_PAGE

        if not note_ids:
            log(f"skip {name}: 0 notes")
            continue

        # Chunk notes_info to keep response sizes manageable.
        notes: list[dict[str, Any]] = []
        for i in range(0, len(note_ids), NOTES_INFO_CHUNK):
            chunk = note_ids[i : i + NOTES_INFO_CHUNK]
            info_raw = client.call_tool("notes_info", {"notes": chunk})
            notes.extend(_normalize_notes(info_raw))
        if not notes:
            log(f"skip {name}: notes_info empty")
            continue

        new_md = render_deck(name, notes, timestamp)
        filename = f"{slugify_filename(name)}.md"
        # If two decks slugify to the same name, append a counter.
        base = filename
        n = 2
        while filename in seen_files:
            stem = base[:-3]
            filename = f"{stem}_{n}.md"
            n += 1
        seen_files.add(filename)

        path = cards_dir / filename
        deck_paths.append(path)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if _stable_body(existing) == _stable_body(new_md):
                log(f"unchanged {filename}: {len(notes)} cards")
                total_notes += len(notes)
                continue

        path.write_text(new_md, encoding="utf-8")
        log(f"wrote {filename}: {len(notes)} cards")
        written += 1
        total_notes += len(notes)

    sync_media(cards_dir, deck_paths)

    log(f"done: {written} decks changed, {total_notes} cards total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
