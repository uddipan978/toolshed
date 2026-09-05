---
name: board
description: Regenerates the Foreman Kanban board and HTML dashboard from task files and reports current status. Use when the user asks for Foreman status, progress, the board, or the dashboard, or after any batch of task status changes.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(python3 ${GROK_PLUGIN_ROOT}/scripts/*)
---

# Board and dashboard

```bash
PLUGIN_ROOT="${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"
python3 "$PLUGIN_ROOT/scripts/refresh.py" --root .foreman
```

One command regenerates all four views:

| File | Tracked | Who it is for |
|---|---|---|
| `STATUS.md` | yes | **the default.** Plain markdown — renders in a repo browser, an editor, anywhere |
| `board.html` | yes | a teammate who cloned and wants the visual board, no plugin needed |
| `board.md` | yes | you, in Obsidian — drag-and-drop |
| `work/dashboard.html` | no | the live ops console: gauges, spend, alerts; click a task or session card for a rendered chat transcript with expandable tool input/output |

To watch a live worker without attaching a TUI:

```bash
python3 "$PLUGIN_ROOT/scripts/dashboard.py" --root .foreman --open --watch 8
```

The page reloads from disk every 8 seconds. Click the in-flight card.

All four are **derived from the task files**. Never hand-edit any of them — an edit to
`board.md` is lost on the next regeneration, and the Obsidian plugin rewrites that file
anyway when it opens it.

`board.html` is deliberately deterministic — no timestamp, no live session state — so it
only shows a diff when task state actually changed. `work/dashboard.html` carries the
volatile detail and never ships.

## Reporting status

Read the task files and the session `status.json` files, then tell the user:

- Which gate the run is at, and what it is waiting on.
- Active sprint/MVP: committed, delivered, added/removed scope and remaining G4/G5.
- The current preview/demo path, which data is mocked, and what is wired to real services.
- Worker admission: RAM/CPU pressure, paused capacity and held queue jobs.
- Pending durable events and the age of the last supervisor heartbeat/view refresh.
- Tasks done / total, and anything blocked with the reason.
- Live sessions: context %, spend against budget, time against deadline.
- Dirty sessions: uncommitted paths, especially any stopped worker requiring `SALVAGE`.
- Any task whose acceptance boxes are unchecked while its session reads done — that is a
  reconciliation gap, and it is the most common one.
- Decisions that were auto-selected while the user was away.

Lead with what needs their attention. If nothing does, say so in one line rather than
narrating the whole board.
