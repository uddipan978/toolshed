# HLD — Human-Like Design

A gated UX/UI studio for AI coding agents. One grill at the start, then it runs on its
own to the end: research with a **kill door** (a feature that shouldn't exist gets a
recorded *no*, and the handoff still runs), IA-derived wireframes (never template
galleries), a locked direction with rejected alternatives, then build and proof at nine
real viewport widths in light and dark.

Three invariants:

1. **Installs nothing at runtime, mutates nothing it doesn't own.** A missing tool is a
   recorded `COULD-NOT-RUN`, never an install and never a crash. `/hld:doctor` prints
   what's missing and the exact command — you run it.
2. **No house style.** The target repo's own design contract (design.md / UI-DESIGN.md /
   token file) is ingested at H0 and outranks every skill and every model default. Slop
   detection is contract-parameterized; taste never blocks, severity does.
3. **Provenance on every claim.** Every recommendation names a principle, an evidence
   grade, and a build cost, from the absorbed human-like-thinking tables.

## Install

```bash
# Claude Code
claude plugin marketplace add /Users/shankhajeettaran/workspace/experiments/toolshed/hld
claude plugin install hld@hld --scope user

# Grok Build
grok plugin install /Users/shankhajeettaran/workspace/experiments/toolshed/hld --trust

# Codex CLI (router only — stage calls and hooks are Claude/Grok; no plugin runtime)
ln -s /Users/shankhajeettaran/workspace/experiments/toolshed/hld/skills/hld ~/.codex/skills/hld
# On Codex, ${CLAUDE_PLUGIN_ROOT} is not substituted: the scripts live at
#   /Users/shankhajeettaran/workspace/experiments/toolshed/hld/scripts/
# (resolve the plugin dir from the skill file's real location), and the Stop-hook
# behavior runs as `gate.py --final` invoked manually at the end of a run.
```

The plugin cache **copies** files at install time — editing this repo does not change
what is installed. Fast loop for testing edits:

```bash
claude --plugin-dir /Users/shankhajeettaran/workspace/experiments/toolshed/hld
```

Reinstall after edits (version bump alone is not enough):

```bash
claude plugin uninstall hld
rm -rf ~/.claude/plugins/cache/hld
claude plugin marketplace update hld
claude plugin install hld@hld --scope user
```

## Use

`/hld <what you want designed or critiqued>` — or just describe a UX/UI task; the router
triggers on design, critique, wireframe and flow work.

The run writes everything into `.hld/` at a root you choose during the grill:

| Gate | Stage | Blocker (checked by `scripts/gate.py`, not prose) |
|---|---|---|
| g0 | H0 grill | zero `[NEEDS CLARIFICATION]` in BRIEF.md; contract named or `NONE-EXISTS` |
| g1 | H1 research | kill-door verdict recorded (`PROCEED` or `KILL`) |
| g2 | H2 direction | IA beat done; rejected-alternatives written; every sev≥3 finding dispositioned |
| g3 | H3 plan | every task has a worker + non-overlapping file scope |
| g4 | H4 build+prove | no required shot absent without a script-captured `COULD-NOT-RUN` |
| g5 | H5 handoff | auto-decision block present; no open tasks |

H1b (the IA beat — object model + copy inventory) is a beat inside H1/H2, not a seventh
gate. A `KILL` at g1 skips H2–H4; H5 still runs and packages the no with its evidence.

## Standalone or with Foreman

At H3 the probe checks for a **runnable** Foreman (its `verify_gate.py --help` must
exit 0 — a half-install counts as absent). Present → HLD hands over BUILD-PLAN.md and
keeps only the watch seam (recapture-verified UI checks). Absent → HLD drives the build
itself, in-session and sequential: one task at a time, `commit_check.py`-wrapped commits,
a gate check between tasks, and a fresh-context critic per task where the host supports
subagents (recorded `COULD-NOT-RUN` on isolation where it doesn't).

HLD builds the surface **and its minimal wiring** (components, styles, routes into
existing pages, state, a fetch call to an *existing* endpoint). It stops and names
Foreman when a task needs a whole non-UI subsystem (new endpoint/service, schema or
migration, auth).

## Individual calls

The stages are also explicit calls — they never auto-trigger:

`/hld:walk` · `/hld:brief` · `/hld:research` · `/hld:ui` · `/hld:plan` · `/hld:build` ·
`/hld:prove` · `/hld:handoff` · `/hld:doctor`

## Verify the plugin itself

```bash
python3 scripts/data_check.py     # dataset schemas + provenance
python3 scripts/eval.py           # deterministic fixture suite (kill door, slop, boundary, plan grammar)
```

## Uninstall

`claude plugin uninstall hld`. HLD wrote nothing outside its own cache and your chosen
`.hld/` directories, so there is nothing else to clean.
