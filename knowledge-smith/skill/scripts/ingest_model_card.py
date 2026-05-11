#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27",
#   "python-frontmatter>=1.1",
#   "pyyaml>=6.0",
# ]
# ///
"""Write a model-card note + (optionally) raw assets into the active vault.

Thin orchestrator. The agent fetches the source (paper / blog / HF card /
PDF / Raschka diagram), drafts the architecture-rich body markdown
(Model Family, Architecture, Training, Reported Evals, Related),
picks the slug, and supplies metadata. This script copies any source
PDF into raw/model-cards/pdf/ (gitignored) and writes the note via
merge_frontmatter.

Required JSON keys:
    title, slug, year, developer, family, model_type
    (and links.source pointing at paper/blog/announcement URL)

Optional --pdf-path: a local PDF (system card, technical report) to
preserve under raw/model-cards/pdf/<basename>.pdf.

Examples:
  uv run ingest_model_card.py \\
    --metadata-json '{"title":"DeepSeek V3","slug":"deepseek-v3",
                       "year":2024,"developer":"DeepSeek",
                       "family":"DeepSeek-V3","model_type":"llm",
                       "variants":["V3-Base","V3-Chat"],
                       "license":"DeepSeek-LICENSE",
                       "parameters_total":"671B (37B active)"}' \\
    --links-json '{"source":"https://github.com/deepseek-ai/DeepSeek-V3",
                    "paper":"https://arxiv.org/abs/2412.19437"}' \\
    --body-md-path /tmp/note-body.md
"""

from __future__ import annotations

import argparse
import sys
import tempfile
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
    raw_split_path,
    validate_meta,
)
from _ks_helpers import (  # noqa: E402
    copy_into_raw,
    download_pdf,
    emit_summary,
    load_body,
)

KIND = "model-card"


def _materialize_pdf(pdf_path: str | None, pdf_url: str | None,
                     tmpdir: Path) -> Path | None:
    if pdf_path:
        p = Path(pdf_path).expanduser().resolve()
        if not p.is_file():
            die(2, f"--pdf-path is not a file: {p}")
        return p
    if pdf_url:
        info(f"downloading PDF: {pdf_url}")
        target = tmpdir / "input.pdf"
        if not download_pdf(pdf_url, target):
            die(5, f"PDF download failed: {pdf_url}")
        return target
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata-json", required=True,
                   help="JSON metadata, or '-' to read from stdin")
    p.add_argument("--pdf-path",
                   help="local PDF (system card / tech report) to archive")
    p.add_argument("--pdf-url",
                   help="PDF URL to download and archive")
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

    slug = raw_meta.get("slug")
    year = raw_meta.get("year")
    if not (slug and year):
        die(2, "model-card metadata missing slug/year (agent must supply)")

    basename = f"{year}-{slug}.md"
    stem = basename.removesuffix(".md")
    note_target = note_path(vault, KIND, basename)

    raw_pdf_target: Path | None = None
    with tempfile.TemporaryDirectory() as tdir:
        pdf_src = _materialize_pdf(args.pdf_path, args.pdf_url, Path(tdir))
        if pdf_src is not None:
            raw_pdf_target = raw_split_path(vault, KIND, "pdf", f"{stem}.pdf")
            if copy_into_raw(pdf_src, raw_pdf_target, force=args.force):
                info(f"wrote: {raw_pdf_target.relative_to(vault)}")
            else:
                info(f"raw_pdf already present: {raw_pdf_target.relative_to(vault)}")
            raw_meta["raw_pdf"] = raw_pdf_target.relative_to(vault).as_posix()
            raw_meta["links"].setdefault(
                "raw", f"[[raw/model-cards/pdf/{stem}]]",
            )

    meta = validate_meta(raw_meta, KIND, schema)
    note_body = load_body(args.body_md_path, raw_meta.get("body"))
    is_new = merge_frontmatter(note_target, meta, note_body, force_body=args.force)
    info(f"{'wrote' if is_new else 'updated'}: {note_target.relative_to(vault)}")

    emit_summary([
        ("note", note_target),
        ("raw_pdf", raw_pdf_target),
    ])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
