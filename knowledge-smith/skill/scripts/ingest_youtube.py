#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1"]
# ///
"""Write a YouTube note + raw assets into the active vault.

The agent runs `yt-dlp -j <url>` for metadata and decides the
transcription path:

  - high-quality (default): agent runs `yt-dlp -x --audio-format mp3`
    then `helpers/transcribe.sh <audio> > <transcript>`, passes
    --transcript-path to this script.
  - fast/low-quality: agent runs `yt-dlp --write-auto-subs` and passes
    --vtt-path; this script flattens the VTT into prose.
  - none: skip both flags; the note is still written, the transcript
    file is a placeholder.

Required JSON keys: youtube_id, title.
Optional: channel, channel_id, duration_seconds, upload_date, year.

The agent should write yt-dlp's JSON dump to raw/youtube/<id>.metadata.json
itself before calling (one less arg, less script work).

Examples:
  uv run ingest_youtube.py --metadata-json '{
    "youtube_id": "dQw4w9WgXcQ",
    "title": "...",
    "channel": "...",
    "channel_id": "...",
    "duration_seconds": 213,
    "upload_date": "2009-10-24"
  }' --transcript-path raw/youtube/dQw4w9WgXcQ.transcript.md \\
     --transcript-source whisper
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

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
    validate_metadata_json,
    warn,
    write_frontmatter,
)


def vtt_to_markdown(vtt: str) -> str:
    """Flatten a WebVTT auto-subs file into plain prose paragraphs."""
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--transcript-path",
                   help="path to a pre-extracted transcript markdown file "
                        "(e.g. whisper output). Will be moved into raw/youtube/.")
    p.add_argument("--vtt-path",
                   help="path to a yt-dlp auto-subs .vtt file; will be flattened "
                        "into prose markdown.")
    p.add_argument("--transcript-source",
                   choices=("whisper", "yt-auto", "human", "none"),
                   default=None,
                   help="frontmatter label for the transcript provenance")
    p.add_argument("--metadata-path",
                   help="optional path to a yt-dlp -j JSON dump; will be moved "
                        "into raw/youtube/<id>.metadata.json")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    args = p.parse_args(argv)

    if args.transcript_path and args.vtt_path:
        die(2, "--transcript-path and --vtt-path are mutually exclusive")

    meta = validate_metadata_json(args.metadata_json, "youtube")
    youtube_id = meta["youtube_id"]
    vault = find_vault().path
    info(f"vault: {vault}")
    info(f"youtube: {youtube_id}")

    raw_metadata_target = raw_path(vault, "youtube", f"{youtube_id}.metadata.json")
    raw_transcript_target = raw_path(vault, "youtube", f"{youtube_id}.transcript.md")
    raw_audio_target = raw_path(vault, "youtube", f"{youtube_id}.audio.mp3")

    raw_metadata_target.parent.mkdir(parents=True, exist_ok=True)

    if args.metadata_path:
        src = Path(args.metadata_path).expanduser().resolve()
        if not src.is_file():
            die(2, f"--metadata-path is not a file: {src}")
        if raw_metadata_target.exists() and not args.force:
            warn(f"metadata exists, leaving as-is: "
                 f"{raw_metadata_target.relative_to(vault)}")
        else:
            shutil.move(str(src), str(raw_metadata_target))
            info(f"wrote: {raw_metadata_target.relative_to(vault)}")

    transcript_source = args.transcript_source
    if args.transcript_path:
        src = Path(args.transcript_path).expanduser().resolve()
        if not src.is_file():
            die(2, f"--transcript-path is not a file: {src}")
        text = src.read_text(encoding="utf-8")
        transcript_source = transcript_source or "whisper"
    elif args.vtt_path:
        src = Path(args.vtt_path).expanduser().resolve()
        if not src.is_file():
            die(2, f"--vtt-path is not a file: {src}")
        text = vtt_to_markdown(src.read_text(encoding="utf-8"))
        transcript_source = transcript_source or "yt-auto"
    else:
        warn("no transcript supplied — writing placeholder")
        text = ("<!-- no transcript supplied; run helpers/transcribe.sh on the "
                "downloaded audio and re-run with --transcript-path -->\n")
        transcript_source = transcript_source or "none"

    if raw_transcript_target.exists() and not args.force:
        warn(f"transcript exists, leaving as-is: "
             f"{raw_transcript_target.relative_to(vault)}")
    else:
        raw_transcript_target.write_text(text, encoding="utf-8")
        info(f"wrote: {raw_transcript_target.relative_to(vault)}")

    title = meta["title"]
    slug = slugify(title)
    year = meta.get("year")
    upload_date = meta.get("upload_date")
    if isinstance(upload_date, str) and len(upload_date) == 8 and upload_date.isdigit():
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    if not year and upload_date:
        try:
            year = int(upload_date[:4])
        except ValueError:
            year = None

    note_target = note_path(vault, "youtube", stub_filename(year, slug))
    refuse_if_exists(note_target, args.force)

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
        "channel": meta.get("channel"),
        "channel_id": meta.get("channel_id"),
        "duration_seconds": meta.get("duration_seconds") or 0,
        "upload_date": upload_date,
        "raw_audio": raw_audio_target.relative_to(vault).as_posix()
                     if raw_audio_target.is_file() else None,
        "raw_transcript": raw_transcript_target.relative_to(vault).as_posix(),
        "raw_metadata": (raw_metadata_target.relative_to(vault).as_posix()
                         if raw_metadata_target.is_file() else None),
        "transcript_source": transcript_source,
    }
    body = (
        f"# {title}\n\n"
        f"> *{meta.get('channel') or 'unknown'}* — uploaded "
        f"{upload_date or '?'} — {meta.get('duration_seconds') or 0}s\n\n"
        "## TL;DR\n\n(stub)\n\n"
        "## Notes\n\n(stub)\n\n"
        "## Source\n\n"
        f"- Transcript: [[raw/youtube/{youtube_id}.transcript]]\n"
        f"- Metadata: `raw/youtube/{youtube_id}.metadata.json`\n"
        f"- Audio (gitignored): `raw/youtube/{youtube_id}.audio.mp3`\n"
        f"- Original: <https://youtu.be/{youtube_id}>\n"
    )
    write_frontmatter(note_target, note_meta, body)
    info(f"wrote: {note_target.relative_to(vault)}")

    print(f"note={note_target}")
    print(f"raw_transcript={raw_transcript_target}")
    if raw_metadata_target.is_file():
        print(f"raw_metadata={raw_metadata_target}")
    print(f"transcript_source={transcript_source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
