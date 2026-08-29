---
name: plan
description: Internal HLD stage — do not invoke directly; it auto-loads from /hld, or call /hld:plan explicitly. Writes BUILD-PLAN.md with bounded tasks, boundary checks and the defer decision.
argument-hint: "[]"
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# HLD stage — plan

The run’s grammar and gates: [reference/hld-gates.md](../../reference/hld-gates.md). This stage assumes a
`.hld/` run exists (start one with `/hld` if not; `gate.py status` shows where it is).

H3: read [reference/doctrine/sdd.md](../../reference/doctrine/sdd.md) and
[commit-discipline.md](../../reference/doctrine/commit-discipline.md) (+
[agent-as-graph.md](../../reference/doctrine/agent-as-graph.md) with the verdict block
if the surface is agentic). Write `BUILD-PLAN.md` in the task grammar — reviewable
units, `worker=`, non-overlapping `scope=`. Run
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate.py boundary "<task>"` per task; STOP tasks are
marked `[b]` with the subsystem named for Foreman. Record the defer decision once
(probe says whether a runnable Foreman exists). `gate.py check g3`.
