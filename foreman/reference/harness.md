# Harness adapters

Foreman skills describe one procedure. Worker launch is an adapter.

| Harness | How workers run | Worktrees | Stream |
|---|---|---|---|
| **claude** (default) | `claude -p` via `scripts/adapters/claude/spawn.sh` | `<project>/.claude/worktrees/` | `--output-format stream-json` |
| **grok** | `grok --prompt-file` via `scripts/adapters/grok/spawn.sh` | `<project>/.grok/worktrees/` | `--output-format streaming-messages-json` |

`scripts/spawn.sh` dispatches. `supervise.py` and `integrate.sh` are shared: they read `status.json` and `stream.jsonl`.

## Which harness

Override: `FOREMAN_HARNESS=claude|grok` or `python3 scripts/preflight.py --harness grok`.

Otherwise, in order: `.foreman/work/harness` (written by preflight/scaffold), `GROK_SESSION_ID` / `GROK_AGENT`, `CLAUDECODE`, `GROK_PLUGIN_ROOT`, `CLAUDE_PLUGIN_ROOT`, then **claude**.

## Plugin root

```bash
PLUGIN_ROOT="${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"
python3 "$PLUGIN_ROOT/scripts/preflight.py"
"$PLUGIN_ROOT/scripts/spawn.sh" --name dev-m01-02 --agent foreman-developer \
  --brief .foreman/work/sessions/dev-m01-02/brief.md --root .foreman
```

## Branch ancestry

`spawn.sh` accepts `--base <branch-or-commit>`. A tester named `test-X` defaults to
`foreman/dev-X`; it never falls back to HEAD if that branch is missing. Both adapters use
`scripts/worktree.py`, which records `base_commit`, `start_commit`, and
`lineage_start_commit` in `status.json` and verifies the new branch contains its base.

A session-backed base must be stopped and clean. A developer base must contain at least
one commit after that developer session's own `start_commit`; inherited commits do not
count. This catches killed workers whose worktree is dirty while their branch still points
at an ancestor. A tester may add no branch commit because its evidence is in the session
directory. A `foreman/*` base without matching session metadata is rejected because its
live/dirty state cannot be verified. Git-backed developers and testers cannot use
`--worktree no`, because that would run against the manager checkout instead of the
recorded base. Fix-round successors name the predecessor explicitly:

```bash
"$PLUGIN_ROOT/scripts/spawn.sh" --name dev-m01-02-fix-1 --agent foreman-developer \
  --brief .foreman/work/sessions/dev-m01-02-fix-1/brief.md --root .foreman \
  --base foreman/test-m01-02
```

Grok sets `GROK_PLUGIN_ROOT` (and a `CLAUDE_PLUGIN_ROOT` alias on hooks). Claude sets `CLAUDE_PLUGIN_ROOT`. Scripts also self-locate via `plugin_root()` when invoked by path.

## G2 on Grok

Claude's critique skill uses `context: fork`. Grok skills do not. On Grok, spawn the critic as a worker in the same tree:

```bash
"$PLUGIN_ROOT/scripts/spawn.sh" --name g2-critic-1 --agent foreman-critic \
  --brief .foreman/work/sessions/g2-critic-1/brief.md --root .foreman \
  --worktree no --deadline 45 --turns 80
```

Name later rounds `g2-critic-2` … `g2-critic-4`. Never a fifth. `--g2-spawn` is
what decides whether to launch; do not spawn on a prompt `if`.

Brief: write `.foreman/CRITIQUE.md` only; do not edit the plan; do not close findings. Then `--check-critique` as in [gates.md](gates.md).

On Claude, invoke `/foreman:critique` only after `--g2-spawn` exits 0.

## POKE

Claude `-p` workers accept `SendMessage` when `crossSessionInbound` is `accept`. Grok `-p` workers have no inbound channel. A `POKE` event on Grok is log-only; `STUCK` is the action (stop and respawn from handover).

## Grok-only limits

- No `--max-budget-usd`. `--budget` is stored on `status.json`; the supervisor emits `BUDGET` when captured spend crosses it. The manager stops the pid, then routes from `READY` or `REVIEW` after artefact validation—not from the budget subtype alone.
- Headless `grok -p` does not create a worktree from `--worktree`. The adapter creates `.grok/worktrees/` itself.
- Ask-question auto-select: `[toolset.ask_user_question] timeout_secs = 300` in `~/.grok/config.toml` (preflight) and `GROK_ASK_USER_QUESTION_TIMEOUT_SECS=300` on the worker.

## What is not adapted

Procedure, `.foreman/` schema, gates, task format, board, critic/planner/tester *text* — one copy. Do not fork those per harness.
