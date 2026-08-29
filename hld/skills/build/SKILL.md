---
name: build
description: Internal HLD stage — do not invoke directly; it auto-loads from /hld, or call /hld:build explicitly. Drives BUILD-PLAN tasks in-session (or defers to Foreman) with commit checks and critics.
argument-hint: "[task id, optional]"
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git status *), Bash(git diff *), Bash(git log *), Bash(git add *), Bash(git commit *)
---

# HLD stage — build

The run’s grammar and gates: [reference/hld-gates.md](../../reference/hld-gates.md). This stage assumes a
`.hld/` run exists (start one with `/hld` if not; `gate.py status` shows where it is).

H4 build. Foreman present (per the recorded defer decision): hand over BUILD-PLAN.md
and keep the watch seam — recapture after every UI task; if you did not recapture, you
did not watch. Otherwise drive in-session, one task at a time: `[>]` → implement inside
`scope=` → stage those exact paths → `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit_check.py
--task Tn --plan .hld/BUILD-PLAN.md --msg "<msg>"` → commit → fresh-context critic
(subagent where the host has one — it RUNS the verification itself; else a separate
recorded pass, isolation COULD-NOT-RUN) → `[x]` with evidence. One task = one commit.
