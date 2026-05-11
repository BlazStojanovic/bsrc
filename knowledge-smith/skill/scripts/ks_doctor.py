#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter>=1.1", "pyyaml>=6.0"]
# ///
"""Health check, scaffolding, and migration for knowledge-smith.

Modes:
  (default)            Report active vault, counts in `notes/<kind>/`,
                       schema-driven frontmatter validation, orphan raws,
                       stale references, tag aggregation, reading-list
                       freshness.

  --init <path>        Scaffold a new vault at <path> by copying
                       `vault-template/` from this skill bundle.

  --migrate            One-shot, idempotent migration that lifts old-shape
                       fields into the current schema (`url` → `links.source`,
                       `arxiv` → `links.paper`, `raw_pdf` → `links.raw`,
                       inject `owner`, prepend namespaced `type/<kind>` tag,
                       convert `read/read|unread` tags to the `read:`
                       boolean). Combine with `--dry-run` to preview.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ks_common import (  # noqa: E402
    KIND_TO_PLURAL,
    Schema,
    die,
    find_vault,
    info,
    load_schema,
    read_frontmatter,
    today,
    validate_meta,
    warn,
    write_frontmatter,
)


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

def _safe_read(path: Path) -> tuple[dict | None, str | None]:
    try:
        meta, body = read_frontmatter(path)
        return meta, body
    except Exception as exc:
        warn(f"failed to parse {path}: {exc}")
        return None, None


def cmd_report() -> int:
    vault = find_vault()
    schema = load_schema(vault.path)
    print(f"vault: {vault.path}")
    print(f"rule:  {vault.rule}")
    print(f"schema sources: {[str(s) for s in schema.sources]}")
    print()

    counts, read_counts = _count_notes(vault.path, schema)
    total_notes = sum(counts.values())
    total_unread = sum(counts[k] - read_counts.get(k, 0) for k in counts)
    print(f"notes/ ({total_notes} total, {total_unread} unread)")
    for kind in schema.all_kinds():
        c = counts.get(kind, 0)
        r = read_counts.get(kind, 0)
        unread = c - r
        plural = KIND_TO_PLURAL.get(kind, kind)
        print(f"  {plural:14s}  {c:4d} total  ({unread:4d} unread)")
    print()

    issues = _validate(vault.path, schema)
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

    rl_status = _reading_list_freshness(vault.path, schema)
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


def _count_notes(vault: Path, schema: Schema) -> tuple[Counter[str], Counter[str]]:
    counts: Counter[str] = Counter()
    read_counts: Counter[str] = Counter()
    notes_root = vault / "notes"
    if not notes_root.is_dir():
        return counts, read_counts
    for kind in schema.all_kinds():
        d = notes_root / KIND_TO_PLURAL.get(kind, kind)
        if not d.is_dir():
            continue
        for md in d.rglob("*.md"):
            counts[kind] += 1
            meta, _ = _safe_read(md)
            if meta and meta.get("read") is True:
                read_counts[kind] += 1
    return counts, read_counts


def _validate(vault: Path, schema: Schema) -> list[str]:
    """Schema-driven validation — runs validate_meta against every note."""
    issues: list[str] = []
    notes_root = vault / "notes"
    if not notes_root.is_dir():
        return issues

    cc_required = schema.common_core.get("required", [])
    for kind in schema.all_kinds():
        d = notes_root / KIND_TO_PLURAL.get(kind, kind)
        if not d.is_dir():
            continue
        spec = schema.kind_spec(kind)
        for md in d.rglob("*.md"):
            meta, _ = _safe_read(md)
            rel = md.relative_to(vault)
            if meta is None:
                issues.append(f"{rel}: unparseable frontmatter")
                continue

            # Common-core presence.
            for field in cc_required:
                if field not in meta:
                    issues.append(f"{rel}: missing common-core '{field}'")
            if meta.get("kind") not in (kind, None):
                issues.append(
                    f"{rel}: kind={meta.get('kind')!r} but file is under {kind}/"
                )
            if "read" in meta and not isinstance(meta["read"], bool):
                issues.append(f"{rel}: 'read' must be bool, got {type(meta['read']).__name__}")

            # Per-kind required fields.
            for field in spec.get("required", []):
                if not meta.get(field):
                    issues.append(f"{rel}: missing per-kind '{field}'")

            # Per-kind required links.
            links = meta.get("links")
            if not isinstance(links, dict):
                issues.append(f"{rel}: missing or non-dict 'links' block")
            else:
                for lk in spec.get("required_links", []):
                    if not links.get(lk):
                        issues.append(f"{rel}: missing links.{lk}")

            # Legacy field detection (warn-style — included as issues for now).
            for legacy in ("url", "arxiv"):
                if legacy in meta and meta.get("links", {}).get("source") is None and \
                        meta.get("links", {}).get("paper") is None:
                    issues.append(
                        f"{rel}: legacy '{legacy}' present without links — run --migrate"
                    )
                    break

            # model-card structural lint: body should contain a `## Architecture` H2.
            if kind == "model-card":
                _, body = _safe_read(md)
                if body and "## Architecture" not in body:
                    issues.append(f"{rel}: model-card body missing `## Architecture` section")
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


def _reading_list_freshness(vault: Path, schema: Schema) -> list[str]:
    rl = vault / "reading-list"
    if not rl.is_dir():
        return ["no reading-list/ directory — run ks_reading_list.py --all"]
    lines = []
    for kind in schema.all_kinds():
        plural = KIND_TO_PLURAL.get(kind, kind)
        page = rl / f"{plural}.md"
        if not page.is_file():
            lines.append(f"{plural:14s}  not generated — run ks_reading_list.py --kind {kind}")
            continue
        meta, _ = _safe_read(page)
        gen = meta.get("generated") if meta else None
        if not isinstance(gen, str):
            lines.append(f"{plural:14s}  unparseable 'generated:' field")
            continue
        try:
            gen_dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - gen_dt).days
            stale_marker = " (stale)" if age_days > 7 else ""
            lines.append(
                f"{plural:14s}  generated {gen_dt.date()} ({age_days}d ago){stale_marker}"
            )
        except ValueError:
            lines.append(f"{plural:14s}  generated: {gen}")
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


# ---------------------------------------------------------------------------
# migrate mode
# ---------------------------------------------------------------------------

def cmd_migrate(kind_filter: str | None, dry_run: bool) -> int:
    """Idempotently lift old-shape notes into the current schema.

    For every note under notes/<kind>/, derive the canonical shape and
    write it back via merge_frontmatter (which preserves user-edited
    fields by default). Logs a per-file summary of the transformation.
    """
    vault = find_vault()
    schema = load_schema(vault.path)
    info(f"vault: {vault.path}")
    info(f"mode:  {'dry-run' if dry_run else 'apply'}")

    notes_root = vault.path / "notes"
    if not notes_root.is_dir():
        die(2, "no notes/ directory in vault")

    kinds = (kind_filter,) if kind_filter else schema.all_kinds()
    touched = 0
    skipped = 0
    for kind in kinds:
        d = notes_root / KIND_TO_PLURAL.get(kind, kind)
        if not d.is_dir():
            continue
        spec = schema.kind_spec(kind)
        for md in d.rglob("*.md"):
            meta, body = _safe_read(md)
            if meta is None:
                continue
            new_meta = _migrate_one(dict(meta), kind, spec)
            try:
                validated = validate_meta(new_meta, kind, schema)
            except SystemExit as exc:
                warn(f"{md.relative_to(vault.path)}: validate_meta failed ({exc}) — skipping")
                skipped += 1
                continue
            if validated == meta:
                continue
            touched += 1
            rel = md.relative_to(vault.path)
            diff = _diff(meta, validated)
            info(f"{rel}: {diff}")
            if not dry_run:
                # Re-write with merged frontmatter; body unchanged.
                write_frontmatter(md, validated, body or "")
    print()
    print(f"migrate: touched={touched} skipped={skipped} ({'dry-run' if dry_run else 'applied'})")
    return 0


def _migrate_one(meta: dict[str, Any], kind: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Lift legacy fields into the new shape. Idempotent."""
    out = dict(meta)
    out["kind"] = kind
    out.setdefault("type", "note")

    # links: { source, paper, code, raw } block.
    links = dict(out.get("links") or {})
    legacy_url = out.pop("url", None)        # drop legacy top-level url after lifting
    if legacy_url and not links.get("source") and not links.get("paper"):
        links["source"] = legacy_url
    if out.get("arxiv") and not links.get("paper"):
        links["paper"] = f"https://arxiv.org/abs/{out['arxiv']}"
    if out.get("raw_pdf") and not links.get("raw"):
        # Wikilink to the parsed-md sibling when paper-style; otherwise the pdf path stem.
        rp = str(out["raw_pdf"])
        if rp.startswith("raw/papers/pdf/") and rp.endswith(".pdf"):
            stem = Path(rp).stem
            links["raw"] = f"[[raw/papers/md/{stem}]]"
        elif rp.endswith(".pdf"):
            links["raw"] = f"[[{rp.removesuffix('.pdf')}]]"
    # Canonicalize links to the schema's link_keys order; missing keys → None.
    canonical = {k: links.get(k) for k in spec.get("link_keys", [])}
    out["links"] = canonical

    # Convert legacy read/unread or read/read tags to the read: boolean.
    tags = list(out.get("tags") or [])
    if "read/read" in tags:
        out["read"] = True
    elif "read/unread" in tags:
        out.setdefault("read", False)
    out.setdefault("read", False)
    tags = [t for t in tags if t not in ("read/read", "read/unread")]

    # Inject namespaced type/<kind> tag if absent.
    type_tag = f"type/{kind}"
    if type_tag not in tags:
        tags.insert(0, type_tag)
    out["tags"] = tags

    out.setdefault("owner", "blaz")
    out.setdefault("created", today())
    out.setdefault("updated", today())

    return out


def _diff(old: dict[str, Any], new: dict[str, Any]) -> str:
    changes: list[str] = []
    keys = set(old) | set(new)
    for k in sorted(keys):
        if old.get(k) != new.get(k):
            old_v = old.get(k, "<absent>")
            new_v = new.get(k, "<absent>")
            ov = repr(old_v) if not isinstance(old_v, (dict, list)) else f"<{type(old_v).__name__}>"
            nv = repr(new_v) if not isinstance(new_v, (dict, list)) else f"<{type(new_v).__name__}>"
            changes.append(f"{k}: {ov} → {nv}")
    return ", ".join(changes) if changes else "(no change)"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--init", metavar="PATH", help="scaffold a new vault at PATH")
    p.add_argument("--migrate", action="store_true",
                   help="run idempotent schema migration over existing notes")
    p.add_argument("--kind", help="limit --migrate to one kind")
    p.add_argument("--dry-run", action="store_true",
                   help="show what --migrate would change, but write nothing")
    args = p.parse_args(argv)

    if args.init:
        return cmd_init(Path(args.init))
    if args.migrate:
        return cmd_migrate(args.kind, args.dry_run)
    return cmd_report()


if __name__ == "__main__":
    raise SystemExit(main())
