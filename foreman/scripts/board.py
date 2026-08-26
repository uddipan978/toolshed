#!/usr/bin/env python3
"""Generate the Obsidian Kanban board from Foreman task files.

  board.py [--root .foreman]

The board is a DERIVED view. Task files are the source of truth, so this file can
be deleted and regenerated at any time. Cards are wikilinks rather than inline
text, which keeps the board thin and stops the Obsidian plugin and Foreman from
fighting over the same content.

Format notes, verified byte-exact against a real board written by the plugin:
  - frontmatter is --- / blank / kanban-plugin: board / blank / ---
  - lanes are level-2 headings, one blank line before the first card
  - two blank lines between the last card of a lane and the next heading
  - the settings block emits only {"kanban-plugin":"board"}; the plugin adds
    list-collapse itself, and a hand-written array of the wrong length misrenders
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import all_sessions, all_tasks  # noqa: E402

LANES = [
    ("backlog", "Backlog"),
    ("planned", "Planned"),
    ("in_progress", "In Progress"),
    ("in_test", "In Test"),
    ("beta", "Beta"),
    ("awaiting_human", "Awaiting Human"),
    ("done", "Done"),
    ("blocked", "Blocked"),
]


def card(task: dict, live: dict[str, dict]) -> str:
    checked = "x" if task["status"] == "done" else " "
    bits = [f"- [{checked}] [[{task['path'].stem}]]"]

    tags = []
    if task["parallel"]:
        tags.append("#parallel")
    if task["needs_clarification"]:
        tags.append("#needs-clarification")
    if task["acceptance_total"]:
        tags.append(f"#ac-{task['acceptance_done']}of{task['acceptance_total']}")

    sess = live.get(task["session"])
    if sess:
        state = sess.get("state", "")
        if state in ("stuck", "overdue"):
            tags.append(f"#{state}")
        pct = sess.get("context_pct")
        if isinstance(pct, (int, float)) and pct >= sess.get("compact_pct", 55):
            tags.append("#compacting")

    if tags:
        bits.append("  " + " ".join(tags))
    return "\n".join(bits)


def render(root: Path) -> str:
    tasks = all_tasks(root)
    live = {s["name"]: s for s in all_sessions(root) if s.get("name")}

    out = ["---", "", "kanban-plugin: board", "", "---", ""]
    for key, label in LANES:
        out.append(f"## {label}")
        out.append("")
        for t in [t for t in tasks if t["status"] == key]:
            out.append(card(t, live))
        out.append("")
        out.append("")

    out.append('%% kanban:settings')
    out.append("```")
    out.append('{"kanban-plugin":"board"}')
    out.append("```")
    out.append("%%")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".foreman")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        sys.exit(f"board.py: no such directory: {root}")
    target = root / "board.md"
    target.write_text(render(root))
    n = len(all_tasks(root))
    print(f"wrote {target} ({n} task{'s' if n != 1 else ''})")
