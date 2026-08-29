# Credits and provenance

Every absorbed or vendored source, with its license and the exact state it was taken
from. HLD never copies unlicensed third-party text; those tools are runtime-detected
instead (missing = `COULD-NOT-RUN`).

## Absorbed

| Source | What | License | Pinned |
|---|---|---|---|
| `human-like-thinking` (this machine, user-authored) | `data/principles.csv`, `data/symptoms.csv`, `data/conflicts.csv`, `data/effort-weights.csv`, `scripts/why.py`, `scripts/effort.py`, `reference/hlt/*` (11 docs) | author's own | snapshot 2026-08-30 |
| `foreman` (this repo) | `reference/formats/{task-format,delegation-brief,critique-format,gates}.md` — the four worker-contract formats and status tokens. **The engine (spawn/supervise/board/handover/scaffold/integrate/dashboard and the five roles) is deliberately NOT absorbed** — HLD defers to a runnable Foreman and otherwise drives in-session. | MIT © 2026 Uddipan Dey | commit `31b38123fb47ca1fe8aa73a4108d4b9e03ce4194` |
| Machine doctrine (`~/.claude/CLAUDE.md` + `~/.claude/memory/`) | `reference/doctrine/*` — distilled, machine paths parameterized out | author's own | snapshot 2026-08-30 |

MIT notice for the foreman-derived files:

> MIT License — Copyright (c) 2026 Uddipan Dey. Permission is hereby granted, free of
> charge, to any person obtaining a copy of this software and associated documentation
> files, to deal in the Software without restriction. THE SOFTWARE IS PROVIDED "AS IS",
> WITHOUT WARRANTY OF ANY KIND.

## Runtime-detected, never copied (no license in their trees)

| Tool | Used as | When absent |
|---|---|---|
| `impeccable` — `scripts/detect.mjs` | the generic slop detector (59 rules, exit 2 on findings), run by `scripts/slop.py` when present | `COULD-NOT-RUN`; HLD's own contract-parameterized rules still run |
| `ui-ux-pro-max` — data CSVs | lookups (palettes, typography, guidelines) during H1/H2 when present | skipped; recorded |
| `grill-me` | inspiration only — the H0 grill discipline was re-written fresh for `/hld:brief` | n/a |

## Deliberately not decided here

The copyright holder name on any future standalone LICENSE for this plugin is the
owner's call (`plugin.json` currently mirrors this repo's existing author field).
