<!-- Distilled from the owner's agent-as-graph mental model, snapshot 2026-08-30.
     Read at H3 whenever the surface being designed/built is itself agentic. -->

# Agent-as-graph — when the thing you're building contains an agent

An agent-as-graph architecture represents an agentic system as an explicit state
machine: **nodes perform meaningful work** (deterministic code, one model call, a tool
call, or a whole agent loop), **edges control what may happen next**, **state carries
durable evidence**. The model provides judgment; the graph provides control.

## The spectrum — choose the least autonomous mechanism that works

1. Deterministic code
2. One model call with structured output
3. A fixed chain of calls
4. Conditional routing
5. A graph with branches and bounded cycles
6. A flexible agent loop
7. A complete agent as one node inside a larger graph

## Feasibility signals (graph is worth it when several hold)

- Multiple meaningful states with different responsibilities
- Conditional routing on state, evidence, risk, or external signals
- Validation / revision / retry cycles; deterministic safety or completion gates
- Human approval points; long-running work that must pause, resume, recover
- Fan-out into independent workers followed by aggregation
- Terminal conditions checkable independently of the agent's own claim of "done"

Prefer non-graph when: the task is one call; the flow is short and linear; the work is
open-ended discovery; graph state would be artificial; orchestration cost exceeds the
reliability benefit.

## Design rules

- Smallest graph that captures the real workflow — never one node per function.
- Deterministic code for validation, permissions, budgets, retry limits, completion.
- Model judgment for ambiguity, investigation, synthesis, diagnosis.
- Bound every loop. Make retryable nodes idempotent. Gate irreversible actions behind
  explicit authorization. Never let an LLM evaluator override a deterministic check.
- State: typed, minimal, inspectable — evidence over summaries.

## The verdict

When H3 plans an agentic surface, BUILD-PLAN.md records under `## Workflow architecture`:

```
Agent-as-graph: graph | hybrid | non-graph — <one-line justification>
SDD: use | partial | none — <one-line justification>
Workflow-conversion: convert | offer | direct — <one-line justification>
```

`gate.py` requires this block only when the run is agentic (deterministic keyword
checklist) — an ordinary UI surface is never asked for a fake verdict.
