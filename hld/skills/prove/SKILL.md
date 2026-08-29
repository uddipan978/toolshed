---
name: prove
description: Internal HLD stage — do not invoke directly; it auto-loads from /hld, or call /hld:prove explicitly. Captures the nine-band proof with sidecars and writes TEST-REPORT.md until g4 passes.
argument-hint: "[]"
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git status *), Bash(git diff *), Bash(git log *), Bash(git add *), Bash(git commit *)
---

# HLD stage — prove

The run’s grammar and gates: [reference/hld-gates.md](../../reference/hld-gates.md). This stage assumes a
`.hld/` run exists (start one with `/hld` if not; `gate.py status` shows where it is).

H4 proof. `TEST-PLAN.md` lists required shots `H4-{band}-{theme}-{flow}-{NN}-{state}.png`
across the effort size bands (M = all nine), light AND dark, walkthrough AND negative
scenarios. Capture with the browser this host has; every PNG gets
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sidecar.py <png> --url .. --viewport .. --theme ..`.
Replay the pinned walk (`ledger.py verify --against <steps>`) — divergence is a
DIVERGED-PATH verdict to record. Whatever cannot run: a script-captured
`COULD-NOT-RUN: <shot> — <reason>` line in `TEST-REPORT.md`. `gate.py check g4`.
