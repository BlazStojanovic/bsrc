---
name: devpod
description: Drive the user's Kubernetes GPU dev pod (infractl dev) with the `devpod` CLI from bsrc. Covers resume and suspend, GPU pinning, shells, the one-time tool bootstrap, and moving files between laptop, pod and S3. Use when the user mentions their dev pod or devpod, infractl dev, copying files to or from the pod, running something on the GPU box, the GPU being unavailable in the pod, or querying data from inside the pod. Triggers: devpod, dev pod, infractl dev, GPU dev box, push to the pod, pull from the pod, /mnt/s3, lake-sql, suspend the pod, resume the pod, CUDA_VISIBLE_DEVICES.
---

# devpod

`devpod` (source `bsrc/devpod/bin/devpod`, linked to `~/.local/bin/devpod`) wraps
`infractl dev` for the pod's lifecycle and `kubectl exec`/`cp` for shells and
files, the same paths `infractl dev connect` and `infractl dev cp` use.

**Read `~/.config/bsrc/devpod.md` first if it exists.** It holds the
cluster-specific facts (clusters, queues, limits, buckets, access rules, data
tools) that stay out of this public repo. Settings live next to it in
`~/.config/bsrc/devpod.env`; `devpod help` lists them.

**Where am I?** `DEVPOD=1` and `HOME=/persistent` mean you are inside the pod:
`devpod` is not installed there, so use the in-pod section below. On the
laptop, use `devpod`.

## Daily use

| Need | Command |
| --- | --- |
| Start working | `devpod up`: resume if suspended, then pin the GPU |
| Stop working (frees the GPU, keeps `/persistent`) | `devpod down` |
| What is going on | `devpod status` |
| Shell (zsh) or one command | `devpod shell`, `devpod shell 'nvidia-smi -L'` |
| Copy in or out | `devpod push <local> [pod-path]`, `devpod pull <pod-path> [local]` |
| Large files through S3 | `devpod stage <local> [key]`, `devpod unstage <key> [local]` |
| Reinstall or refresh pod tools | `devpod bootstrap [--upgrade]` |
| New pod after a delete | `devpod create`, then `devpod bootstrap` |

To work from any terminal tab (Rex, Ghostty, tmux), run `devpod shell` in it.

## The GPU pin

The dev container runs privileged, so `nvidia-smi` lists every GPU on its node,
including GPUs that belong to other pods. `devpod up` (via `pin-gpu`) reads the
pod's DRA allocation with the laptop's kubectl access and writes
`~/.devpod/gpu.sh`, which every shell sources.

- The pin holds only for the pod start it was written for (host boot id plus
  PID 1's start time). After any restart, including a resume through
  `infractl dev connect`, it sets `CUDA_VISIBLE_DEVICES=-1` until `devpod up`
  runs again.
- Sandboxed agent commands may see `-1` or no GPU devices; GPU work needs an
  unsandboxed (escalated) command.
- Agents: never unset `CUDA_VISIBLE_DEVICES` or pick GPUs by `nvidia-smi` index.
  If it is `-1`, stop and ask the user to run `devpod up` on the laptop.

## Facts that bite

1. **Only `/persistent` survives restarts.** Install tools with
   `pixi global install <pkg>` or into `~/.local`; apt installs vanish on the
   next resume.
2. **The pod's own cloud role is narrow** (typically just its S3 prefix,
   mounted at `/mnt/s3`). Anything more needs the user's own SSO session inside
   the pod (`aws sso login`).
3. **Logins in the pod are shared risk:** anyone allowed to exec into the pod
   can read SSO caches, agent logins and `.netrc` in `/persistent`. Keep
   long-lived secrets out of it.

## Moving data

| From → to | How |
| --- | --- |
| laptop → pod | `devpod push ./notes.md /persistent/data/notes.md` |
| pod → laptop | `devpod pull /persistent/runs/out.json ./out.json` |
| laptop → pod, large | `devpod stage ./big.parquet` → `/mnt/s3/big.parquet` in the pod |
| pod → laptop, large | write to `/mnt/s3/<key>` in the pod, then `devpod unstage <key>` |
| SQL → pod | in the pod: `lake-sql "SELECT ... LIMIT 1000" > /persistent/data/x.jsonl` |

`/mnt/s3` is Mountpoint for S3: whole-file sequential writes only, no appends,
renames or random writes. Write to `/persistent` first and copy finished files.
`push`/`pull` go through the Kubernetes API server; prefer `stage` above a few
hundred MB.

## Inside the pod

- Tools that persist: zsh, tmux, rg, fd, jq, btop, yazi, lazygit, node (pixi,
  `~/.pixi/bin`); nvim, claude, aws, lake-sql (`~/.local/bin`); codex (Codex's
  standalone package under `~/.codex/packages`, linked from `~/.local/bin`).
- Config comes from `~/bsrc` (its zsh, git, tmux, nvim, codex and claude
  components), except `~/.claude/settings.json` (bsrc's minus macOS hooks) and
  `~/.codex/config.toml` (bsrc's minus macOS notify and paths, plus trust for
  `/persistent` and the repos in it).
- One-time sign-ins: `claude` then `/login`; `codex login --device-auth`;
  `aws sso login --profile <profile> --use-device-code --no-browser`.

## Troubleshooting

- `kubectl auth failed`: refresh the SSO session (`DEVPOD_LOGIN_HINT`).
- `CUDA_VISIBLE_DEVICES=-1`: the pod restarted since its last pin; run
  `devpod up` on the laptop.
- Pod stays Pending after `devpod up`: its queue has no room.
- A tool is missing after a restart: it was apt-installed; use pixi, or rerun
  `devpod bootstrap`.
- `codex` says "this CLI has no complete local package": it is a bare binary,
  not the standalone package. Rerun `devpod bootstrap --upgrade`, or in the pod
  run Codex's `install.sh` from its latest GitHub release.

## Rules for agents

- Ask before `devpod create`, deleting a pod, or changing its queue; each
  takes or gives up a GPU in a shared queue. `up`, `down` and `status` on the
  user's own pod are fine when the work calls for them.
- `devpod bootstrap` downloads and runs installers from GitHub, claude.ai and
  AWS. Run it only when the user asks.
- Never print tokens or copy auth files between machines; the user signs in
  inside the pod.
