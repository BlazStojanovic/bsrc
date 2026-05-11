"""I/O building blocks for knowledge-smith ingest scripts.

This module is imported by orchestrator scripts (`ingest_*.py`) and is
also exposed via thin CLI wrappers under `helpers/` so the agent can
compose pipelines step-by-step (download → parse → write).

Every helper here is **pure I/O**: HTTP, subprocess, file ops. No
metadata judgment, no slug derivation, no parser-tier choice — those
are the agent's job.

The importing runner declares its own PEP 723 deps as needed
(`httpx` for download_pdf / fetch_ar5iv; `markdownify` for fetch_ar5iv).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import die, info, read_frontmatter, warn, write_frontmatter  # noqa: E402


USER_AGENT = "knowledge-smith/0.3"
AR5IV_URL = "https://ar5iv.labs.arxiv.org/html/{id}"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{id}.pdf"


# ---------------------------------------------------------------------------
# HTTP — download_pdf + fetch_ar5iv.
# ---------------------------------------------------------------------------

def download_pdf(url: str, dest: Path, *, timeout: float = 120.0) -> bool:
    """Stream a PDF to `dest` (atomic via .tmp + rename).

    Returns True on success, False on HTTP failure (with a warn log).
    Caller decides whether to die() or continue with a missing PDF.
    """
    import httpx  # type: ignore[import-not-found]

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with httpx.Client(
            follow_redirects=True, timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        ) as c:
            with c.stream("GET", url) as r:
                r.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in r.iter_bytes():
                        fh.write(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        warn(f"PDF download failed ({url}): {exc}")
        return False
    tmp.replace(dest)
    return True


def download_arxiv_pdf(arxiv_id: str, dest: Path) -> bool:
    """Convenience wrapper for arXiv-hosted PDFs."""
    return download_pdf(ARXIV_PDF_URL.format(id=arxiv_id), dest)


def fetch_ar5iv(arxiv_id: str, *, timeout: float = 60.0) -> str | None:
    """Fetch the ar5iv HTML for an arXiv id and convert to markdown.

    Returns markdown string on success, None on HTTP failure or non-200
    (with a warn log).
    """
    import httpx  # type: ignore[import-not-found]
    from markdownify import markdownify  # type: ignore[import-not-found]

    try:
        with httpx.Client(
            follow_redirects=True, timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        ) as c:
            r = c.get(AR5IV_URL.format(id=arxiv_id))
    except httpx.HTTPError as exc:
        warn(f"ar5iv fetch failed for {arxiv_id}: {exc}")
        return None
    if r.status_code != 200:
        warn(f"ar5iv returned {r.status_code} for {arxiv_id}")
        return None
    return markdownify(r.text, heading_style="ATX", strip=["script", "style"])


# ---------------------------------------------------------------------------
# Subprocess — pdftotext + docling.
# ---------------------------------------------------------------------------

def run_pdftotext(pdf_path: Path, *, layout: bool = False) -> str:
    """Run `pdftotext <pdf> -` and return the extracted text.

    Hard-fails if pdftotext exits non-zero. `layout=True` preserves
    columns (useful for tables); default reflowed mode is better for
    prose.
    """
    cmd = ["pdftotext"]
    if layout:
        cmd.append("-layout")
    cmd.extend([str(pdf_path), "-"])
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        die(11, "pdftotext not found — install poppler (`brew install poppler`)")
    except subprocess.CalledProcessError as exc:
        die(5, f"pdftotext failed (exit {exc.returncode}):\n{exc.stderr}")
    return result.stdout


def run_docling(pdf_path: Path) -> str:
    """Shell out to the docling helper and return markdown.

    Keeps docling's heavy deps out of the orchestrator's PEP 723 block.
    First invocation downloads layout/OCR models (~hundreds of MB).
    """
    helper = Path(__file__).resolve().parent / "helpers" / "docling_extract.py"
    if not helper.is_file():
        die(11, f"docling helper missing: {helper}")
    info("running docling (first run pulls layout/OCR models — slow)…")
    try:
        result = subprocess.run(
            [str(helper), str(pdf_path)],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        die(5, f"docling failed (exit {exc.returncode}):\n{exc.stderr}")
    return result.stdout


# ---------------------------------------------------------------------------
# VTT flattening for YouTube auto-subs.
# ---------------------------------------------------------------------------

def vtt_to_markdown(vtt: str) -> str:
    """Flatten a WebVTT auto-subs file into plain prose paragraphs.

    Deterministic string transform — no LLM judgment. Strips timing
    cues, HTML tags, and consecutive duplicate lines (yt's auto-subs
    repeat heavily).
    """
    lines: list[str] = []
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT":
            continue
        if line.startswith(("NOTE", "STYLE", "REGION", "X-TIMESTAMP-MAP")):
            continue
        if "-->" in line:
            continue
        if re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = (line.replace("&amp;", "&").replace("&#39;", "'")
                    .replace("&quot;", '"'))
        if not line:
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    deduped: list[str] = []
    for line in lines:
        if deduped and (deduped[-1] in line or line in deduped[-1]):
            if len(line) > len(deduped[-1]):
                deduped[-1] = line
            continue
        deduped.append(line)
    text = " ".join(deduped)
    text = re.sub(r"(?<=[.!?])\s+", "\n\n", text)
    return text.strip() + "\n"


# ---------------------------------------------------------------------------
# File moves into raw/.
# ---------------------------------------------------------------------------

def copy_clipper(src: Path, dest: Path, *, force: bool = False) -> dict:
    """Copy a Web Clipper markdown file into the vault, preserving its
    original frontmatter under a `clipper:` block in the new raw note.

    Returns the original clipper frontmatter as a dict (so the caller
    can inspect URL / title / etc.).
    """
    if not src.is_file():
        die(2, f"clipper source is not a file: {src}")
    if dest.exists() and not force:
        warn(f"raw target exists, leaving as-is: {dest}")
        clipper_meta, _ = read_frontmatter(dest)
        return dict(clipper_meta.get("clipper") or {})

    clipper_meta, body = read_frontmatter(src)
    raw_meta = {
        "source": "clipper",
        "clipper": dict(clipper_meta),
    }
    write_frontmatter(dest, raw_meta, body)
    return dict(clipper_meta)


def move_into_raw(src: Path, dest: Path, *, force: bool = False) -> bool:
    """Move a file into the vault's `raw/` tree. Returns True on move,
    False if dest existed and `force=False` (caller logs)."""
    if not src.is_file():
        die(2, f"source is not a file: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return False
    shutil.move(str(src), str(dest))
    return True


def copy_into_raw(src: Path, dest: Path, *, force: bool = False) -> bool:
    """Like move_into_raw but copy-preserve, used when the source is
    something the user might keep in /tmp (e.g. PDFs they already had).
    """
    if not src.is_file():
        die(2, f"source is not a file: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return False
    shutil.copy2(src, dest)
    return True


# ---------------------------------------------------------------------------
# Body markdown loader — used by every ingest orchestrator.
# ---------------------------------------------------------------------------

def load_body(body_md_path: str | None, body_md_inline: str | None) -> str:
    """Resolve the note body markdown.

    Precedence: --body-md-path > inline `body_md` from --metadata-json
    > empty string. Empty body is allowed; the agent may have nothing to
    write yet (a stub note).
    """
    if body_md_path:
        path = Path(body_md_path).expanduser()
        if not path.is_file():
            die(2, f"--body-md-path is not a file: {path}")
        return path.read_text(encoding="utf-8")
    if body_md_inline:
        return body_md_inline
    return ""


# ---------------------------------------------------------------------------
# Tiny convenience: write multiple lines of `key=value` summary to stdout
# for the agent to parse after a successful ingest.
# ---------------------------------------------------------------------------

def emit_summary(pairs: Iterable[tuple[str, object]]) -> None:
    for key, value in pairs:
        if value is None:
            continue
        print(f"{key}={value}")
