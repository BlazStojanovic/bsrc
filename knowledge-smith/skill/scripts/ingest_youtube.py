#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "yt-dlp>=2024.8",
#   "python-frontmatter>=1.1",
# ]
# ///
"""Ingest a YouTube video into the active vault.

Slice 1 fetches only:
  - metadata via yt-dlp's extract_info (no download)
  - auto-generated English subtitles (.vtt -> flattened transcript markdown)

Audio download and Whisper transcription are slice-2 follow-ups.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    die,
    find_vault,
    info,
    note_path,
    raw_path,
    refuse_if_exists,
    slugify,
    stub_filename,
    today,
    warn,
    write_frontmatter,
)


YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def parse_youtube_id(arg: str) -> str:
    if YOUTUBE_ID_RE.match(arg):
        return arg
    parsed = urlparse(arg)
    if parsed.netloc.endswith("youtu.be"):
        ytid = parsed.path.lstrip("/").split("/", 1)[0]
        if YOUTUBE_ID_RE.match(ytid):
            return ytid
    if "youtube" in parsed.netloc:
        qs = parse_qs(parsed.query)
        v = qs.get("v", [None])[0]
        if v and YOUTUBE_ID_RE.match(v):
            return v
        # /shorts/<id>, /embed/<id>, /v/<id>
        m = re.match(r"^/(?:shorts|embed|v)/([A-Za-z0-9_-]{11})", parsed.path)
        if m:
            return m.group(1)
    die(2, f"could not extract YouTube id from: {arg!r}")


def vtt_to_markdown(vtt: str) -> str:
    """Flatten a WebVTT auto-subs file into plain prose paragraphs.

    YouTube auto-subs are dense with overlapping cues (rolling display).
    Strategy: drop timestamps and tags, dedupe consecutive identical lines,
    emit roughly one sentence per line, group into paragraphs at long pauses.
    """
    lines = []
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
        # Strip <c.colorXXXX> and <00:00:00.000> inline tags.
        line = re.sub(r"<[^>]+>", "", line)
        # Decode common entities.
        line = line.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
        if not line:
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)

    # Coalesce token-level cue overlaps: each subsequent line often extends
    # the previous one. We keep only "longer" extensions, not duplicates.
    deduped: list[str] = []
    for line in lines:
        if deduped and (deduped[-1] in line or line in deduped[-1]):
            if len(line) > len(deduped[-1]):
                deduped[-1] = line
            continue
        deduped.append(line)

    text = " ".join(deduped)
    # Light paragraphing on sentence-ending punctuation.
    text = re.sub(r"(?<=[.!?])\s+", "\n\n", text)
    return text.strip() + "\n"


def fetch_via_yt_dlp(youtube_id: str, tmpdir: Path) -> tuple[Path, Path | None]:
    """Run yt-dlp to write metadata.json + auto-sub .vtt. Returns (info_json, vtt or None)."""
    from yt_dlp import YoutubeDL  # type: ignore[import-not-found]

    out_template = str(tmpdir / "%(id)s")
    opts: dict = {
        "skip_download": True,
        "writeinfojson": True,
        "writeautomaticsub": True,
        "writesubtitles": False,  # don't fetch human-uploaded subs (slice-1 keeps it simple)
        "subtitleslangs": ["en", "en-US", "en-GB"],
        "subtitlesformat": "vtt",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
    }
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    info(f"fetching yt-dlp metadata + auto-subs for {youtube_id}")
    with YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
        try:
            ydl.extract_info(url, download=True)
        except Exception as exc:
            die(5, f"yt-dlp failed: {exc}")

    info_json = tmpdir / f"{youtube_id}.info.json"
    if not info_json.is_file():
        die(5, f"yt-dlp did not produce info.json for {youtube_id}")

    vtt: Path | None = None
    for ext in ("en.vtt", "en-US.vtt", "en-GB.vtt"):
        candidate = tmpdir / f"{youtube_id}.{ext}"
        if candidate.is_file():
            vtt = candidate
            break
    return info_json, vtt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", help="YouTube URL or 11-char video id")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    args = p.parse_args(argv)

    vault = find_vault().path
    youtube_id = parse_youtube_id(args.input)
    info(f"vault: {vault}")
    info(f"youtube: {youtube_id}")

    raw_metadata_target = raw_path(vault, "youtube", f"{youtube_id}.metadata.json")
    raw_transcript_target = raw_path(vault, "youtube", f"{youtube_id}.transcript.md")

    with tempfile.TemporaryDirectory() as tdir:
        tmpdir = Path(tdir)
        info_json, vtt = fetch_via_yt_dlp(youtube_id, tmpdir)
        meta_dict = json.loads(info_json.read_text(encoding="utf-8"))

        raw_metadata_target.parent.mkdir(parents=True, exist_ok=True)
        if raw_metadata_target.exists() and not args.force:
            warn(f"metadata exists, leaving as-is: {raw_metadata_target.relative_to(vault)}")
        else:
            shutil.move(str(info_json), str(raw_metadata_target))
        info(f"wrote: {raw_metadata_target.relative_to(vault)}")

        if vtt is None:
            warn("no auto-generated English subtitles available for this video")
            transcript_text = (
                "<!-- no auto-subs available; consider promoting and running "
                "Whisper transcription (slice 2) -->\n"
            )
            transcript_source = "none"
        else:
            transcript_text = vtt_to_markdown(vtt.read_text(encoding="utf-8"))
            transcript_source = "yt-auto"

    raw_transcript_target.parent.mkdir(parents=True, exist_ok=True)
    if raw_transcript_target.exists() and not args.force:
        warn(f"transcript exists, leaving as-is: {raw_transcript_target.relative_to(vault)}")
    else:
        raw_transcript_target.write_text(transcript_text, encoding="utf-8")
    info(f"wrote: {raw_transcript_target.relative_to(vault)}")

    title = meta_dict.get("title", youtube_id)
    channel = meta_dict.get("channel") or meta_dict.get("uploader")
    channel_id = meta_dict.get("channel_id") or meta_dict.get("uploader_id")
    duration_seconds = meta_dict.get("duration") or 0
    upload_date_raw = meta_dict.get("upload_date")  # YYYYMMDD
    if upload_date_raw and len(upload_date_raw) == 8:
        upload_date = f"{upload_date_raw[:4]}-{upload_date_raw[4:6]}-{upload_date_raw[6:8]}"
        year = int(upload_date_raw[:4])
    else:
        upload_date = None
        year = datetime.now().year

    slug = slugify(title)
    stub = stub_filename(year, slug)
    note_target = note_path(vault, "youtube", stub)
    refuse_if_exists(note_target, args.force)

    raw_audio_path = raw_path(vault, "youtube", f"{youtube_id}.audio.m4a")
    note_meta = {
        "type": "note",
        "kind": "youtube",
        "slug": slug,
        "title": title,
        "created": today(),
        "updated": today(),
        "read": False,
        "tags": [],
        "year": year,
        "youtube_id": youtube_id,
        "url": f"https://youtu.be/{youtube_id}",
        "channel": channel,
        "channel_id": channel_id,
        "duration_seconds": duration_seconds,
        "upload_date": upload_date,
        "raw_audio": None,
        "raw_transcript": raw_transcript_target.relative_to(vault).as_posix(),
        "raw_metadata": raw_metadata_target.relative_to(vault).as_posix(),
        "transcript_source": transcript_source,
    }
    body = (
        f"# {title}\n\n"
        f"> *{channel or 'unknown'}* — uploaded {upload_date or '?'}"
        f" — {duration_seconds}s\n\n"
        "## TL;DR\n\n"
        "(stub)\n\n"
        "## Notes\n\n"
        "(stub)\n\n"
        "## Source\n\n"
        f"- Transcript: [[raw/youtube/{youtube_id}.transcript]]\n"
        f"- Metadata: `raw/youtube/{youtube_id}.metadata.json`\n"
        f"- Audio (gitignored, slice-2): `{raw_audio_path.relative_to(vault).as_posix()}`\n"
        f"- Original: <https://youtu.be/{youtube_id}>\n"
    )
    write_frontmatter(note_target, note_meta, body)
    info(f"wrote: {note_target.relative_to(vault)}")

    print(f"note={note_target}")
    print(f"raw_metadata={raw_metadata_target}")
    print(f"raw_transcript={raw_transcript_target}")
    print(f"transcript_source={transcript_source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
