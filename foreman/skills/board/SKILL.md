---
name: board
description: Regenerates the Foreman Kanban board and HTML dashboard from task files and reports current status. Use when the user asks for Foreman status, progress, the board, or the dashboard, or after any batch of task status changes.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)
---

# Board and dashboard

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/board.py --root .foreman
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard.py --root .foreman
```

Both are **derived from the task files**. Never hand-edit either one — an edit to
`board.md` is lost on the next regeneration, and the Obsidian plugin rewrites the file
anyway when it opens it.

`board.md` opens as a drag-and-drop board in Obsidian. `dashboard.html` opens in any
browser with no plugin, and carries the session gauges the board cannot show.

## Reporting status

Read the task files and the session `status.json` files, then tell the user:

- Which gate the run is at, and what it is waiting on.
- Tasks done / total, and anything blocked with the reason.
- Live sessions: context %, spend against budget, time against deadline.
- Any task whose acceptance boxes are unchecked while its session reads done — that is a
  reconciliation gap, and it is the most common one.
- Decisions that were auto-selected while the user was away.

Lead with what needs their attention. If nothing does, say so in one line rather than
narrating the whole board.
