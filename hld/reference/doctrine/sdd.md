<!-- Distilled from the owner's Subagent-Driven Development model, snapshot 2026-08-30.
     The HLD drive loop is the v1 runtime of this doctrine. -->

# Subagent-driven development — the contracts

SDD executes a written plan through focused workers with isolated context. The
controller owns the goal, plan, architecture, dependencies, integration and the final
completion claim — a worker never declares the overall task complete.

## Task decomposition

A delegated task is a **reviewable unit of working functionality**, never a fragment.
Each task defines: purpose, exact acceptance criteria, files/interfaces in scope,
dependencies, explicit exclusions, required verification, expected evidence, commit
boundary, and escalation behavior. Never split a helper/schema/provider from its first
real consumer.

## Dispatch

A worker gets a **focused brief** (see `reference/formats/delegation-brief.md`), not the
conversation: where the task fits, the authoritative requirements, only the prior
decisions that affect it, the permitted scope, the verification commands, and the
instruction to **ask before implementing** when requirements are ambiguous and to
**escalate rather than guess** when uncertainty exceeds the task.

## Status contract

`DONE` · `DONE_WITH_CONCERNS` · `NEEDS_CONTEXT` · `BLOCKED` — a worker never silently
reports success while uncertain.

## Review

Every task passes a review by someone who is not its implementer before its status
flips: specification compliance (missing requirements, unrequested additions,
misunderstood behavior) and implementation quality (correctness, error handling, edge
cases, simplicity, test quality). Findings: critical / important — fix and re-review;
minor — recorded for the final pass. **The critic runs the verification commands
itself**; reading the diff is not a review.

## Concurrency

Only for genuinely independent tasks: disjoint file scopes, no dependence on each
other's uncommitted results, stable interfaces, unambiguous integration. Otherwise
sequential. HLD's v1 drive is sequential by design.

## In HLD

The drive loop (see the `build` stage) applies this in-session: task → implement →
`commit_check.py` → gate check → fresh-context critic (host subagent where available;
a separate recorded in-session pass where not, with isolation marked `COULD-NOT-RUN`)
→ status token + evidence → next task. Resume after any interruption = re-read
`.hld/BUILD-PLAN.md` and STATUS.md from disk; never redispatch work recorded `[x]`.
