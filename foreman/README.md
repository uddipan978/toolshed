# foreman

A Claude Code plugin that drives a requirement through a full SDLC — grill, plan,
critique, build, test, beta-review, hand off — by spawning and supervising independent
Claude sessions with budgets, deadlines, stuck-detection and handover compaction.

```
/foreman add a health-check endpoint
```

## Install

```bash
claude plugin marketplace add ~/projects/claude-tooling/foreman
claude plugin install foreman@claude-tooling --scope user
```

The first `/foreman` run installs its own dependencies (`impeccable`, `ui-ux-pro-max`,
`mattpocock-skills`, `skill-creator`, `pr-review-toolkit`, `session-report`,
`frontend-design`), adds the marketplaces they live in, and sets
`askUserQuestionTimeout: "5m"` — then reports exactly what it changed.

## The gates

| | Gate | Runs as |
|---|---|---|
| G0 | Intake — grill until nothing is assumed | main session + `/grilling` |
| G1 | Plan — modules, tasks, dependencies, `[P]` markers | main session |
| G2 | Critique — adversarial review in isolation | forked `foreman-critic` |
| G3 | Develop — one task per session, own worktree | `foreman-developer` |
| G4 | Test — cases written first, then executed | `foreman-tester` |
| G5 | Beta — real-user perspective, no build context | `foreman-beta-tester` |
| G6 | Handoff — to you, with every auto-decision listed | manager |

No gate is skipped to save time. A small change gets a thin version of each.

## How workers run

Workers are `claude -p` processes, not `--bg` sessions — `--max-budget-usd`,
`--max-turns` and `--output-format` are print-mode only, and `--bg` refuses to combine
with `-p`. Each gets its own git worktree and runs `bypassPermissions` inside it, so it
never stalls on a prompt and cannot damage the main checkout.

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
| `DONE` | verify the acceptance boxes before advancing |
| `FAILED` | fix the brief, then respawn |

Compaction fires at 55% via `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`. A `PreCompact` hook writes
a handover document; a `SessionStart(compact)` hook injects it into the fresh context.

A `Stop` hook refuses to let a worker finish while its acceptance boxes are unchecked or
its Activity log carries no real verify output — up to three times, then it defers to the
manager.

## What it writes

```
<project>/.foreman/
├── constitution.md          non-negotiables + run/build/test commands
├── REQUIREMENTS.md          grilled requirement, EARS acceptance criteria
├── modules/M*/tasks/T-*.md  one file per task — the source of truth
├── sessions/<name>/         brief, status, captured stream, handovers
├── decisions/D*.md          decision ledger, including auto-selected ones
├── board.md                 Obsidian Kanban view — derived
└── dashboard.html           browser view — derived
```

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

- [reference/gates.md](reference/gates.md) — entry and exit criteria per gate
- [reference/task-format.md](reference/task-format.md) — task file schema, status legend
- [reference/delegation-brief.md](reference/delegation-brief.md) — the four mandatory fields
- [reference/troubleshooting.md](reference/troubleshooting.md) — known traps and rejected dependencies

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
