# foreman

A plugin that drives a requirement through a full SDLC — grill, plan,
critique, build, test, beta-review, hand off — by spawning and supervising independent
worker sessions with budgets, deadlines, stuck-detection and handover compaction.
Claude and Grok adapters live under `scripts/adapters/`.

Version 0.5 adds MVP/production milestones, committed sprints and a managed runtime.
For UI products, the first sprint delivers a static frontend preview **alongside**
backend development using shared contracts; wiring follows when both are ready.
Targeted changes use a thin sprint. See [delivery.md](reference/delivery.md) for the
schema, commands, resource limits and migration of existing runs.

The managed loop owns RAM/CPU admission, worker capacity, queue recovery, task-state
reconciliation, durable completion events and all four progress views. It reserves
test capacity, bounds fix rounds and tracks optional findings without continually
refilling the sprint backlog. G3 records real Verify output against the product
files; G4/G5 cannot pass with contradictory evidence.

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
| G1 | Plan — MVP, sprints, frontend/backend contracts, tasks and dependencies | main session |
| G2 | Critique — isolated attack, then manager disposition; `--g2-clear`; max 4 G2a rounds (`--g2-spawn`) | forked skill (Claude) or `foreman-critic` worker (Grok) |
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

Each worker gets its own git worktree and runs with permissions bypassed. Git worktrees
isolate repository changes, not databases, processes or external services; briefs must
name the authorized environment and boundaries.

For managed work, `spawn.sh` validates the sprint, gate, brief, file scope and resources,
then records in-progress status and Session. `scheduler.py run` performs the recurring
lifecycle checks and refreshes `STATUS.md`, `board.md`, `board.html` and
`work/dashboard.html`. `refresh.py` regenerates all four on demand. Existing pre-sprint
runs retain a labelled compatibility launch path until their remaining work is migrated.

`spawn.sh --base <branch>` carries predecessor ancestry into a successor. A normal
`test-X` worker defaults to `foreman/dev-X`; launch fails rather than falling back to
HEAD when that predecessor is live, dirty, missing, or contains no worker commit. After
G4, Foreman integrates the tester lineage—the exact worker commits tested—not the
developer branch or its synthetic launch snapshot.

`supervise.py` reads the captured `stream-json` — the supported interface — and emits one
event per state change. Events are durable until manager acknowledgement; supervisor
restarts do not replay historical thresholds. Managed workers also record process exits
independently of notifications. The manager checks the outbox at least every five minutes.

| Event | Manager response |
|---|---|
| `POKE` | message the worker for a status line |
| `STUCK` | read `progress.md`, unblock or respawn from handover |
| `OVERDUE` | stop, seed a successor from the handover |
| `COMPACT` | informational — it self-compacted at 55% |
| `CHECKPOINT` | 40% of turns used while dirty — commit explicit task-scoped paths now |
| `SALVAGE` | worker stopped dirty — preserve the worktree; the branch does not contain that work |
| `TURNS` | 80% of the turn cap used — narrow scope or prepare a successor |
| `BUDGET` | cap reached — wait for `READY`/`REVIEW`; choose successor only from missing artefacts |
| `DONE` | verify evidence, clean git state and ancestry, then G4, then integrate the tested branch |
| `READY` | process ended abnormally, but completion evidence is valid — review its verdict, then advance or route |
| `REVIEW` | process ended with unresolved gate evidence — inspect `completion_problems`; do not restart blindly |
| `FAILED` | an ungated process failed; inspect its result subtype |
| `RESOURCE` | new launches paused/recovered based on laptop RAM and CPU pressure |
| `SPRINT_BUDGET` | review remaining scope and gates; do not turn incomplete work into a pass |

Compaction fires at 55% via `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`. A `PreCompact` hook writes
a handover document; a `SessionStart(compact)` hook injects it into the fresh context.

A `Stop` hook resolves tasks against the worker worktree. Developers need checked
acceptance, Verify output, `[t]`, a clean worktree and a worker commit. Testers need a
result for every declared `TC-NN`; beta testers need a structured review. A documented
failure may stop—the manager routes it—while missing evidence may not. After three
blocks, the process may exit to avoid a trap. The supervisor then rechecks current
artefacts and emits `READY:gate_deferred` when they pass or `REVIEW:gate_deferred`
with concrete problems when they do not—never a generic failure.

## What it writes

```
<project>/.foreman/               ← TRACKED. Commit this.
├── STATUS.md                     markdown board — a teammate starts here
├── board.html                    visual board — deterministic, no live state
├── board.md                      Obsidian drag-and-drop board
├── REQUIREMENTS.md               grilled requirement, EARS acceptance criteria
├── constitution.md               non-negotiables + run/build/test commands
├── CRITIQUE.md                   G2 findings; gate is `--g2-clear`, not file presence
├── delivery.json                 product/targeted mode, milestones, sprint scope and limits
├── design.md / contracts.md      early frontend direction and frontend/backend contract
├── sprints/S*.json               frozen commitments and explicit scope changes
├── evidence/<session>/           durable gate reports and receipts
├── KNOWN-ISSUES.md               deferred observations; not automatically user-accepted
├── modules/M*/tasks/T-*.md       one file per task — the source of truth
├── decisions/D*.md               HITL ledger, including auto-selected calls
├── adr/NNNN-*.md                 architectural decisions
├── agents/glossary.md            domain vocabulary — use these words exactly
├── agents/code-standards.md      what a review reviews against
├── agents/domain.md              how to read this repo's docs, and which drift
├── log.md                        append-only activity log
└── work/                        ← GITIGNORED. Agent scratchpad.
    ├── memory.md                 read this first; **Gate** must match `--check-memory`
    ├── sessions/<name>/          brief, progress, status, stream, handovers
    ├── queue.json / events/      recoverable dispatch and acknowledged event outbox
    ├── resources.json            RAM/CPU pressure and worker admission reason
    ├── research/  screenshots/  errors/
    └── dashboard.html            live ops console — gauges, alerts, agent transcripts
```

Four views of the same data, because no one format reaches everyone:

| View | Tracked | Reaches |
|---|---|---|
| `STATUS.md` | yes | anyone — repo browser, editor, Obsidian |
| `board.html` | yes | a teammate who cloned; visual, no plugin |
| `board.md` | yes | you, in Obsidian — drag-and-drop |
| `work/dashboard.html` | no | the live run: gauges, spend, alerts; click a card for a rendered chat transcript with expandable tool input/output |

A `board.md` wikilink renders as literal text on GitHub, and a repo browser shows HTML
as source — which is why `STATUS.md` is the default. `board.html` is deliberately
deterministic (no timestamp, no session state) so it only diffs when task state changed.

**Why sessions are not tracked:** `status.json` is rewritten every supervisor sweep and
handovers are transient scaffolding. The durable record of how a task got built is the
task file's Activity log, which carries the Verify command and its real output.

`board.md` and `dashboard.html` are generated. Delete them any time; `/foreman:board`
rebuilds both.

## Sizing

Default to 3 concurrent workers, configurable from 1 to 5. RAM/CPU pressure can
pause new launches below that ceiling, and pending G4 work reserves testing capacity.
Fan out across `[P]` tasks with declared disjoint file sets. A static frontend and
backend may proceed together; the contract and wiring dependencies keep them aligned.

## Skills

`/foreman` · `/foreman:intake` · `/foreman:plan` · `/foreman:critique` · `/foreman:run` ·
`/foreman:board`

## Reference

- [reference/gates.md](reference/gates.md) — entry and exit criteria per gate, severity
- [reference/critique-format.md](reference/critique-format.md) — CRITIQUE.md schema
- [reference/task-format.md](reference/task-format.md) — task file schema, status legend
- [reference/delegation-brief.md](reference/delegation-brief.md) — the four mandatory fields
- [reference/evidence-format.md](reference/evidence-format.md) — enforced G4/G5 evidence schemas
- [reference/troubleshooting.md](reference/troubleshooting.md) — known traps and rejected dependencies
- [reference/harness.md](reference/harness.md) — Claude vs Grok worker adapters
- [reference/delivery.md](reference/delivery.md) — MVP/sprints, managed loop, recovery and migration
- [reference/reliability-review.md](reference/reliability-review.md) — observed gaps and implemented corrections

## Developing

```bash
python3 -m unittest discover -s tests -v
```

The suite creates temporary git repositories for the developer → tester → integration
handoff, including dirty/live predecessor refusal and parallel manager bookkeeping edits.

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
