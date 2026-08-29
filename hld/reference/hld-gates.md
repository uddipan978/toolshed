# The HLD run — artifacts, grammar, gates

One run designs (and optionally builds) **one surface**. Everything lives under `.hld/`
at the root the client chose during the grill. Tracked; `.hld/work/` is gitignored.

```
.hld/
├── STATUS.md          state + current gate (the resume point)
├── BRIEF.md           H0 output — the grill's record
├── contract.json      the repo's design contract, parsed (or authored at H2 if greenfield)
├── UX-REPORT.md       H1 output — research, principles with grades, kill-door verdict
├── IA.md              the IA beat — object model + copy inventory
├── WIREFRAMES/index.html   the walkable wireframe — THE human deliverable
├── UI-SPEC.md         H2 output — locked direction, region→IA trace, rejected alternatives
├── BUILD-PLAN.md      H3 output — tasks with workers, scopes, status tokens
├── TEST-PLAN.md       required shots, bands, test kinds
├── TEST-REPORT.md     what ran, what COULD-NOT-RUN and why (script-captured)
├── HANDOFF.md         H5 output — includes the auto-decisions block
├── findings.csv       every finding, severity-ranked, dispositions
├── ledger.json        path-pinned effort ledger (tracked — H4 replays it)
├── decisions/D*.md    one file per decision that changed course
└── work/              GITIGNORED: host.json, screenshots/, a11y/, scratch
```

## STATUS.md

```
state: running | done | killed
gate: H0 | H1 | H2 | H3 | H4 | H5
root: <this directory>
```

## Gate blockers — checked by `scripts/gate.py check gN`, never by prose

| Gate | One structural blocker |
|---|---|
| g0 | BRIEF.md exists with **zero** `[NEEDS CLARIFICATION]`, and names the contract (`Contract:` line — paths or `NONE-EXISTS`) |
| g1 | UX-REPORT.md records the kill-door verdict: a line `Kill-door verdict: PROCEED` or `Kill-door verdict: KILL — <reason>` |
| g2 | IA beat done (IA.md has non-empty `## Object model` and `## Copy inventory`); UI-SPEC.md has `## Rejected alternatives` with content; every findings.csv row at severity ≥ 3 has a non-empty disposition |
| g3 | Every BUILD-PLAN task line carries `worker=` and `scope=`; scopes are pairwise disjoint; if the run is agentic (see below), the `## Workflow architecture` verdict block is present |
| g4 | Every required shot in TEST-PLAN.md exists in `work/screenshots/` **with** a sidecar `.json`, or TEST-REPORT.md carries `COULD-NOT-RUN: <shot> — <reason>` |
| g5 | HANDOFF.md has `## Auto-decisions`; no BUILD-PLAN task still `[ ]` or `[>]` |

`KILL` at g1 is a valid verdict, not a failure: H2–H4 are skipped, STATUS becomes
`killed`, and H5 still runs — the handoff packages the no with its evidence.

**Agentic trigger (g3):** the verdict block (`Agent-as-graph:`, `SDD:`,
`Workflow-conversion:` lines under `## Workflow architecture`) is required **iff**
BRIEF.md or BUILD-PLAN.md matches the checklist — mentions of agents, LLM loops,
multi-stage tool orchestration, or autonomous execution as part of the surface being
built. A checkout redesign is never asked for a fake verdict.

## BUILD-PLAN.md task grammar

```
- [ ] T1 · worker=drive · scope=src/components/Chip.tsx,src/styles/chip.css · Build the chip variants
```

Status tokens (foreman's, absorbed): `[ ]` todo · `[>]` active · `[~]` review ·
`[t]` testing · `[b]` blocked · `[x]` done · `[!]` failed · `[?]` needs input.

## The scope boundary (drive mode)

HLD builds the surface **and its minimal wiring**: components, styles, routes into
existing pages, state slices, a fetch call to an *existing* endpoint, copy, tests.
HLD **stops and names Foreman** when a task requires a whole non-UI subsystem: a new
endpoint or service, a schema change or migration, an auth change.
`gate.py boundary "<task text>"` prints `BUILD` or `STOP — <subsystem>`.

## The nine viewport bands

| Band | Width | | Band | Width |
|---|---|---|---|---|
| mobile-s | 320 | | tablet-l | 1024 |
| mobile-m | 375 | | desktop-s | 1280 |
| mobile-l | 430 | | desktop-m | 1600 |
| tablet-s | 600 | | ultrawide | 2560 |
| tablet-m | 768 | | | |

Effort size bounds **capture breadth, never test kinds**: S captures mobile-m /
tablet-m / desktop-s; M (the unattended default) and L capture all nine. Light and dark
at every captured band. Negative-scenario testing runs at every size; regression only
when the client asked for it.

## Screenshots and sidecars

`H4-{band}-{theme}-{flow}-{NN}-{state}.png`, never renumbered. In TEST-PLAN.md each
required shot is one line — `- H4-....png` optionally followed by an annotation — and
a malformed `- H4-` line is a g4 error, never silently ignored. Every PNG gets a sidecar
written by `scripts/sidecar.py`: url, viewport, theme, dpr, build SHA, sha256 of the
image and of the a11y snapshot. A shot without a sidecar does not count at g4.

## findings.csv

```
id,severity,rule,source,file,line,note,disposition
```

Severity 0–4. `source` is `detect` (impeccable's detect.mjs), `contract` (HLD's own
rules), `critic`, or `walk`. Severity ≥ 3 requires a disposition before g2/g4. Taste
never blocks; severity does.

## The conflict stack — who wins when guidance disagrees

1. The client's own words (BRIEF.md)
2. The repo's design contract (contract.json)
3. H1 research + the kill-door verdict
4. Craft floor and per-surface mode (locked at H2)
5. Dataset lookups (principles/symptoms/behavior tables)
6. Any ambient host doctrine (rank describes authority, not presence)
7. Generic taste — which never blocks anything
