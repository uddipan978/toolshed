# foreman

A plugin that drives a requirement through a full SDLC — grill, plan,
critique, build, test, beta-review, hand off — by spawning and supervising independent
worker sessions with budgets, deadlines, stuck-detection and handover compaction.
Claude and Grok adapters live under `scripts/adapters/`.

```
/foreman add a health-check endpoint
```

## Install

```bash
# Claude Code
claude plugin marketplace add ~/projects/claude-tooling/foreman
claude plugin install foreman@claude-tooling --scope user

# Grok Build
grok plugin install ~/projects/claude-tooling/foreman --trust
```

The first `/foreman` run installs remaining dependencies and reports what it changed.
On Claude it sets `askUserQuestionTimeout: "5m"`; on Grok, `[toolset.ask_user_question] timeout_secs = 300`.
Workers: Claude `claude -p`, Grok `grok --prompt-file`. See [reference/harness.md](reference/harness.md).

## The gates

| | Gate | Runs as |
|---|---|---|
| G0 | Intake — grill until nothing is assumed | main session + `/grilling` |
| G1 | Plan — modules, tasks, dependencies, `[P]` markers | main session |
| G2 | Critique — isolated attack, then manager disposition; `--g2-clear` | forked skill (Claude) or `foreman-critic` worker (Grok) |
| G3 | Develop — one task per session, own worktree | `foreman-developer` |
| G4 | Test — cases written first, then executed | `foreman-tester` |
| G5 | Beta — real-user perspective, no build context | `foreman-beta-tester` |
| G6 | Handoff — to you, with every auto-decision listed | manager |

No gate is skipped to save time. A small change gets a thin version of each.

## How workers run

`scripts/spawn.sh` dispatches to a harness adapter ([reference/harness.md](reference/harness.md)):

- **Claude:** `claude -p` with `stream-json`. `--bg` refuses to combine with `-p`.
- **Grok:** `grok --prompt-file` with `streaming-messages-json`. No `--max-budget-usd`;
  the supervisor emits `BUDGET` from captured spend. Headless Grok does not honour
  `--worktree`, so the adapter creates `.grok/worktrees/` itself.

Each worker gets its own git worktree and runs with permissions bypassed, so it never
stalls on a prompt and cannot damage the main checkout.

`supervise.py` reads the captured `stream-json` — the supported interface — and emits one
event per state change:

| Event | Manager response |
|---|---|
| `POKE` | message the worker for a status line |
| `STUCK` | read `progress.md`, unblock or respawn from handover |
| `OVERDUE` | stop, seed a successor from the handover |
| `COMPACT` | informational — it self-compacted at 55% |
| `TURNS` | 80% of the turn cap used — narrow scope or prepare a successor |
| `BUDGET` | cap reached; successor or descope |
| `DONE` | verify the acceptance boxes and `[t]` (not `[x]`), then G4, then `integrate.sh` |
| `FAILED` | fix the brief, then respawn |

Compaction fires at 55% via `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`. A `PreCompact` hook writes
a handover document; a `SessionStart(compact)` hook injects it into the fresh context.

A `Stop` hook refuses to let a worker finish while its acceptance boxes are unchecked,
its Activity log is empty, the brief has no `**Task file**`, or a developer has marked
`[x]` before G4 — up to three times, then it defers to the manager.

## What it writes

```
<project>/.foreman/               ← TRACKED. Commit this.
├── STATUS.md                     markdown board — a teammate starts here
├── board.html                    visual board — deterministic, no live state
├── board.md                      Obsidian drag-and-drop board
├── REQUIREMENTS.md               grilled requirement, EARS acceptance criteria
├── constitution.md               non-negotiables + run/build/test commands
├── CRITIQUE.md                   G2 findings; gate is `--g2-clear`, not file presence
├── modules/M*/tasks/T-*.md       one file per task — the source of truth
├── decisions/D*.md               HITL ledger, including auto-selected calls
├── adr/NNNN-*.md                 architectural decisions
├── agents/glossary.md            domain vocabulary — use these words exactly
├── agents/code-standards.md      what a review reviews against
├── agents/domain.md              how to read this repo's docs, and which drift
├── log.md                        append-only activity log
└── work/                        ← GITIGNORED. Agent scratchpad.
    ├── memory.md                 read this first — running state, immediate attention
    ├── sessions/<name>/          brief, progress, status, stream, handovers
    ├── research/  screenshots/  errors/
    └── dashboard.html            live ops console — session gauges, spend, alerts
```

Four views of the same data, because no one format reaches everyone:

| View | Tracked | Reaches |
|---|---|---|
| `STATUS.md` | yes | anyone — repo browser, editor, Obsidian |
| `board.html` | yes | a teammate who cloned; visual, no plugin |
| `board.md` | yes | you, in Obsidian — drag-and-drop |
| `work/dashboard.html` | no | the live run: context %, spend, alerts |

A `board.md` wikilink renders as literal text on GitHub, and a repo browser shows HTML
as source — which is why `STATUS.md` is the default. `board.html` is deliberately
deterministic (no timestamp, no session state) so it only diffs when task state changed.

**Why sessions are not tracked:** `status.json` is rewritten every supervisor sweep and
handovers are transient scaffolding. The durable record of how a task got built is the
task file's Activity log, which carries the Verify command and its real output.

`board.md` and `dashboard.html` are generated. Delete them any time; `/foreman:board`
rebuilds both.

## Sizing

3–5 concurrent workers, 5–6 tasks each. Fan out only across `[P]` tasks with genuinely
disjoint file sets. Multi-agent runs cost roughly 15× a single session and coding
parallelises far worse than research does — both are why the ceiling is low.

## Skills

`/foreman` · `/foreman:intake` · `/foreman:plan` · `/foreman:critique` · `/foreman:run` ·
`/foreman:board`

## Reference

- [reference/gates.md](reference/gates.md) — entry and exit criteria per gate, severity
- [reference/critique-format.md](reference/critique-format.md) — CRITIQUE.md schema
- [reference/task-format.md](reference/task-format.md) — task file schema, status legend
- [reference/delegation-brief.md](reference/delegation-brief.md) — the four mandatory fields
- [reference/troubleshooting.md](reference/troubleshooting.md) — known traps and rejected dependencies
- [reference/harness.md](reference/harness.md) — Claude vs Grok worker adapters

## Developing

The plugin cache **copies** files at install time — editing this repo does not change
what is installed. After an edit, either:

```bash
# session-only, no install: fastest loop for testing a change
claude --plugin-dir ~/projects/claude-tooling/foreman

# or reinstall. A version bump alone is not enough, and neither is uninstall alone —
# the old versioned cache directory is reused, so clear it too.
claude plugin uninstall foreman
rm -rf ~/.claude/plugins/cache/claude-tooling
claude plugin marketplace update claude-tooling
claude plugin install foreman@claude-tooling --scope user -y
```

Check what is actually live:

```bash
diff -q "$(find ~/.claude/plugins/cache/claude-tooling -name dashboard.py | tail -1)" \
        scripts/dashboard.py
```
