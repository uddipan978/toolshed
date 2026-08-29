<!-- Absorbed from foreman/reference/delegation-brief.md @ 31b38123fb47ca1fe8aa73a4108d4b9e03ce4194 (MIT, (c) 2026 Uddipan Dey). See CREDITS.md. -->
# The delegation brief

## Contents
- Why four fields
- The template
- A worked example
- Common failures

## Why four fields

Anthropic's published post-mortem on multi-agent systems names the cause of duplicated
work and silent gaps directly: *"Without detailed specifications, agents duplicate work,
leave gaps, or fail to find necessary information."*

Four fields fix it. A brief missing any one of them reliably produces one of those three
failures, so treat them as mandatory rather than a checklist to trim under time pressure.

## The template

```markdown
**Task file** .foreman/modules/M01-auth/tasks/T-01-02-session-cookie.md

## Objective
What done looks like, in one paragraph. Not the steps — the end state.

## Output format
Which files to write, and where. Which files to modify. What to report back.

## Tools and sources
What to use. What is already established so it is not re-derived. Which commands
come from constitution.md. Which skills to reach for.

## Boundaries
Explicitly out of scope. Files not to touch. Decisions already made that are not
open for relitigation.
```

`**Task file**` is read by the `Stop` gate hook to find the acceptance criteria. A missing
line, a path that does not exist, or a missing `## Acceptance` section **blocks** the
stop — those used to fail open, which is the early-victory case.

## A worked example

```markdown
**Task file** .foreman/modules/M01-auth/tasks/T-01-02-session-cookie.md

## Objective
A signed-in user's session survives a page reload and expires cleanly after 24 hours.
Done means both acceptance criteria in the task file pass and `npm run test -- session`
is green.

## Output format
Implement in `src/lib/session.ts` and `src/app/api/auth/route.ts`. Update the task
file's acceptance boxes and Activity log with the real Verify output. Keep
`progress.md` in your session directory current as you go.

## Tools and sources
Commands are in `.foreman/constitution.md` — use those, do not invent your own.
The cookie helper already exists at `src/lib/cookies.ts`; use it rather than writing
another. Reach for `mattpocock-skills:tdd` for the red/green loop.

## Boundaries
Do not touch `src/lib/auth.ts` — T-01-01 owns it and is running concurrently.
Do not add a session store; the decision to keep sessions stateless is settled and
recorded in `.foreman/decisions/D03-stateless-sessions.md`.
Password reset is out of scope entirely — that is T-01-04.
```

## Common failures

**Objective written as steps.** "First add the cookie, then wire the route" tells the
worker what to type, not what success is — so it stops when it runs out of steps rather
than when the thing works. State the end condition.

**Boundaries left empty.** This is the one people skip, and it is the one that causes
concurrent workers to collide. If two tasks are running in parallel, each brief must name
the other's files as untouchable.

**Re-deriving settled context.** If a decision is recorded in `.foreman/decisions/`, cite
the path. A worker that cannot see the conversation will otherwise re-open a closed
question, at full cost.

**Referencing conversation the worker cannot see.** Workers are separate sessions with no
access to your history. "As we discussed" is invisible to them. Reference paths, never
conversation.
