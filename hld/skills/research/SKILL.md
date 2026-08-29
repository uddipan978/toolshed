---
name: research
description: Internal HLD stage — do not invoke directly; it auto-loads from /hld, or call /hld:research explicitly. Writes the graded UX-REPORT and records the kill-door verdict, plus the IA beat.
argument-hint: "[surface or feature]"
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# HLD stage — research

The run’s grammar and gates: [reference/hld-gates.md](../../reference/hld-gates.md). This stage assumes a
`.hld/` run exists (start one with `/hld` if not; `gate.py status` shows where it is).

H1: evidence, then the kill door. Walk first if the surface exists (/hld:walk). Query
the tables — `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/why.py --symptom "<phrase>"` — every claim carries
principle + evidence grade + build cost. Then the verdict this stage exists for:
B=MAP · Tesler dump · one-sixth effect-size floor · ethics gate. Write `UX-REPORT.md`
ending in `Kill-door verdict: PROCEED` or `KILL — <reason>`; `gate.py check g1`.
KILL is a valid answer: skip to /hld:handoff and package the no. Also write the IA beat
into `IA.md` (object model + copy inventory) — wireframes must trace to it.
