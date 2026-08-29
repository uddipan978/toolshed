---
name: handoff
description: Internal HLD stage — do not invoke directly; it auto-loads from /hld, or call /hld:handoff explicitly. Packages the run (or the kill) into HANDOFF.md and closes g5.
argument-hint: "[]"
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# HLD stage — handoff

The run’s grammar and gates: [reference/hld-gates.md](../../reference/hld-gates.md). This stage assumes a
`.hld/` run exists (start one with `/hld` if not; `gate.py status` shows where it is).

H5 — runs even after a kill. `HANDOFF.md`: decisions and why, evidence by exact shot
name, findings + dispositions, effort deltas (`effort.py --compare .hld/work/effort-before.csv .hld/work/effort-after.csv` when both exist), the `## Auto-decisions` block, and what a
human should review first. Set `state: done` (or confirm `killed`);
`gate.py check g5`. The Stop hook (`gate.py --final`) refuses a false done — an honest
pause is always allowed.
