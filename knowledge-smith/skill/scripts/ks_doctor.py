#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1"]
# ///
"""Health check + vault scaffolding for knowledge-smith.

Default mode: report active vault, counts in `notes/<kind>/`, frontmatter
validation, orphan raws, stale references, tag aggregation, reading-list
freshness.

`--init <path>` mode: scaffold a new vault at <path> by copying
`vault-template/` from this skill bundle. Refuses if <path> already exists
and is non-empty (other than `.git`).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    KIND_TO_PLURAL,
    die,
    find_vault,
    info,
    read_frontmatter,
    warn,
)

KINDS = ("paper", "article", "youtube", "blog", "github")
RAW_KINDS_WITH_DIR = {"paper": "papers", "article": "articles", "youtube": "youtube"}


def _vault_template_dir() -> Path:
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

    counts, read_counts = _count_notes(vault.path)
    total_notes = sum(counts.values())
    total_unread = sum(counts[k] - read_counts.get(k, 0) for k in counts)
    print(f"notes/ ({total_notes} total, {total_unread} unread)")
    for kind in KINDS:
        c = counts.get(kind, 0)
        r = read_counts.get(kind, 0)
        unread = c - r
        print(f"  {KIND_TO_PLURAL[kind]:8s}  {c:4d} total  ({unread:4d} unread)")
    print()

    issues = _validate(vault.path)
    if issues:
        print(f"validation issues ({len(issues)})")
        for issue in issues[:30]:
            print(f"  {issue}")
        if len(issues) > 30:
            print(f"  ... and {len(issues) - 30} more")
        print()
    else:
        print("validation: ok")

    orphans = _find_orphan_raws(vault.path)
    if orphans:
        print(f"orphan raw files ({len(orphans)})")
        for path in orphans[:20]:
            print(f"  {path.relative_to(vault.path)}")
        if len(orphans) > 20:
            print(f"  ... and {len(orphans) - 20} more")
        print()

    stale = _find_stale_refs(vault.path)
    if stale:
        print(f"stale binary refs ({len(stale)}) — run recover_raw.py")
        for path, missing in stale[:20]:
            print(f"  {path.relative_to(vault.path)} -> {missing}")
        if len(stale) > 20:
            print(f"  ... and {len(stale) - 20} more")
        print()

    rl_status = _reading_list_freshness(vault.path)
    if rl_status:
        print("reading-list")
        for line in rl_status:
            print(f"  {line}")
        print()

    tags = _aggregate_tags(vault.path)
    if tags:
        print("tags (top 20)")
        for tag, count in tags.most_common(20):
            print(f"  {count:4d}  {tag}")

    return 1 if issues else 0


def _count_notes(vault: Path) -> tuple[Counter[str], Counter[str]]:
    counts: Counter[str] = Counter()
    read_counts: Counter[str] = Counter()
    notes_root = vault / "notes"
    if not notes_root.is_dir():
        return counts, read_counts
    for kind in KINDS:
        d = notes_root / KIND_TO_PLURAL[kind]
        if not d.is_dir():
            continue
        for md in d.rglob("*.md"):
            counts[kind] += 1
            meta, _ = _safe_read(md)
            if meta and meta.get("read") is True:
                read_counts[kind] += 1
    return counts, read_counts


def _safe_read(path: Path) -> tuple[dict | None, str | None]:
    try:
        meta, body = read_frontmatter(path)
        return meta, body
    except Exception as exc:
        warn(f"failed to parse {path}: {exc}")
        return None, None


REQUIRED_CORE = ("type", "slug", "title", "created", "updated")


def _validate(vault: Path) -> list[str]:
    issues: list[str] = []
    notes_root = vault / "notes"
    if not notes_root.is_dir():
        return issues
    for kind in KINDS:
        d = notes_root / KIND_TO_PLURAL[kind]
        if not d.is_dir():
            continue
        for md in d.rglob("*.md"):
            meta, _ = _safe_read(md)
            if meta is None:
                issues.append(f"{md.relative_to(vault)}: unparseable frontmatter")
                continue
            for field in REQUIRED_CORE:
                if field not in meta:
                    issues.append(f"{md.relative_to(vault)}: missing '{field}'")
            if meta.get("type") != "note":
                issues.append(f"{md.relative_to(vault)}: type must be 'note'")
            if meta.get("kind") != kind:
                issues.append(f"{md.relative_to(vault)}: kind must be {kind!r}")
            if "read" not in meta or not isinstance(meta.get("read"), bool):
                issues.append(f"{md.relative_to(vault)}: missing or non-bool 'read'")
    return issues


def _find_orphan_raws(vault: Path) -> list[Path]:
    raw_root = vault / "raw"
    if not raw_root.is_dir():
        return []
    referenced: set[str] = set()
    notes_root = vault / "notes"
    if notes_root.is_dir():
        for md in notes_root.rglob("*.md"):
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
    stale: list[tuple[Path, str]] = []
    notes_root = vault / "notes"
    if not notes_root.is_dir():
        return stale
    for md in notes_root.rglob("*.md"):
        meta, _ = _safe_read(md)
        if not meta:
            continue
        for key in ("raw_pdf", "raw_md", "raw_audio", "raw_transcript", "raw_metadata"):
            val = meta.get(key)
            if isinstance(val, str) and val:
                if not (vault / val).exists():
                    stale.append((md, val))
    return stale


def _reading_list_freshness(vault: Path) -> list[str]:
    rl = vault / "reading-list"
    if not rl.is_dir():
        return ["no reading-list/ directory — run ks_reading_list.py --all"]
    lines = []
    for kind in KINDS:
        page = rl / f"{KIND_TO_PLURAL[kind]}.md"
        if not page.is_file():
            lines.append(f"{KIND_TO_PLURAL[kind]:8s}  not generated — run ks_reading_list.py --kind {kind}")
            continue
        meta, _ = _safe_read(page)
        gen = meta.get("generated") if meta else None
        if not isinstance(gen, str):
            lines.append(f"{KIND_TO_PLURAL[kind]:8s}  unparseable 'generated:' field")
            continue
        try:
            gen_dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - gen_dt).days
            stale_marker = " (stale)" if age_days > 7 else ""
            lines.append(f"{KIND_TO_PLURAL[kind]:8s}  generated {gen_dt.date()} ({age_days}d ago){stale_marker}")
        except ValueError:
            lines.append(f"{KIND_TO_PLURAL[kind]:8s}  generated: {gen}")
    return lines


def _aggregate_tags(vault: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    notes_root = vault / "notes"
    if not notes_root.is_dir():
        return counts
    for md in notes_root.rglob("*.md"):
        meta, _ = _safe_read(md)
        if not meta:
            continue
        for tag in meta.get("tags", []) or []:
            if isinstance(tag, str) and tag.strip():
                counts[tag.strip()] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--init", metavar="PATH", help="scaffold a new vault at PATH")
    args = p.parse_args(argv)

    if args.init:
        return cmd_init(Path(args.init))
    return cmd_report()


if __name__ == "__main__":
    raise SystemExit(main())
