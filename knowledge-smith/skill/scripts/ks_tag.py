#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "anthropic>=0.39",
#   "python-frontmatter>=1.1",
# ]
# ///
"""LLM-suggest tags for knowledge-smith notes via the Anthropic API.

For each note (default: notes/<kind>/*.md with empty `tags:`), call Claude
with title + abstract/description and parse 2-5 lowercase kebab-case tags.
The controlled vocabulary (vault-overridable via `.ks-tag-vocab`) is sent in
a cached system prompt so the per-paper user message stays tiny.

Reads ANTHROPIC_API_KEY from env. No-ops if the key is missing.

Examples:
    ks_tag.py --kind paper                  # tag all un-tagged paper notes
    ks_tag.py --kind paper --force          # re-tag (overwrite existing)
    ks_tag.py --kind paper --model haiku    # cheaper run
    ks_tag.py --all                         # all kinds
"""

from __future__ import annotations

import argparse
import json
import os
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

KINDS = ("paper", "article", "youtube", "blog", "github")

MODEL_ALIASES = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-7",
}
DEFAULT_MODEL = "claude-sonnet-4-6"

TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")


def _resolve_model(arg: str | None) -> str:
    if not arg:
        return DEFAULT_MODEL
    return MODEL_ALIASES.get(arg, arg)


def _system_prompt(vocab: list[str]) -> str:
    return (
        "You assign topical tags to research-source notes in a personal "
        "knowledge base. Pick 2 to 5 short, lowercase, kebab-case tags that "
        "describe the technical/topical content of the source.\n\n"
        "PREFERRED VOCABULARY (use these whenever they fit; you may add "
        "free-form tags only when none of these are accurate):\n"
        + "\n".join(f"- {v}" for v in vocab)
        + "\n\nSTRICT OUTPUT FORMAT — return only JSON of the form:\n"
        '  {"tags": ["tag-one", "tag-two"]}\n'
        "Do not output any prose. Do not output Markdown fences. JSON only."
    )


def _user_prompt_for_paper(meta: dict, abstract: str | None) -> str:
    title = str(meta.get("title") or "").strip() or "(untitled)"
    authors = meta.get("authors") or []
    year = meta.get("year")
    venue = meta.get("venue")
    arxiv = meta.get("arxiv")
    head = [f"TITLE: {title}"]
    if authors:
        head.append("AUTHORS: " + ", ".join(str(a) for a in authors[:6]))
    if year:
        head.append(f"YEAR: {year}")
    if venue:
        head.append(f"VENUE: {venue}")
    if arxiv:
        head.append(f"ARXIV: {arxiv}")
    if abstract:
        head.append(f"\nABSTRACT:\n{abstract.strip()[:2000]}")
    return "\n".join(head)


def _user_prompt_for_article(meta: dict, body: str) -> str:
    title = str(meta.get("title") or "").strip() or "(untitled)"
    head = [f"TITLE: {title}"]
    if meta.get("author"):
        head.append(f"AUTHOR: {meta['author']}")
    if meta.get("publication"):
        head.append(f"PUBLICATION: {meta['publication']}")
    if meta.get("year"):
        head.append(f"YEAR: {meta['year']}")
    excerpt = body.strip()[:1500]
    if excerpt:
        head.append(f"\nEXCERPT:\n{excerpt}")
    return "\n".join(head)


def _user_prompt_for_youtube(meta: dict, body: str) -> str:
    title = str(meta.get("title") or "").strip() or "(untitled)"
    head = [f"TITLE: {title}"]
    if meta.get("channel"):
        head.append(f"CHANNEL: {meta['channel']}")
    excerpt = body.strip()[:1200]
    if excerpt:
        head.append(f"\nDESCRIPTION/SUMMARY:\n{excerpt}")
    return "\n".join(head)


def _user_prompt_for_bookmark(meta: dict, body: str) -> str:
    title = str(meta.get("title") or "").strip() or "(untitled)"
    head = [f"TITLE: {title}"]
    if meta.get("description"):
        head.append(f"DESCRIPTION: {meta['description']}")
    if meta.get("url"):
        head.append(f"URL: {meta['url']}")
    excerpt = body.strip()[:800]
    if excerpt:
        head.append(f"\nNOTE:\n{excerpt}")
    return "\n".join(head)


def _abstract_from_raw_md(vault: Path, raw_md_rel: str | None) -> str | None:
    if not raw_md_rel:
        return None
    p = vault / raw_md_rel
    if not p.is_file():
        return None
    try:
        meta, body = read_frontmatter(p)
    except Exception:
        return None
    summary = meta.get("summary") if isinstance(meta, dict) else None
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    text = body.strip()
    if text:
        return text[:3000]
    return None


def _build_user_prompt(kind: str, vault: Path, meta: dict, body: str) -> str:
    if kind == "paper":
        abstract = _abstract_from_raw_md(vault, meta.get("raw_md"))
        if not abstract and body:
            for header in ("## Abstract", "## abstract"):
                if header in body:
                    abstract = body.split(header, 1)[1].strip()[:2000]
                    break
        return _user_prompt_for_paper(meta, abstract)
    if kind == "article":
        return _user_prompt_for_article(meta, body)
    if kind == "youtube":
        return _user_prompt_for_youtube(meta, body)
    return _user_prompt_for_bookmark(meta, body)


def _parse_tags(text: str) -> list[str]:
    text = text.strip()
    # Strip code fences if any leaked in.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    raw = data.get("tags") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for t in raw:
        if not isinstance(t, str):
            continue
        t = t.strip().lower().replace("_", "-").replace(" ", "-")
        t = re.sub(r"-+", "-", t).strip("-")
        if t and TAG_RE.match(t):
            out.append(t)
    # de-dup preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:5]


def _call_claude(client, model: str, system_prompt: str, user_prompt: str) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=200,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )
    parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", choices=KINDS, help="restrict to one kind")
    p.add_argument("--all", action="store_true", help="tag every kind")
    p.add_argument("--force", action="store_true", help="retag even if tags already set")
    p.add_argument("--model", help="haiku|sonnet|opus or full model id")
    p.add_argument("--limit", type=int, default=None, help="cap number of notes processed")
    p.add_argument("--dry-run", action="store_true", help="print suggested tags without writing")
    args = p.parse_args(argv)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        die(20, "ANTHROPIC_API_KEY not set")

    if not (args.kind or args.all):
        p.error("must pass --kind <K> or --all")

    try:
        from anthropic import Anthropic  # type: ignore[import-not-found]
    except Exception as exc:
        die(21, f"failed to import anthropic SDK: {exc}")

    vault = find_vault().path
    info(f"vault: {vault}")

    vocab = load_tag_vocab(vault)
    sys_prompt = _system_prompt(vocab)
    model = _resolve_model(args.model)
    info(f"model: {model}  vocab: {len(vocab)} entries")

    client = Anthropic(api_key=api_key)

    kinds = list(KINDS) if args.all else [args.kind]
    targets: list[tuple[str, Path]] = []
    for kind in kinds:
        plural = KIND_TO_PLURAL[kind]
        d = vault / "notes" / plural
        if not d.is_dir():
            continue
        for md in sorted(d.glob("*.md")):
            try:
                meta, _ = read_frontmatter(md)
            except Exception as exc:
                warn(f"skipping {md}: {exc}")
                continue
            if meta.get("type") != "note" or meta.get("kind") != kind:
                continue
            tags = meta.get("tags") or []
            if tags and not args.force:
                continue
            targets.append((kind, md))

    if args.limit:
        targets = targets[: args.limit]

    info(f"to tag: {len(targets)}")
    ok = 0
    fail = 0
    for i, (kind, md) in enumerate(targets, 1):
        try:
            meta, body = read_frontmatter(md)
        except Exception as exc:
            warn(f"[{i}] {md.name}: parse failed: {exc}")
            fail += 1
            continue
        user_prompt = _build_user_prompt(kind, vault, meta, body)
        try:
            text = _call_claude(client, model, sys_prompt, user_prompt)
        except Exception as exc:
            warn(f"[{i}] {md.name}: API call failed: {exc}")
            fail += 1
            continue
        tags = _parse_tags(text)
        if not tags:
            warn(f"[{i}] {md.name}: empty tag set (raw: {text[:80]!r})")
            fail += 1
            continue
        print(f"[{i:3d}/{len(targets)}] {md.name} -> {tags}")
        if args.dry_run:
            ok += 1
            continue
        meta["tags"] = tags
        meta["updated"] = today()
        write_frontmatter(md, meta, body)
        ok += 1

    print(f"\nTOTAL: {len(targets)}  ok={ok}  fail={fail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
