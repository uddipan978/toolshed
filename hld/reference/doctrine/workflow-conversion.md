<!-- Distilled from the owner's workflow-conversion model, snapshot 2026-08-30. -->

# Workflow conversion — scripted fan-out, gated on opt-in

A workflow is a deterministic orchestration script for one fan-out: ordinary code
decides control flow (loops, joins, budgets, gates); agents supply judgment inside each
step. Convert when the task's *shape* is more reliable than the model's memory of it.

**Assessing is always allowed. Running requires the user's explicit opt-in** — their own
words asking for a workflow/fan-out, a skill that instructs it, or a standing session
opt-in. A task that would merely benefit is never authorization.

Verdicts: **Convert** (shape known, fan-out real, opt-in exists) · **Offer** (state the
shape and rough cost in two lines, continue directly meanwhile) · **Direct** (one agent
or tool call does the job; coupled edits; fewer than ~3 independent units).

Convert-signals: N independent items known or cheaply scoutable; the same operation per
item; findings needing adversarial verification; unknown-size discovery until dry;
wall-clock dominated by per-item latency. Direct-signals: coupled edits to the same
files; next step depends on the last step's result; coordination costs more than the
work.

Rules when converting: scout the item list first, never guess it in the script; bound
every loop; log anything dropped — silent truncation reads as full coverage; one
well-scoped fan-out per invocation; completion remains the controller's call on
evidence.
