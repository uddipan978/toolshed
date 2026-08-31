# Troubleshooting

## Contents
- Spawning and supervision
- Cross-session messaging
- Compaction and handover
- Browser testing
- Dependencies
- Sources that were rejected

## Spawning and supervision

**`--bg` and `-p` refuse to combine.** Claude Code rejects the pair explicitly. Foreman
workers must be `-p`, because `--max-budget-usd`, `--max-turns` and `--output-format` are
all print-mode only. That is why `spawn.sh` backgrounds the process with `nohup` rather
than using `--bg`.

**A `-p` worker starts in Manual permission mode** unless `--permission-mode` is passed.
Omit it and the worker blocks on its first tool call with nobody to answer.

**`claude agents --json` shows `state: null` for `-p` sessions.** It confirms the session
exists and is addressable, but the state fields are only populated for interactive ones.
This is why `supervise.py` derives state from the captured stream instead.

**Never parse `~/.claude/projects/**/*.jsonl`.** The format is documented as internal and
version-unstable. The captured `stream-json` in `sessions/<name>/stream.jsonl` carries the
same numbers through a supported interface.

**Context percentage** is `input_tokens + cache_creation_input_tokens +
cache_read_input_tokens` from the last assistant message, over the model's window. Output
tokens are excluded — this matches how Claude Code computes it for the status line.

**A worker that says its task file is missing is telling the truth.** A worktree is a
fresh checkout of the branch, so anything uncommitted in the main tree is invisible
inside it — and `.foreman/` is almost always uncommitted when a worker spawns. `spawn.sh`
writes a `commit-tree` snapshot of `.foreman/` and `.gitignore` **without moving the
user's HEAD or index**, then points the new branch at that commit. If the snapshot
fails, spawn exits non-zero — it does not continue on a tree with no task file. If you
bypass `spawn.sh`, produce an equivalent snapshot yourself.

**G2 is `--g2-clear`, not "CRITIQUE.md exists".** A file with open findings, a pending
re-critique, or a thin "looks reasonable" body is not a passed gate. The router and
the dashboard badge both call `verify_gate.py --g2-clear`.

**`work/memory.md` going stale is a gate miss, not a style miss.** The file is
gitignored, so compact loses whatever was only in the manager's head. `--check-memory`
compares **Gate** to artefacts (`G0`–`G3`/`G6`). Non-zero: rewrite, then route.
A **Last updated: G0 intake** after task files exist is the failure this check
exists for.

**G2a spawn is `--g2-spawn`, not a prompt `if`.** Missing file, thin file, or
`pending` under the round cap exits 0. Open findings with `done`, `pending` at
round 4, or a 4th counted spawn exits 1 — that is G2b, not another fork. Rewinding
`done` → `pending` without `--g2-may-pending` exiting 0 is the loop that burns
rounds. Schema retries on a thin file stop at 3.

## Grok

**`FOREMAN_HARNESS=grok`** (or a Grok TUI session: `GROK_SESSION_ID`) selects
`scripts/adapters/grok/spawn.sh`. Claude remains the default. See
[harness.md](harness.md).

**Headless `grok -p` does not create a worktree from `--worktree`.** The Grok adapter
creates `.grok/worktrees/foreman-<name>/` itself, same as the Claude adapter does for
`.claude/worktrees/`.

**Grok has no `--max-budget-usd`.** Spend is read from the stream; the supervisor emits
`BUDGET` when it crosses the value stored in `status.json`. Stop the pid.

**`POKE` cannot reach a Grok `-p` worker.** There is no `SendMessage` equivalent. Treat
POKE as log-only; act on `STUCK`.

**G2 is not a forked skill.** Spawn `--agent foreman-critic --worktree no`.

**Worker working files must use absolute paths.** The worker's cwd is its worktree, so a
relative `.foreman/work/sessions/<name>/progress.md` resolves inside the worktree — where
the supervisor and the handover hook never look. `spawn.sh` appends the absolute session
path to the brief.

## Cross-session messaging

**A worker that never receives pokes is missing `crossSessionInbound: "accept"`.** Without
it an unattended `-p` session holds the message behind an approval dialog nobody can
answer, and it expires after `dialogExpiry` (5 minutes by default). `spawn.sh` passes it.

**"No agent named X is reachable"** usually means the worker already exited. Check
`ListAgents` and the tail of its `stream.jsonl` before assuming the channel is broken.

**Messages drain at the receiver's next tool round.** A worker mid-way through a long Bash
call will not react until that call returns. This is normal; do not re-send.

## Compaction and handover

**Compaction fires at 55%** because `spawn.sh` exports `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`.
That variable can only *lower* the threshold — a value above the default is ignored.

**It takes two hooks, not one.** `PreCompact` stdout is not injected into context, so the
handover is written to a file there and echoed by a `SessionStart` hook with matcher
`compact`, whose stdout *is* injected.

**A thin handover means a thin `progress.md`.** The document is assembled from durable
artefacts — the brief, `progress.md`, git state — not from summarising the transcript.
Workers are told to keep `progress.md` current for exactly this reason.

**Spend and turns do not reset on compaction.** A worker that compacts twice is usually a
task that should have been two tasks.

## Browser testing

**`file:` URLs are blocked in Playwright MCP.** Serve the build over HTTP and target
`localhost`. This bites every first attempt at testing a static build.

**`--caps=testing` is what provides `browser_generate_locator`.** Foreman bundles its own
`.mcp.json` for this: the marketplace `playwright` plugin hardcodes no flags, so installing
it instead of using the bundled config silently loses the capability. The README's options
table also omits `testing` from the `--caps` list; `config.d.ts` is authoritative.

**`--isolated` matters under concurrency.** Parallel testers sharing a browser profile
interfere with each other; upstream recommends `--isolated` or distinct `--user-data-dir`
whenever multiple MCP clients run at once.

**Reconnaissance before action.** Navigate, wait for the page to settle, snapshot, *then*
derive selectors. Selectors invented before looking at the page are why suites flake.

## Dependencies

**Never write a version constraint for `impeccable` or `ui-ux-pro-max`.** Claude Code
resolves semver ranges against `{plugin-name}--v{version}` git tags. Those repos tag as
`skill-v4.1.2` and `v2.15.0`, so a constrained install fails with `has no git tag
satisfying ^4`. Declare them as bare names.

**Cross-marketplace dependencies need an allowlist.** `marketplace.json` must carry
`allowCrossMarketplaceDependenciesOn`. Only the root marketplace's list is consulted —
trust does not chain.

**`impeccable` needs Node ≥ 22.18.** Below that its hooks silently no-op and write
`~/.impeccable/node-unsupported`. Preflight checks the version for this reason.

**A `ui-ux-pro-max` copy under `~/.agents/skills/` is broken.** Its SKILL.md invokes
scripts via `${CLAUDE_PLUGIN_ROOT}`, which is only set for plugin-installed components —
loaded from a plain skills directory the variable is empty and every documented invocation
fails silently. Install it as a plugin.

## Sources that were rejected

Recorded so nobody re-proposes them:

| Candidate | Why not |
|---|---|
| `anti-slop-ui` (claude-community) | source repo returns 404 — stale catalogue entry |
| `audit-suite`, `claude-seo-and-geo-site-audit` | 0–1 stars, no licence |
| `a11y-fixer`, `accessibility-audit`, `accessibility-test` | machine-generated one-liners |
| `the-design-library`, `design-with-claude` | 10–11 stars, non-standard licence |
| `claude-flow` / Ruflo | vendor-published benchmarks, unverifiable; 60-agent hive contradicts Anthropic's own 3–5 sizing data |
| Agent Teams as the substrate | teammates cannot spawn sub-agents, need an interactive session, and their idle notification carries no output — a manager waiting on results stalls |

Accessibility and UX auditing is covered by `impeccable audit` plus `chrome-devtools` MCP
Lighthouse instead. There is no dependency-grade a11y plugin on either Anthropic marketplace.
