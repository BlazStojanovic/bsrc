#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1", "pyyaml>=6.0"]
# ///
"""Write a YouTube note + raw assets into the active vault.

Thin orchestrator: the agent runs `yt-dlp -j` for metadata, picks the
slug + year, decides the transcription path, and supplies the rendered
note body. This script moves the transcript / metadata into raw/youtube/
and writes the note via merge_frontmatter.

Required JSON keys:
    title, slug, year, youtube_id  (and links.source)

Transcription paths (agent picks externally):
  - whisper:  agent ran `helpers/transcribe.sh audio.mp3 > transcript.md`
              and passes `--transcript-path … --transcript-source whisper`.
  - yt-auto:  agent ran `yt-dlp --write-auto-subs` then
              `helpers/vtt_flatten.py …vtt > transcript.md` and passes
              `--transcript-path … --transcript-source yt-auto`.
  - none:     agent passes `--transcript-source none` and no path.

Examples:
  uv run ingest_youtube.py \\
    --metadata-json '{"youtube_id":"<id>","title":"...","slug":"...",
                       "year":2024,"channel":"...","duration_seconds":600}' \\
    --links-json '{"source":"https://youtu.be/<id>"}' \\
    --transcript-path /tmp/<id>.transcript.md \\
    --transcript-source whisper \\
    --metadata-path /tmp/<id>.metadata.json \\
    --body-md-path /tmp/note-body.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    die,
    find_vault,
    info,
    load_schema,
    merge_frontmatter,
    note_path,
    parse_links_json,
    parse_metadata_json,
    raw_path,
    validate_meta,
    warn,
)
from _ks_helpers import emit_summary, load_body, move_into_raw  # noqa: E402

KIND = "youtube"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--transcript-path",
                   help="path to a markdown transcript file (whisper or yt-auto). "
                        "Will be moved into raw/youtube/.")
    p.add_argument("--metadata-path",
                   help="path to a yt-dlp -j JSON dump; will be moved into raw/youtube/.")
    p.add_argument("--transcript-source",
                   choices=("whisper", "yt-auto", "human", "none"),
                   default="none",
                   help="frontmatter label for transcript provenance")
    p.add_argument("--body-md-path",
                   help="path to a markdown file with the rendered note body")
    p.add_argument("--links-json",
                   help="JSON object overriding/augmenting metadata.links")
    p.add_argument("--force", action="store_true",
                   help="overwrite existing body and raw assets")
    args = p.parse_args(argv)

    vault = find_vault().path
    schema = load_schema(vault)
    info(f"vault: {vault}")

    raw_meta = parse_metadata_json(args.metadata_json)
    links_override = parse_links_json(args.links_json)
    raw_meta["links"] = {**(raw_meta.get("links") or {}), **links_override}

    youtube_id = raw_meta.get("youtube_id")
    slug = raw_meta.get("slug")
    year = raw_meta.get("year")
    if not (youtube_id and slug and year):
        die(2, "youtube metadata missing youtube_id/slug/year (agent must supply)")
    info(f"youtube: {youtube_id}")

    raw_metadata_target = raw_path(vault, KIND, f"{youtube_id}.metadata.json")
    raw_transcript_target = raw_path(vault, KIND, f"{youtube_id}.transcript.md")
    raw_audio_target = raw_path(vault, KIND, f"{youtube_id}.audio.mp3")

    if args.metadata_path:
        if move_into_raw(Path(args.metadata_path).expanduser(), raw_metadata_target,
                         force=args.force):
            info(f"wrote: {raw_metadata_target.relative_to(vault)}")
        else:
            warn(f"metadata exists, leaving as-is: "
                 f"{raw_metadata_target.relative_to(vault)}")

    if args.transcript_path:
        if move_into_raw(Path(args.transcript_path).expanduser(), raw_transcript_target,
                         force=args.force):
            info(f"wrote: {raw_transcript_target.relative_to(vault)}")
        else:
            warn(f"transcript exists, leaving as-is: "
                 f"{raw_transcript_target.relative_to(vault)}")
    elif not raw_transcript_target.exists():
        warn("no transcript supplied — writing placeholder")
        raw_transcript_target.parent.mkdir(parents=True, exist_ok=True)
        raw_transcript_target.write_text(
            "<!-- no transcript supplied; run helpers/transcribe.sh on the "
            "downloaded audio and re-run with --transcript-path -->\n",
            encoding="utf-8",
        )

    basename = f"{year}-{slug}.md"
    note_target = note_path(vault, KIND, basename)

    raw_meta["raw_transcript"] = raw_transcript_target.relative_to(vault).as_posix()
    raw_meta["raw_metadata"] = (
        raw_metadata_target.relative_to(vault).as_posix()
        if raw_metadata_target.is_file() else None
    )
    raw_meta["raw_audio"] = (
        raw_audio_target.relative_to(vault).as_posix()
        if raw_audio_target.is_file() else None
    )
    raw_meta["transcript_source"] = args.transcript_source
    raw_meta["links"].setdefault("source", f"https://youtu.be/{youtube_id}")
    raw_meta["links"].setdefault(
        "raw", f"[[raw/youtube/{youtube_id}.transcript]]",
    )

    meta = validate_meta(raw_meta, KIND, schema)
    note_body = load_body(args.body_md_path, raw_meta.get("body"))
    is_new = merge_frontmatter(note_target, meta, note_body, force_body=args.force)
    info(f"{'wrote' if is_new else 'updated'}: {note_target.relative_to(vault)}")

    emit_summary([
        ("note", note_target),
        ("raw_transcript", raw_transcript_target),
        ("raw_metadata", raw_metadata_target if raw_metadata_target.is_file() else None),
        ("transcript_source", args.transcript_source),
    ])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
