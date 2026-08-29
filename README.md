# toolshed

Claude Code / Grok / Codex plugins. Each plugin is a self-contained directory with its
own `.claude-plugin/` manifest, README, license and tests.

| Plugin | What it does | Install |
|---|---|---|
| [foreman](foreman/) | Agentic SDLC orchestration — a manager session spawns and supervises worker sessions through gated lifecycle phases. | `claude plugin marketplace add <repo>/foreman && claude plugin install foreman@claude-tooling --scope user` |
| [hld](hld/) | Human-Like Design — a gated UX/UI studio: grill once, research with a kill door, IA-derived wireframes, contract-based anti-slop, nine-viewport proof. Standalone, or defers to foreman when one is present. | `claude plugin marketplace add <repo>/hld && claude plugin install hld@hld --scope user` |

`<repo>` is this checkout's path, e.g. `/Users/shankhajeettaran/workspace/experiments/toolshed`.

Both plugins are MIT licensed (per-plugin LICENSE files). HLD absorbs foreman's four
worker-contract formats (MIT, SHA-pinned in [hld/CREDITS.md](hld/CREDITS.md)); the
foreman engine itself is not duplicated — HLD detects a runnable foreman at plan time
and defers to it.
