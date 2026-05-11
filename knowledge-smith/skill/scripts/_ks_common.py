"""Shared helpers for knowledge-smith ingest/recover/doctor scripts.

This module is imported by every runner script via:

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _ks_common import find_vault, load_schema, validate_meta, ...

It is not invoked directly. The importing runner declares its own PEP 723
deps (must include `python-frontmatter` and `pyyaml`).
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, NoReturn

import frontmatter  # type: ignore[import-not-found]
import yaml  # type: ignore[import-not-found]


VAULT_MARKER = ".knowledge-smith"
ENV_VAR = "KNOWLEDGE_SMITH_VAULT"
SCHEMA_OVERRIDE_FILE = ".ks-schema.yaml"
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent / "_ks_schema.yaml"

Kind = Literal[
    "paper", "model-card", "article", "youtube",
    "blog", "post", "github", "course",
]
KIND_TO_PLURAL: dict[str, str] = {
    "paper": "papers",
    "model-card": "model-cards",
    "article": "articles",
    "youtube": "youtube",
    "blog": "blogs",
    "post": "posts",
    "github": "github",
    "course": "courses",
}
# Subset of kinds that have associated raw assets on disk.
RAW_DIRS: dict[str, str] = {
    "paper": "papers",
    "model-card": "model-cards",
    "article": "articles",
    "youtube": "youtube",
}
# Kinds whose raw/<folder>/ is split into <ext>/ subdirs (binaries gitignored).
RAW_SPLIT: dict[str, tuple[str, ...]] = {
    "paper": ("pdf", "md"),
    "model-card": ("pdf", "md"),
}

# Default tag vocabulary used by ks_tag.py. A vault may override by writing
# its own one-tag-per-line file at <vault>/.ks-tag-vocab.
DEFAULT_TAG_VOCAB: list[str] = [
    "ml", "transformer", "attention", "tabular", "gnn", "llm", "rag",
    "retrieval", "fairness", "calibration", "uncertainty", "benchmark",
    "fine-tuning", "pretraining", "self-supervised", "contrastive",
    "distillation", "interpretability", "missing-data",
    "mixture-of-experts", "scaling-laws", "agents", "rl", "optimization",
    "generalization", "theory", "reproducibility", "vision", "nlp",
    "recsys", "diffusion", "rlhf", "alignment", "evaluation", "book",
    "survey",
]


# ---------------------------------------------------------------------------
# Logging — quiet, prefixed, stderr.
# ---------------------------------------------------------------------------

def info(msg: str) -> None:
    print(f"\033[36m[ks]\033[0m {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"\033[33m[ks!]\033[0m {msg}", file=sys.stderr)


def err(msg: str) -> None:
    print(f"\033[31m[ks×]\033[0m {msg}", file=sys.stderr)


def die(code: int, msg: str) -> NoReturn:
    err(msg)
    raise SystemExit(code)


# ---------------------------------------------------------------------------
# Vault discovery.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Vault:
    path: Path
    rule: Literal["env", "cwd-walk"]


def _is_vault(path: Path) -> bool:
    return path.is_dir() and (path / VAULT_MARKER).exists()


def find_vault(start: Path | None = None) -> Vault:
    """Resolve the active knowledge-smith vault.

    Order: $KNOWLEDGE_SMITH_VAULT, then walk cwd upward for the marker.
    Hard-fails (SystemExit 10) with an init hint if neither succeeds.
    """
    env_path = os.environ.get(ENV_VAR, "").strip()
    if env_path:
        candidate = Path(env_path).expanduser().resolve()
        if _is_vault(candidate):
            return Vault(path=candidate, rule="env")
        die(
            10,
            f"${ENV_VAR}={env_path!r} does not contain a {VAULT_MARKER} marker",
        )

    cwd = (start or Path.cwd()).resolve()
    for candidate in [cwd, *cwd.parents]:
        if _is_vault(candidate):
            return Vault(path=candidate, rule="cwd-walk")

    die(
        10,
        "no knowledge-smith vault found. Set "
        f"{ENV_VAR}, cd into a vault, or run "
        "`ks_doctor.py --init <path>` to scaffold one.",
    )


# ---------------------------------------------------------------------------
# Strings / identifiers.
# ---------------------------------------------------------------------------

def slugify(text: str, max_len: int = 60) -> str:
    """Kebab-case, ASCII, lowercase. Used by `ks_doctor --migrate` only —
    new ingests receive the slug from the agent."""
    norm = unicodedata.normalize("NFKD", text)
    ascii_only = norm.encode("ascii", "ignore").decode("ascii")
    lower = ascii_only.lower()
    kebab = re.sub(r"[^a-z0-9]+", "-", lower).strip("-")
    if not kebab:
        kebab = "untitled"
    if len(kebab) > max_len:
        cut = kebab[:max_len].rsplit("-", 1)[0] or kebab[:max_len]
        kebab = cut
    return kebab


def sha1_short(data: bytes | str, length: int = 10) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha1(data).hexdigest()[:length]


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Frontmatter I/O.
# ---------------------------------------------------------------------------

def read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Return (metadata dict, body)."""
    post = frontmatter.load(path)
    return dict(post.metadata), post.content


def write_frontmatter(path: Path, meta: dict[str, Any], body: str) -> None:
    """Atomic write: tmp + rename. Parent dir must exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(body or "", **meta)
    serialized = frontmatter.dumps(post)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(serialized, encoding="utf-8")
    if not serialized.endswith("\n"):
        with tmp.open("a", encoding="utf-8") as fh:
            fh.write("\n")
    tmp.replace(path)


def merge_frontmatter(
    path: Path,
    new_meta: dict[str, Any],
    new_body: str | None,
    *,
    preserve_keys: Iterable[str] = ("tags", "read", "owner", "status"),
    force_body: bool = False,
) -> bool:
    """Write `new_meta` + `new_body` to `path`, preserving user edits.

    Returns True if the file is new, False if it was updated in place.

    Behavior on existing file:
      - For keys in `preserve_keys`, the existing value (if non-empty)
        wins over the new value. This protects user-curated tags, read
        state, etc. from being clobbered on re-ingest.
      - For all other keys, the new value wins.
      - The existing body is preserved unless `force_body=True` or the
        existing body is empty.
      - `updated:` is always set to today.
      - `created:` is preserved from the existing file if present.
    """
    is_new = not path.exists()
    if is_new:
        meta = {**new_meta}
        meta["updated"] = today()
        write_frontmatter(path, meta, new_body or "")
        return True

    existing_meta, existing_body = read_frontmatter(path)
    merged = {**new_meta}
    for key in preserve_keys:
        if key in existing_meta and existing_meta[key] not in (None, "", []):
            merged[key] = existing_meta[key]
    if "created" in existing_meta:
        merged["created"] = existing_meta["created"]
    merged["updated"] = today()

    body = existing_body if (existing_body and not force_body) else (new_body or existing_body or "")
    write_frontmatter(path, merged, body)
    return False


# ---------------------------------------------------------------------------
# Path helpers.
# ---------------------------------------------------------------------------

def note_path(vault: Path, kind: str, basename: str) -> Path:
    """Where a note for a given kind lives: <vault>/notes/<kind-plural>/<basename>."""
    folder = KIND_TO_PLURAL.get(kind)
    if folder is None:
        raise ValueError(f"unknown kind={kind!r}")
    return vault / "notes" / folder / basename


def reading_list_path(vault: Path, kind_plural: str) -> Path:
    """Generated reading-list page for a kind: <vault>/reading-list/<plural>.md."""
    return vault / "reading-list" / f"{kind_plural}.md"


def raw_path(vault: Path, kind: str, basename: str) -> Path:
    folder = RAW_DIRS.get(kind)
    if folder is None:
        raise ValueError(f"no raw subdir defined for kind={kind!r}")
    return vault / "raw" / folder / basename


def raw_split_path(vault: Path, kind: str, ext: str, basename: str) -> Path:
    """Path under raw/<kind-plural>/<ext>/.

    Used by kinds whose raw assets are split by extension (paper, model-card).
    `ext` must be one of the entries in RAW_SPLIT[kind]; `basename` already
    includes the extension.
    """
    if kind not in RAW_SPLIT:
        raise ValueError(f"raw_split_path: kind={kind!r} has no split layout")
    if ext not in RAW_SPLIT[kind]:
        raise ValueError(
            f"raw_split_path: ext={ext!r} not in {RAW_SPLIT[kind]} for kind={kind}"
        )
    folder = RAW_DIRS[kind]
    return vault / "raw" / folder / ext / basename


# Back-compat alias for the original paper-only helper.
def raw_paper_path(vault: Path, ext: str, basename: str) -> Path:
    return raw_split_path(vault, "paper", ext, basename)


def stub_filename(year: int | None, slug: str) -> str:
    """Year-prefixed for dated kinds, plain for blog/github (timeless)."""
    if year is None:
        return f"{slug}.md"
    return f"{year}-{slug}.md"


def basename_from(meta: dict[str, Any], kind: str, schema: "Schema") -> str:
    """Compute the note filename from validated metadata + schema.

    Dated kinds get `<year>-<slug>.md`; undated kinds get `<slug>.md`.
    The agent is responsible for supplying the slug — for github
    bookmarks that means `slug = "owner-repo"`.
    """
    spec = schema.kind_spec(kind)
    year = meta.get("year") if spec.get("dated") else None
    return stub_filename(year, meta["slug"])


def load_tag_vocab(vault: Path) -> list[str]:
    """Read <vault>/.ks-tag-vocab if present, else return DEFAULT_TAG_VOCAB."""
    custom = vault / ".ks-tag-vocab"
    if custom.is_file():
        tags = []
        for line in custom.read_text(encoding="utf-8").splitlines():
            t = line.strip()
            if t and not t.startswith("#"):
                tags.append(t)
        if tags:
            return tags
    return list(DEFAULT_TAG_VOCAB)


# ---------------------------------------------------------------------------
# Refusal helpers.
# ---------------------------------------------------------------------------

def refuse_if_exists(path: Path, force: bool) -> None:
    if path.exists() and not force:
        die(4, f"already exists: {path} (use --force to overwrite)")


# ---------------------------------------------------------------------------
# Schema loading and validation.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Schema:
    common_core: dict[str, Any]
    kinds: dict[str, dict[str, Any]]
    sources: tuple[Path, ...] = field(default_factory=tuple)

    def kind_spec(self, kind: str) -> dict[str, Any]:
        spec = self.kinds.get(kind)
        if spec is None:
            die(2, f"unknown kind={kind!r}; schema knows {sorted(self.kinds)}")
        return spec

    def all_kinds(self) -> tuple[str, ...]:
        return tuple(self.kinds)


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Recursive dict merge: `over` wins for scalars, recurses on dicts."""
    out = copy.deepcopy(base)
    for key, val in over.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out


def load_schema(vault: Path | None = None) -> Schema:
    """Load default schema, optionally overlay <vault>/.ks-schema.yaml."""
    sources: list[Path] = []
    with DEFAULT_SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    sources.append(DEFAULT_SCHEMA_PATH)

    if vault is not None:
        override = vault / SCHEMA_OVERRIDE_FILE
        if override.is_file():
            with override.open("r", encoding="utf-8") as fh:
                overlay = yaml.safe_load(fh) or {}
            data = _deep_merge(data, overlay)
            sources.append(override)

    common = data.get("common_core") or {}
    kinds = data.get("kinds") or {}
    if not isinstance(common, dict) or not isinstance(kinds, dict):
        die(2, f"malformed schema in {sources[-1]}: missing common_core/kinds")
    return Schema(common_core=common, kinds=kinds, sources=tuple(sources))


def _coerce_year(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        m = re.search(r"\d{4}", v)
        return int(m.group(0)) if m else None
    return None


def _coerce_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v.strip()] if v.strip() else []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return []


def validate_meta(
    meta: dict[str, Any],
    kind: str,
    schema: Schema,
    *,
    fill_defaults: bool = True,
) -> dict[str, Any]:
    """Validate a metadata dict against the schema and return it normalized.

    Hard-fails with `die(2, ...)` on missing required fields. Fills
    common-core defaults (`type`, `read`, `owner`, `tags`, `links`,
    `created`, `updated`) and per-kind `default_tags` if `fill_defaults`.

    Coerces `year` to int and `authors` to list[str] when those keys are
    present (paper/model-card use both).

    The returned dict is suitable for `write_frontmatter` directly.
    """
    spec = schema.kind_spec(kind)
    out: dict[str, Any] = {**meta}
    out["kind"] = kind

    # Per-kind required fields.
    missing = [k for k in spec.get("required", []) if not out.get(k)]
    if missing:
        die(2, f"metadata missing required fields for kind={kind}: {missing}")

    # Per-kind required link sub-keys.
    links = out.get("links") or {}
    if not isinstance(links, dict):
        die(2, f"`links` must be a dict, got {type(links).__name__}")
    missing_links = [
        k for k in spec.get("required_links", []) if not links.get(k)
    ]
    if missing_links:
        die(
            2,
            f"metadata missing required link keys for kind={kind}: {missing_links}",
        )

    # Light type coercion for fields the schema explicitly mentions.
    if "year" in out:
        out["year"] = _coerce_year(out["year"])
    if "authors" in out:
        out["authors"] = _coerce_str_list(out["authors"])

    # Title / slug must be present (common-core).
    for key in ("title", "slug"):
        if not out.get(key):
            die(2, f"metadata missing required common-core field: {key}")

    if not fill_defaults:
        return out

    # Common-core defaults — fill only if the agent omitted them.
    cc_defaults = schema.common_core.get("defaults", {}) or {}
    for key, default in cc_defaults.items():
        if key not in out or out[key] in (None, "", [], {}):
            out[key] = copy.deepcopy(default)
    out.setdefault("created", today())
    out.setdefault("updated", today())

    # Per-kind default tags merged into existing tags (deduped, order preserved).
    default_tags = spec.get("default_tags") or []
    if default_tags:
        existing = list(out.get("tags") or [])
        for t in default_tags:
            if t not in existing:
                existing.append(t)
        out["tags"] = existing

    # Ensure links dict has all known keys present (None when unset),
    # so frontmatter rendering shows the canonical shape.
    link_keys = spec.get("link_keys") or []
    canonical_links: dict[str, Any] = {}
    for key in link_keys:
        canonical_links[key] = links.get(key)
    out["links"] = canonical_links

    return out


def parse_metadata_json(payload: str) -> dict[str, Any]:
    """Parse a `--metadata-json` payload (or '-' for stdin) to a dict."""
    if payload == "-":
        payload = sys.stdin.read()
    try:
        meta = json.loads(payload)
    except json.JSONDecodeError as exc:
        die(2, f"invalid JSON: {exc}")
    if not isinstance(meta, dict):
        die(2, f"metadata JSON must be an object, got {type(meta).__name__}")
    return meta


def parse_links_json(payload: str | None) -> dict[str, Any]:
    """Parse the optional `--links-json` payload into a links dict."""
    if not payload:
        return {}
    try:
        out = json.loads(payload)
    except json.JSONDecodeError as exc:
        die(2, f"invalid --links-json: {exc}")
    if not isinstance(out, dict):
        die(2, f"--links-json must be an object, got {type(out).__name__}")
    return out


# ---------------------------------------------------------------------------
# Self-test entry point: round-trip every vault-template skeleton.
# ---------------------------------------------------------------------------

def _self_test() -> int:
    """Load default schema; ensure every kind's defaults validate."""
    schema = load_schema(None)
    info(f"schema sources: {[str(s) for s in schema.sources]}")
    info(f"kinds: {schema.all_kinds()}")
    failures = 0
    for kind, spec in schema.kinds.items():
        sample: dict[str, Any] = {
            "title": f"sample {kind}",
            "slug": f"sample-{kind}",
        }
        # Fill required per-kind fields with placeholder values.
        for req in spec.get("required", []):
            if req == "year":
                sample[req] = 2024
            elif req == "authors":
                sample[req] = ["Sample Author"]
            else:
                sample[req] = f"sample-{req}"
        # Fill required link keys with placeholders.
        sample["links"] = {k: f"https://example.com/{k}" for k in spec.get("required_links", [])}
        try:
            out = validate_meta(sample, kind, schema)
        except SystemExit as exc:
            err(f"kind={kind} sample failed: {exc}")
            failures += 1
            continue
        if out.get("kind") != kind:
            err(f"kind={kind} round-trip dropped kind field")
            failures += 1
        else:
            info(f"  ok: {kind} (links={list(out['links'])}, tags={out['tags']})")
    if failures:
        err(f"{failures} self-test failure(s)")
        return 1
    info("self-test: all kinds OK")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    err("_ks_common is a library; pass --self-test to validate the schema")
    raise SystemExit(2)


# ---------------------------------------------------------------------------
# Legacy validate_metadata_json — kept until all ingest scripts migrate to
# `validate_meta`. Mirrors the old behavior with hardcoded REQUIRED_KEYS.
# ---------------------------------------------------------------------------

REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "paper": ("title", "authors", "year"),
    "article": ("title", "url"),
    "youtube": ("youtube_id", "title"),
    "blog": ("url", "title"),
    "post": ("url", "title"),
    "github": ("url",),
    "course": ("url", "title"),
}


def validate_metadata_json(payload: str, kind: str) -> dict[str, Any]:
    """Legacy validator — superseded by `validate_meta(schema)`.

    Retained only so older ingest scripts still parse; new scripts call
    `validate_meta` against a loaded `Schema`.
    """
    meta = parse_metadata_json(payload)
    required = REQUIRED_KEYS.get(kind)
    if required is None:
        die(2, f"unknown kind={kind!r}; must be one of {tuple(REQUIRED_KEYS)}")
    missing = [k for k in required if not meta.get(k)]
    if missing:
        die(2, f"metadata JSON missing required keys for kind={kind}: {missing}")

    if kind == "paper":
        meta["year"] = _coerce_year(meta.get("year"))
        meta["authors"] = _coerce_str_list(meta.get("authors"))
        meta.setdefault("arxiv", None)
        meta.setdefault("doi", None)
        meta.setdefault("venue", None)
        meta.setdefault("abstract", "")
        meta.setdefault("url", None)
    elif kind == "article":
        meta["year"] = _coerce_year(meta.get("year") or meta.get("published"))
        meta.setdefault("author", None)
        meta.setdefault("publication", None)
        meta.setdefault("tldr", "")
    elif kind == "youtube":
        meta["year"] = _coerce_year(meta.get("year") or meta.get("upload_date"))
        meta.setdefault("channel", None)
        meta.setdefault("channel_id", None)
        meta.setdefault("duration_seconds", 0)
        meta.setdefault("upload_date", None)
    elif kind == "blog":
        meta.setdefault("author", None)
        meta.setdefault("description", None)
    elif kind == "post":
        meta["year"] = _coerce_year(meta.get("year"))
        meta.setdefault("author", None)
        meta.setdefault("source", None)
        meta.setdefault("description", None)
    elif kind == "github":
        meta.setdefault("description", None)
    elif kind == "course":
        meta["year"] = _coerce_year(meta.get("year"))
        meta.setdefault("instructor", None)
        meta.setdefault("institution", None)
        meta.setdefault("description", None)

    return meta
