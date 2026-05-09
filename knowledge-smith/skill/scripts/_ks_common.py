"""Shared helpers for knowledge-smith ingest/recover/doctor scripts.

This module is imported by every runner script via:

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _ks_common import find_vault, ...

It is not invoked directly. The importing runner declares its own PEP 723
deps (always including python-frontmatter, since this module uses it).
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, NoReturn

import frontmatter  # type: ignore[import-not-found]


VAULT_MARKER = ".knowledge-smith"
ENV_VAR = "KNOWLEDGE_SMITH_VAULT"

Kind = Literal["paper", "article", "youtube", "blog", "github"]
KIND_TO_PLURAL: dict[str, str] = {
    "paper": "papers",
    "article": "articles",
    "youtube": "youtube",
    "blog": "blogs",
    "github": "github",
}
# Subset of kinds that have associated raw assets on disk.
RAW_DIRS: dict[str, str] = {
    "paper": "papers",
    "article": "articles",
    "youtube": "youtube",
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
    """Kebab-case, ASCII, lowercase. Strip everything but [a-z0-9-]."""
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


def stub_filename(year: int | None, slug: str) -> str:
    """Year-prefixed for dated kinds, plain for blog/github (timeless)."""
    if year is None:
        return f"{slug}.md"
    return f"{year}-{slug}.md"


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
