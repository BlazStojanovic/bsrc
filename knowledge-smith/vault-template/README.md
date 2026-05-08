# knowledge-smith vault

A research aggregation and indexing vault. Sources flow through `inbox/` →
`sources/<kind>/` and feed concept-level synthesis in `notes/`.

The contract — directory roles, frontmatter schema, naming, agent
collaboration rules — lives in [`CLAUDE.md`](./CLAUDE.md). Read that first.

## Quick reference

| Folder | Holds |
|---|---|
| `inbox/` | Just-ingested sources awaiting registration |
| `sources/papers/` | Registered paper sources (one file per paper) |
| `sources/articles/` | Registered web articles |
| `sources/youtube/` | Registered YouTube videos |
| `sources/blogs/` | Lightweight blog bookmarks |
| `sources/github/` | Lightweight GitHub repo bookmarks |
| `notes/` | Concept-oriented synthesis, flat, cross-source |
| `topics/` | User-curated reading maps and taxonomy |
| `raw/papers/<id>.md` | Parsed paper text (committed) |
| `raw/papers/<id>.pdf` | Original PDF (gitignored) |
| `raw/articles/<slug>.md` | Web Clipper output |
| `raw/youtube/<id>.transcript.md` | Auto-subs flattened to text |

## Tooling

Scripts live in `bsrc` and are exposed via the knowledge-smith skill:

```
uv run ~/.claude/skills/knowledge-smith/scripts/<name>.py <args>
```

Run `ks_doctor.py` to confirm the active vault and see counts.
