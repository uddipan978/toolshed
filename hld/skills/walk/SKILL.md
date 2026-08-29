---
name: walk
description: Internal HLD stage — do not invoke directly; it auto-loads from /hld, or call /hld:walk explicitly. Walks a live UI like a real human and counts the effort, logging a replayable path.
argument-hint: "[url or route to walk]"
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# HLD stage — walk

The run’s grammar and gates: [reference/hld-gates.md](../../reference/hld-gates.md). This stage assumes a
`.hld/` run exists (start one with `/hld` if not; `gate.py status` shows where it is).

Walk the surface the way a real human would — drive the actual UI, never describe what
you did not see. Click through it, fill the forms, hit the failure paths. Count before
you opine: steps, fields, waits, reading load (`scripts/effort.py`). Log every step:
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ledger.py log "<step>"`, and `ledger.py pin` when done —
H4 replays this exact path and a change is a DIVERGED-PATH verdict.
Method: [reference/hlt/walkthrough.md](../../reference/hlt/walkthrough.md). Also record the structured effort ledger to `.hld/work/effort-<flow>.csv` in the
format `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/effort.py --example` prints, then score
it: `effort.py .hld/work/effort-<flow>.csv`. Findings go to `.hld/findings.csv` with
source=walk, severity-ranked, principle + grade attached (`scripts/why.py --symptom`).
