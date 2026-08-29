---
name: doctor
description: Internal HLD stage — do not invoke directly; it auto-loads from /hld, or call /hld:doctor explicitly. Prints the environment report: tools, Foreman defer status, collision diff, eval suite.
argument-hint: "[]"
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# HLD stage — doctor

The run’s grammar and gates: [reference/hld-gates.md](../../reference/hld-gates.md). Doctor touches no run state — it is exactly the thing to run cold, before any run exists.

Environment report, no mutations ever:
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py` — what is present, what is missing with the
exact install command for YOU to run, whether a runnable Foreman was found (defer vs
drive), and the human-like-thinking trigger-collision diff (user action required; HLD
never edits that file). `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/eval.py` runs the plugin's own
deterministic fixture suite if you want proof the gates work on this machine.
