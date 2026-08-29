---
name: hld
description: Human-Like Design (HLD) — a gated UX/UI studio. Use for designing, redesigning or critiquing a product surface, screen, flow or feature; wireframes and IA; UX reports grounded in evidence; walking a UI like a real human and counting the effort; deciding whether a feature should exist at all; and building the designed surface with proof at real viewport widths. Triggers on "HLD", "human-like design", design/critique/wireframe/UX-report/walkthrough requests. Not for backend-only work, and not a generic beautifier — it grills once, then runs gated to the end.
argument-hint: "[the surface or feature to design/critique, or 'resume' / 'status']"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git status *), Bash(git diff *), Bash(git log *), Bash(git add *), Bash(git commit *)
---

# HLD — Human-Like Design

**Request:** $ARGUMENTS

One run designs (and optionally builds) **one surface**, through six gates. The gates,
artifact grammar, conflict stack, viewport bands and scope boundary live in
[reference/hld-gates.md](../../reference/hld-gates.md) — read it once per run; follow
it, don't restate it. Commands below use `${CLAUDE_PLUGIN_ROOT}` (substituted by the
host); on Grok use `${GROK_PLUGIN_ROOT}`, and on any other host resolve the plugin
directory from this file's own location (`<plugin>/skills/hld/SKILL.md` → `<plugin>/scripts`).

Three invariants, non-negotiable:
1. **Install nothing, mutate nothing you don't own.** A missing tool is a recorded
   `COULD-NOT-RUN`. Never edit another skill's files; never write into the repo outside
   `.hld/` and the build tasks' declared scopes.
2. **No house style.** The repo's contract (`.hld/contract.json`) outranks every skill
   and every default you have. Taste never blocks; severity does.
3. **Provenance on every claim** — principle + evidence grade + build cost, from
   `data/*.csv` (query with `scripts/why.py`, effort with `scripts/effort.py`).

`resume` / `status` → `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate.py status`, read
`.hld/STATUS.md` and the artifacts, and continue from the open gate. Never redo a gate
that passed; never redispatch a task marked `[x]`.

## H0 — grill once (the only stage that asks questions)

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/probe.py` first and note what this host can do.

Interview the user until nothing is assumed — in ONE pass, batched questions, covering:
the surface and its users; where `.hld/` lives (their choice); the design contract
(paths to design.md / UI-DESIGN.md / token files — parse tokens, primitives, MUST-NOT
lines into `.hld/contract.json`; if none exists, record `Contract: NONE-EXISTS`);
effort size S/M/L (default **M** — bounds capture breadth, never test kinds); whether
to stop at the wireframe/spec or drive the build; anything marked
`[NEEDS CLARIFICATION]` gets asked now or dies here.

Write `BRIEF.md` (with the `Contract:` line), `STATUS.md` (`state: running`,
`gate: H0`), and `.hld/.gitignore` containing `work/`, then
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate.py check g0` — and re-run `probe.py` now
that `.hld/` exists, so `work/host.json` persists for H3 and cold resumes.

**After g0 passes, run on your own to the end.** The closed pause list is
[reference/doctrine/autonomy.md](../../reference/doctrine/autonomy.md). Small ambiguous
choices become `decisions/D*.md` entries, not questions.

## H1 — research, and the kill door

If the surface exists, **walk it like a real human** before opining
([reference/hlt/walkthrough.md](../../reference/hlt/walkthrough.md)): drive the real UI,
never describe what you did not see; count steps and effort; log every step with
`scripts/ledger.py log`, and `ledger.py pin` when the walk is done — H4 replays this
path. Count before you opine.

Write `UX-REPORT.md`: findings with grades, effort counts, and **the kill-door
verdict** — the decision this stage exists to make honestly:

- Does the feature clear B=MAP — a real prompt, ability, motivation?
- Does it dump Tesler complexity on the user instead of the system?
- Does the expected effect clear the one-sixth effect-size floor?
- Does it pass the ethics gate (truth, disclosure survival, reversibility symmetry,
  no deficit exploitation)?

Record `Kill-door verdict: PROCEED` or `Kill-door verdict: KILL — <reason>`, then
`gate.py check g1`. **KILL (exit 3) is a valid answer, not a failure**: skip H2–H4, set
`state: killed`, go to H5 and package the no with its evidence. Apply the
aesthetic-usability counter-procedure from
[reference/hlt/critique.md](../../reference/hlt/critique.md) before trusting any
"it looks fine".

**The IA beat (H1b):** write `IA.md` — the object model and the copy inventory. Every
wireframe region will have to trace to it; this is what makes the layout come from
*this* product instead of a template gallery.

## H2 — direction lock and wireframes

Choose the per-surface mode and lock ONE direction. Write the walkable wireframe to
`WIREFRAMES/index.html` per
[reference/doctrine/deliverables.md](../../reference/doctrine/deliverables.md) —
low-fidelity, real copy from the inventory, every region traceable to IA.md. Write
`UI-SPEC.md` with the region→IA trace table and a real `## Rejected alternatives`
paragraph (what was considered, why it lost). Greenfield (`NONE-EXISTS`): author the
starter contract into `.hld/contract.json` now — offer promotion into the repo, never
do it unasked. For palette/typography/guideline ideas,
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py palette|type|ux <terms>` consults
ui-ux-pro-max's tables when that skill is installed (cite as pro-max lookup, grade
heuristic; its absence is a recorded `COULD-NOT-RUN`) — the contract still outranks
anything it returns.

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/slop.py --root <repo> ` — detect.mjs when present,
contract rules always. Disposition every severity ≥ 3 finding in `findings.csv`, then
`gate.py check g2`.

## H3 — plan

Read [reference/doctrine/sdd.md](../../reference/doctrine/sdd.md) and
[reference/doctrine/commit-discipline.md](../../reference/doctrine/commit-discipline.md);
if the surface itself is agentic, also
[reference/doctrine/agent-as-graph.md](../../reference/doctrine/agent-as-graph.md) and
add the `## Workflow architecture` verdict block.

Write `BUILD-PLAN.md` in the task grammar — every task a reviewable unit with
`worker=` and a non-overlapping `scope=`. Run
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate.py boundary "<task text>"` on each task: a `STOP`
task is marked `[b]` with the blocking subsystem named — that work belongs to Foreman
or the user, never silently absorbed.

**Defer decision, once:** probe reported whether a runnable Foreman exists. Record the
decision in `decisions/` and never re-evaluate it mid-run. Then `gate.py check g3`.
If the user chose design-only, skip to H5 after g3.

## H4 — build and prove

**Foreman present → defer.** Hand `BUILD-PLAN.md` to Foreman and keep the watch seam:
after every UI task Foreman reports done, **recapture** — screenshot + a11y snapshot +
`scripts/sidecar.py` — and re-run `slop.py` on the changed files. If you did not
recapture, you did not watch.

**No Foreman → drive, in-session and sequential.** Per task: mark `[>]` → implement
strictly inside `scope=` → stage those exact paths (never `git add -A`) →
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit_check.py --task Tn --plan .hld/BUILD-PLAN.md
--msg "<message>"` → commit → **fresh-context critic**: where this host has subagents,
dispatch one with the task brief and
[reference/formats/critique-format.md](../../reference/formats/critique-format.md) — it
must RUN the verification commands, not just read the diff; where it doesn't, do a
separate recorded critic pass and mark isolation `COULD-NOT-RUN` in the ledger →
disposition findings → mark `[x]` with evidence. One task = one commit (amend that
task's own unpushed commit for its own defects).

**Prove.** Write `TEST-PLAN.md`: required shots (`H4-{band}-{theme}-{flow}-{NN}-{state}.png`)
across the bands for the chosen effort size, light and dark, walkthrough AND
negative scenarios (wrong input, empty states, failure paths — every size runs these;
regression only if the brief asked). Capture with the browser available to this host;
`scripts/sidecar.py` for every PNG. Replay the pinned path (`ledger.py verify`) —
divergence is a `DIVERGED-PATH` verdict to record, not to hide. What can't run gets a
script-captured `COULD-NOT-RUN: <shot> — <reason>` line in `TEST-REPORT.md`. Then
`gate.py check g4`.

## H5 — handoff (runs even after a kill)

Write `HANDOFF.md`: what was decided and why, the evidence (shots by exact name,
findings and dispositions, effort deltas from `effort.py`), the `## Auto-decisions`
block listing every decision made without asking, and what a human should review
first. Set `state: done` (or confirm `killed`), then `gate.py check g5`.

Never claim done while a gate is open — the Stop hook runs `gate.py --final` and will
refuse a false completion. An honest pause mid-run is always allowed.
