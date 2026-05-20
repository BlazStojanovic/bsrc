# Claude Setup

This file is managed by `bsrc` and is symlinked to `~/.claude/CLAUDE.md`.

## Grafana via `gcx`

For anything Grafana-related (datasource exploration, dashboard inspection,
log queries, alert rules, etc.) use the [`gcx`](https://grafana.com/docs/grafana/latest/cli/gcx/)
CLI directly from Bash. Do **not** attempt to use the old `mcp-grafana` MCP
server — it has been removed from this setup.

Assumptions you can make every time:

- `gcx` is installed (via `brew install grafana/grafana/gcx`).
- The active context is `poolside`, pointing at `https://poolside.grafana.net`
  with `contexts.poolside.grafana.org-id = 1`.
- A service account token has already been set up by the user (`gcx login ... --token '<token>'`).
  You should never run `gcx login` or `gcx config set` yourself — those are
  manual steps the user owns.

Usage pattern:

- Start by reading `gcx --help` (or a specific subcommand's `--help`) if you
  are unsure which command you need; the CLI is the source of truth.
- For read-only triage, prefer commands like `gcx datasources list`,
  `gcx query`, `gcx logs query`, etc.
- Never mutate Grafana state (creating/deleting dashboards, alerts, service
  accounts, etc.) without explicit user confirmation.

If a query fails with an authentication, token, or `gcx config check` error,
**stop and remind the user to refresh the service account token**:

> The Grafana service account token looks missing or expired. Generate a new
> one at https://poolside.grafana.net → Administration → Users and access →
> Service accounts, then run `gcx login poolside --server https://poolside.grafana.net --token '<token>' --yes`.

Do not try to work around auth failures by inventing endpoints, calling the
Grafana HTTP API directly, or hard-coding tokens — surface the issue and wait
for the user to refresh credentials.

## Pending migrations to watch

### Dagster: `dagster-cloud` → `dg`

The user wants to migrate off the `dagster-cloud` CLI in favor of `dg` / `dg plus` / `dg api`.
Most of the surface is already covered (CI/CD via `dg plus deploy start`, inspection via
`dg api`, local materialization via `dg launch`), **but production asset materialization
from the CLI is still blocked**: `dg launch` currently runs in-process and does not route
through the instance's configured run launcher, and `dg api` has no `run launch` /
`asset materialize` mutator.

The unblock is tracked in [dagster-io/dagster#30201](https://github.com/dagster-io/dagster/pull/30201)
("[dg launch] Use instance run launcher for `dg launch`"). As of the last check it was OPEN
with `CHANGES_REQUESTED` and last updated 2025-11-09.

**Trigger condition:** when #30201 merges (or a `dg api run launch` mutator lands in
[the `dg api` reference](https://docs.dagster.io/api/clis/dg-cli/dg-api)), remind the user
and offer to do the migration — they have explicitly said they want to update their setup
at that point. Until then, leave `dagster-cloud` in place for the ad-hoc "kick off this
asset in prod" workflow.
