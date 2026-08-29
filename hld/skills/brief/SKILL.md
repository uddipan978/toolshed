---
name: brief
description: Internal HLD stage — do not invoke directly; it auto-loads from /hld, or call /hld:brief explicitly. Runs the one-time H0 grill and writes BRIEF.md until g0 passes.
argument-hint: "[what to grill about]"
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# HLD stage — brief

The run’s grammar and gates: [reference/hld-gates.md](../../reference/hld-gates.md). This stage assumes a
`.hld/` run exists (start one with `/hld` if not; `gate.py status` shows where it is).

The H0 grill — the only stage that asks questions, and it asks them ONCE, batched.
Cover: the surface and its users; where `.hld/` lives; the design contract paths
(parse into `.hld/contract.json`; else `Contract: NONE-EXISTS`); effort size S/M/L
(default M); design-only or drive the build. Write `BRIEF.md` + `STATUS.md`, create
`.hld/.gitignore` containing `work/`, then `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate.py check g0`, and re-run
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/probe.py` so `.hld/work/host.json` persists for
H3's defer decision and any cold resume.
After g0: no more questions — the closed pause list is
[reference/doctrine/autonomy.md](../../reference/doctrine/autonomy.md).
