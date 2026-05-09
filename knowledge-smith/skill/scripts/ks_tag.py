#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1"]
# ///
"""Subagent-driven tag plumbing for knowledge-smith notes.

This script does the I/O. The LLM call lives in the *agent harness* — Claude
Code (or Codex) reads the JSONL produced by `list`, dispatches a sonnet
subagent per batch with the controlled vocabulary, and feeds the returned
tags back via `apply`.

Subcommands
-----------
  list [--kind K] [--all] [--force] [--limit N]
      Print:
        - a `# vocab: t1, t2, ...` header (controlled vocabulary)
        - JSONL, one per untagged note:
          {"file": "/abs/path.md", "kind": "paper", "slug": "...",
           "title": "...", "year": YYYY, "abstract": "..."}
        - papers without arxiv have abstract == "" — agent should still
          tag them from title alone.
      Default skips notes that already have non-empty `tags:` (use --force
      to retag).

  apply <file> [tag ...]
      Write the given tags to that file's frontmatter (replacing any
      existing list). Bumps `updated:`. Validates that tags are
      lowercase, kebab-case, 1-30 chars.

Examples
--------
  ks_tag.py list --kind paper > /tmp/ks-tag-plan.jsonl
  # ... agent dispatches subagents on batches; collects {file, tags}
  ks_tag.py apply /path/to/note.md transformer attention nlp
  ks_reading_list.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    KIND_TO_PLURAL,
    die,
    find_vault,
    info,
    load_tag_vocab,
    read_frontmatter,
    today,
    warn,
    write_frontmatter,
)

KINDS = ("paper", "article", "youtube", "blog", "github", "course")
TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
ABSTRACT_HEADERS = ("## Abstract", "## abstract")


def _read_abstract_from_raw(vault: Path, raw_md_rel: str | None) -> str:
    if not raw_md_rel:
        return ""
    p = vault / raw_md_rel
    if not p.is_file():
        return ""
    try:
        meta, body = read_frontmatter(p)
    except Exception:
        return ""
    summary = meta.get("summary") if isinstance(meta, dict) else None
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    text = body.strip()
    return text[:3000] if text else ""


def _abstract_from_body(body: str) -> str:
    for header in ABSTRACT_HEADERS:
        if header in body:
            chunk = body.split(header, 1)[1]
            # stop at next H2
            stop = re.search(r"\n## ", chunk)
            section = chunk[: stop.start()] if stop else chunk
            return section.strip()[:2500]
    return ""


def _build_record(vault: Path, kind: str, md: Path, meta: dict, body: str) -> dict:
    title = str(meta.get("title") or md.stem).strip()
    abstract = ""
    if kind == "paper":
        abstract = _read_abstract_from_raw(vault, meta.get("raw_md")) or _abstract_from_body(body)
    elif kind == "article":
        abstract = _abstract_from_body(body) or body.strip()[:1500]
    elif kind == "youtube":
        abstract = _abstract_from_body(body) or body.strip()[:1500]
    else:  # blog, github, course
        desc = str(meta.get("description") or "").strip()
        abstract = desc or body.strip()[:800]

    return {
        "file": str(md.resolve()),
        "kind": kind,
        "slug": str(meta.get("slug") or md.stem),
        "title": title,
        "year": meta.get("year"),
        "abstract": abstract,
    }


def cmd_list(args: argparse.Namespace) -> int:
    vault = find_vault().path
    info(f"vault: {vault}")
    if not (args.kind or args.all):
        die(2, "must pass --kind <K> or --all")

    vocab = load_tag_vocab(vault)
    print(f"# vocab: {', '.join(vocab)}")
    print(f"# vault: {vault}")
    print("# fields: file, kind, slug, title, year, abstract")
    print("# untagged notes follow as one JSON object per line")

    kinds = list(KINDS) if args.all else [args.kind]
    emitted = 0
    for kind in kinds:
        d = vault / "notes" / KIND_TO_PLURAL[kind]
        if not d.is_dir():
            continue
        for md in sorted(d.glob("*.md")):
            try:
                meta, body = read_frontmatter(md)
            except Exception as exc:
                warn(f"skipping {md}: {exc}")
                continue
            if meta.get("type") != "note" or meta.get("kind") != kind:
                continue
            tags = meta.get("tags") or []
            if tags and not args.force:
                continue
            rec = _build_record(vault, kind, md, meta, body)
            print(json.dumps(rec, ensure_ascii=False))
            emitted += 1
            if args.limit is not None and emitted >= args.limit:
                info(f"hit --limit {args.limit}")
                return 0
    info(f"emitted {emitted} record(s)")
    return 0


def _normalize_tag(t: str) -> str | None:
    t = t.strip().lower().replace("_", "-").replace(" ", "-")
    t = re.sub(r"-+", "-", t).strip("-")
    return t if t and TAG_RE.match(t) else None


def cmd_apply(args: argparse.Namespace) -> int:
    target = Path(args.file).expanduser().resolve()
    if not target.is_file():
        die(2, f"not a file: {target}")
    if not args.tags:
        die(2, "no tags given (usage: apply <file> tag1 tag2 ...)")

    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in args.tags:
        norm = _normalize_tag(raw)
        if not norm:
            warn(f"dropping invalid tag: {raw!r}")
            continue
        if norm in seen:
            continue
        seen.add(norm)
        cleaned.append(norm)
    if not cleaned:
        die(2, "no valid tags after normalization")
    cleaned = cleaned[:5]

    try:
        meta, body = read_frontmatter(target)
    except Exception as exc:
        die(2, f"could not parse {target}: {exc}")

    if meta.get("type") != "note":
        die(2, f"refusing to tag non-note file: {target}")

    meta["tags"] = cleaned
    meta["updated"] = today()
    write_frontmatter(target, meta, body)
    info(f"tagged {target.name}: {cleaned}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="emit vocab + untagged notes as JSONL")
    p_list.add_argument("--kind", choices=KINDS, help="restrict to one kind")
    p_list.add_argument("--all", action="store_true", help="every kind")
    p_list.add_argument("--force", action="store_true",
                        help="include notes that already have tags")
    p_list.add_argument("--limit", type=int, help="cap number of records emitted")

    p_apply = sub.add_parser("apply", help="write tags to a single note")
    p_apply.add_argument("file", help="path to notes/<kind>/<slug>.md")
    p_apply.add_argument("tags", nargs="+", help="2-5 lowercase kebab-case tags")

    args = p.parse_args(argv)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "apply":
        return cmd_apply(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
