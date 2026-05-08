#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1"]
# ///
"""Health check + vault scaffolding for knowledge-smith.

Default mode: report active vault, counts, frontmatter validation, orphan
raws, stale references, unindexed sources, tag aggregation.

`--init <path>` mode: scaffold a new vault at <path> by copying
`vault-template/` from this skill bundle. Refuses if <path> already exists
and is non-empty (other than `.git`).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    die,
    find_vault,
    info,
    read_frontmatter,
    warn,
)

SOURCE_KINDS = ("paper", "article", "youtube", "blog", "github")
SOURCE_DIR = {
    "paper": "papers",
    "article": "articles",
    "youtube": "youtube",
    "blog": "blogs",
    "github": "github",
}
RAW_KINDS_WITH_DIR = {"paper": "papers", "article": "articles", "youtube": "youtube"}


def _vault_template_dir() -> Path:
    """Locate vault-template/ alongside the skill bundle.

    Path resolution follows symlinks back to bsrc/knowledge-smith/vault-template.
    """
    here = Path(__file__).resolve()
    candidate = here.parent.parent.parent / "vault-template"
    if not candidate.is_dir():
        die(11, f"vault-template not found at expected path: {candidate}")
    return candidate


# ---------------------------------------------------------------------------
# init mode
# ---------------------------------------------------------------------------

def cmd_init(target: Path) -> int:
    target = target.expanduser().resolve()

    if target.exists():
        # Allow if only a .git/ dir exists (user pre-created a repo).
        contents = [p for p in target.iterdir() if p.name != ".git"]
        if contents:
            die(
                12,
                f"target is non-empty: {target}\n"
                "Refusing to scaffold into a non-empty directory "
                "(only .git/ is tolerated).",
            )
    else:
        target.mkdir(parents=True)

    template = _vault_template_dir()
    info(f"copying vault-template -> {target}")
    _copytree(template, target)
    info("vault initialized")
    info(f"  cd {target}")
    if not (target / ".git").exists():
        info("  git init && git add -A && git commit -m 'init knowledge-smith vault'")
    return 0


def _copytree(src: Path, dst: Path) -> None:
    """Copy src into dst without overwriting existing files."""
    for entry in src.iterdir():
        target = dst / entry.name
        if entry.is_dir():
            target.mkdir(exist_ok=True)
            _copytree(entry, target)
        else:
            if target.exists():
                continue
            shutil.copy2(entry, target)


# ---------------------------------------------------------------------------
# default (report) mode
# ---------------------------------------------------------------------------

def cmd_report() -> int:
    vault = find_vault()
    print(f"vault: {vault.path}")
    print(f"rule:  {vault.rule}")
    print()

    inbox_counts, source_counts = _count_sources(vault.path)
    print("counts")
    print(f"  inbox/                     {sum(inbox_counts.values())}")
    for kind in SOURCE_KINDS:
        print(f"    {kind:8s}                 {inbox_counts.get(kind, 0)}")
    print(f"  sources/                   {sum(source_counts.values())}")
    for kind in SOURCE_KINDS:
        print(f"    {SOURCE_DIR[kind]:8s}                 {source_counts.get(kind, 0)}")
    notes_count = _count_files(vault.path / "notes")
    topics_count = _count_files(vault.path / "topics")
    print(f"  notes/                     {notes_count}")
    print(f"  topics/                    {topics_count}")
    print()

    issues = _validate(vault.path)
    if issues:
        print(f"validation issues ({len(issues)})")
        for issue in issues:
            print(f"  {issue}")
        print()
    else:
        print("validation: ok")

    orphans = _find_orphan_raws(vault.path)
    if orphans:
        print(f"orphan raw files ({len(orphans)})")
        for path in orphans:
            print(f"  {path.relative_to(vault.path)}")
        print()

    stale = _find_stale_refs(vault.path)
    if stale:
        # Stale gitignored binaries (PDF, audio) are expected after a fresh
        # clone — that's why recover_raw.py exists. Report as info, not error.
        print(f"stale binary refs ({len(stale)}) — run recover_raw.py")
        for path, missing in stale:
            print(f"  {path.relative_to(vault.path)} -> {missing}")
        print()

    unindexed = _find_unindexed(vault.path)
    if unindexed:
        print(f"unindexed registered sources ({len(unindexed)})")
        for path in unindexed:
            print(f"  {path.relative_to(vault.path)}")
        print()

    tags = _aggregate_tags(vault.path)
    if tags:
        print("tags (top 20)")
        for tag, count in tags.most_common(20):
            print(f"  {count:4d}  {tag}")

    has_errors = bool(issues)
    return 1 if has_errors else 0


def _count_sources(vault: Path) -> tuple[Counter[str], Counter[str]]:
    inbox = Counter()
    sources = Counter()
    for md in (vault / "inbox").rglob("*.md"):
        meta, _ = _safe_read(md)
        kind = meta.get("source_kind") if meta else None
        if isinstance(kind, str):
            inbox[kind] += 1
    for kind in SOURCE_KINDS:
        d = vault / "sources" / SOURCE_DIR[kind]
        if d.is_dir():
            for md in d.rglob("*.md"):
                sources[kind] += 1
    return inbox, sources


def _count_files(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for _ in path.rglob("*.md"))


def _safe_read(path: Path) -> tuple[dict | None, str | None]:
    try:
        meta, body = read_frontmatter(path)
        return meta, body
    except Exception as exc:
        warn(f"failed to parse {path}: {exc}")
        return None, None


REQUIRED_CORE = ("type", "status", "slug", "title", "created", "updated")


def _validate(vault: Path) -> list[str]:
    issues: list[str] = []
    for sub in ("inbox", "sources", "notes", "topics"):
        root = vault / sub
        if not root.is_dir():
            continue
        for md in root.rglob("*.md"):
            meta, _ = _safe_read(md)
            if meta is None:
                issues.append(f"{md.relative_to(vault)}: unparseable frontmatter")
                continue
            for field in REQUIRED_CORE:
                if field not in meta:
                    issues.append(f"{md.relative_to(vault)}: missing '{field}'")
            t = meta.get("type")
            if t == "source":
                if "source_kind" not in meta:
                    issues.append(f"{md.relative_to(vault)}: source missing 'source_kind'")
                if "id" not in meta:
                    issues.append(f"{md.relative_to(vault)}: source missing 'id'")
    return issues


def _find_orphan_raws(vault: Path) -> list[Path]:
    """Files under raw/ that no inbox/sources entry references."""
    raw_root = vault / "raw"
    if not raw_root.is_dir():
        return []
    referenced: set[str] = set()
    for sub in ("inbox", "sources"):
        root = vault / sub
        if not root.is_dir():
            continue
        for md in root.rglob("*.md"):
            meta, _ = _safe_read(md)
            if not meta:
                continue
            for key in ("raw_pdf", "raw_md", "raw_audio", "raw_transcript", "raw_metadata"):
                val = meta.get(key)
                if isinstance(val, str):
                    referenced.add(val)
    orphans: list[Path] = []
    for f in raw_root.rglob("*"):
        if not f.is_file() or f.name == ".gitkeep":
            continue
        rel = f.relative_to(vault).as_posix()
        if rel not in referenced:
            orphans.append(f)
    return orphans


def _find_stale_refs(vault: Path) -> list[tuple[Path, str]]:
    """Source notes referencing raw_* paths that don't exist on disk."""
    stale: list[tuple[Path, str]] = []
    for sub in ("inbox", "sources"):
        root = vault / sub
        if not root.is_dir():
            continue
        for md in root.rglob("*.md"):
            meta, _ = _safe_read(md)
            if not meta:
                continue
            for key in ("raw_pdf", "raw_md", "raw_audio", "raw_transcript", "raw_metadata"):
                val = meta.get(key)
                if isinstance(val, str) and val:
                    target = vault / val
                    if not target.exists():
                        stale.append((md, val))
    return stale


def _find_unindexed(vault: Path) -> list[Path]:
    """sources/ files with status registered/indexed not referenced from any note's `sources:`."""
    sources_root = vault / "sources"
    notes_root = vault / "notes"
    if not sources_root.is_dir():
        return []

    referenced: set[str] = set()
    if notes_root.is_dir():
        for md in notes_root.rglob("*.md"):
            meta, _ = _safe_read(md)
            if not meta:
                continue
            for ref in meta.get("sources", []) or []:
                if isinstance(ref, str):
                    referenced.add(ref.strip("[]"))

    unindexed: list[Path] = []
    for md in sources_root.rglob("*.md"):
        meta, _ = _safe_read(md)
        if not meta:
            continue
        if meta.get("status") not in ("registered", "indexed"):
            continue
        # The slug we'd see in a [[wikilink]] is the filename without ext,
        # optionally prefixed with sources/<kind>/.
        rel = md.relative_to(vault).with_suffix("").as_posix()
        candidates = {rel, md.stem}
        if not (referenced & candidates):
            unindexed.append(md)
    return unindexed


def _aggregate_tags(vault: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    for sub in ("inbox", "sources", "notes", "topics"):
        root = vault / sub
        if not root.is_dir():
            continue
        for md in root.rglob("*.md"):
            meta, _ = _safe_read(md)
            if not meta:
                continue
            for tag in meta.get("tags", []) or []:
                if isinstance(tag, str) and tag.strip():
                    counts[tag.strip()] += 1
    return counts


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--init", metavar="PATH", help="scaffold a new vault at PATH")
    args = p.parse_args(argv)

    if args.init:
        return cmd_init(Path(args.init))
    return cmd_report()


if __name__ == "__main__":
    raise SystemExit(main())
