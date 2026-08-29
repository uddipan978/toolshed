---
name: ui
description: Internal HLD stage — do not invoke directly; it auto-loads from /hld, or call /hld:ui explicitly. Locks the direction, produces IA-traced HTML wireframes and the UI-SPEC.
argument-hint: "[direction notes, optional]"
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# HLD stage — ui

The run’s grammar and gates: [reference/hld-gates.md](../../reference/hld-gates.md). This stage assumes a
`.hld/` run exists (start one with `/hld` if not; `gate.py status` shows where it is).

H2: lock ONE direction and show it. Wireframes go to `.hld/WIREFRAMES/index.html` —
walkable HTML, low-fidelity, real copy from IA.md, every region traceable to the object
model ([reference/doctrine/deliverables.md](../../reference/doctrine/deliverables.md)).
`UI-SPEC.md` carries the region→IA trace table and a real `## Rejected alternatives`.
Greenfield: author the starter contract into `.hld/contract.json` (offer promotion,
never write into the repo unasked). If ui-ux-pro-max is on this machine,
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py palette <query>` / `type` / `ux` consults its
tables — recorded, and absence is recorded too. Then
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/slop.py --root <repo>`, disposition every sev≥3 finding,
`gate.py check g2`.
