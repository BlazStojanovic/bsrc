# obsidian-skills

A bsrc component that installs [kepano/obsidian-skills][upstream] into
Claude Code and Codex.

The bundle ships five agent skills for working with Obsidian vaults:

| Skill | What it does |
|---|---|
| `obsidian-markdown` | Author Obsidian Flavored Markdown — wikilinks, embeds, callouts, properties, tags |
| `obsidian-bases` | Author Obsidian Bases (`.base`) with views, filters, formulas |
| `json-canvas` | Author JSON Canvas (`.canvas`) files |
| `obsidian-cli` | Drive Obsidian via the official CLI (plugin/theme dev) |
| `defuddle` | Extract clean markdown from web pages via [defuddle-cli][defuddle] |

The skills follow the [Agent Skills specification][spec]; the agent
auto-discovers them by their `SKILL.md` headers when activated.

## How it installs

```
bsrc/obsidian-skills/install.sh
   │
   ├─ clones kepano/obsidian-skills into ~/.cache/bsrc/skills/obsidian-skills
   │  (or fast-forwards if already present)
   │
   └─ for each subdir of skills/:
        symlink → ~/.claude/skills/<name>
        symlink → ~/.codex/skills/<name>
```

The cache dir is regenerable; if you want to start fresh, `rm -rf
~/.cache/bsrc/skills/obsidian-skills` and re-run install.

## Requirements

- `git` (everything else is stdlib + symlinks)

There is no npm dependency, no bundled binary. The upstream repo's
official install paths (`/plugin marketplace add kepano/obsidian-skills`
or `npx skills add ...`) work too — but bsrc prefers the direct
clone+symlink path so the same flow works for Claude and Codex without
extra tooling.

## Tunables (env vars)

- `OBSIDIAN_SKILLS_REPO` — override the upstream URL (default:
  `https://github.com/kepano/obsidian-skills.git`)
- `OBSIDIAN_SKILLS_REF`  — pin to a specific commit/tag/branch
  (default: `main`)
- `OBSIDIAN_SKILLS_CACHE` — relocate the cache (default:
  `~/.cache/bsrc/skills/obsidian-skills`)

## Updating

The component is idempotent — re-running `setup.sh` (or just
`obsidian-skills/install.sh`) fast-forwards the cache and refreshes
the symlinks. To pull a fresh upstream change:

```bash
./obsidian-skills/install.sh
```

To pin to a specific commit (e.g. before a known-good release):

```bash
OBSIDIAN_SKILLS_REF=<sha> ./obsidian-skills/install.sh
```

[upstream]: https://github.com/kepano/obsidian-skills
[defuddle]: https://github.com/kepano/defuddle-cli
[spec]: https://agentskills.io/specification
