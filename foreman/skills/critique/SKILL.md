---
name: critique
description: G2 of the Foreman lifecycle — runs an adversarial review of the plan in an isolated session that tries to refute it, then requires every finding to be fixed or refuted before building starts. Use after planning produces module and task files and before any development session is spawned.
context: fork
agent: foreman-critic
background: false
---

# G2 — Critique the plan

You are reviewing a Foreman plan in isolation. You cannot see the conversation that
produced it, which is the point: you are reading it the way the worker who has to execute
it will read it.

## Read

- `.foreman/REQUIREMENTS.md`
- `.foreman/constitution.md`
- every `.foreman/modules/*/MODULE.md`
- every `.foreman/modules/*/tasks/*.md`

## Try to break it

Default to refuted. A critique concluding "looks reasonable" bought nothing.

**Traceability.** Does every requirement reach a task, and every task reach a requirement?
Orphans in either direction are the plan's biggest holes — one is unbuilt scope, the other
is invented scope.

**Decomposition.** Are `[P]`-marked tasks genuinely disjoint? Open the files they name and
check for overlap rather than trusting the marker. Does any task exceed one context
window? Does the dependency order actually hold?

**Acceptance criteria.** For each one: could this pass while the feature is still broken?
Is the Verify command real and runnable? Criteria that cannot fail are decoration.

**Missing work.** Migrations, auth, error paths, empty states, rollback, concurrency, the
second user, the malformed input. Plans written from the happy path omit the same things
every time.

**Over-engineering.** Speculative abstraction for a requirement nobody stated? Something
the codebase already does? Grep before asserting — a confident wrong finding is worse than
no finding, because someone will act on it.

## Verify before asserting

Read the actual file. Run the actual command. Anything you cannot verify goes in marked
**unverified**, with what would settle it.

## Write it

`.foreman/CRITIQUE.md`. Per finding: what is wrong, the concrete failure it causes,
severity 0–4, and the specific change. Sorted by severity.

End with a plain verdict on whether the plan is fit to build — and if it is, name the
attacks you tried hardest and could not land. That is what makes the verdict worth
anything.

**Every finding must end up refuted or fixed. None may be merely noted.** A critique filed
and ignored is the most expensive work in the whole lifecycle.
