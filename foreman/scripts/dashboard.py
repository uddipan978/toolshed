#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard from Foreman state.

  dashboard.py [--root .foreman] [--open]

No external assets, no network. Opens in any browser without Obsidian.
"""
from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import all_sessions, all_tasks  # noqa: E402
from board import LANES  # noqa: E402

GATES = ["G0 Intake", "G1 Plan", "G2 Critique", "G3 Develop", "G4 Test", "G5 Beta", "G6 Handoff"]

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#f6f7f9; --panel:#fff; --ink:#12151a; --muted:#5c6773; --line:#e2e6ec;
  --accent:#3b5bfd; --ok:#1a8a54; --warn:#b8720a; --bad:#c8382f; --chip:#eef1f6;
  --shadow:0 1px 2px rgba(16,20,28,.06),0 8px 24px rgba(16,20,28,.06);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0e1116; --panel:#161b22; --ink:#e8edf4; --muted:#8b98a8; --line:#242c37;
  --accent:#7c93ff; --ok:#3fbf80; --warn:#e0a33d; --bad:#f0685e; --chip:#1e2530;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.3);
}}
:root[data-theme="dark"]{
  --bg:#0e1116; --panel:#161b22; --ink:#e8edf4; --muted:#8b98a8; --line:#242c37;
  --accent:#7c93ff; --ok:#3fbf80; --warn:#e0a33d; --bad:#f0685e; --chip:#1e2530;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.3);
}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Inter,system-ui,sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1400px;margin:0 auto;padding:32px 24px 64px}
header{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;margin-bottom:4px}
h1{font-size:24px;letter-spacing:-.02em;margin:0;font-weight:650}
.sub{color:var(--muted);font-size:13px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);
  margin:36px 0 12px;font-weight:650}
.gates{display:flex;gap:6px;flex-wrap:wrap;margin-top:20px}
.gate{padding:7px 13px;border-radius:999px;background:var(--panel);border:1px solid var(--line);
  font-size:12.5px;font-weight:550;box-shadow:var(--shadow)}
.gate.done{border-color:var(--ok);color:var(--ok)}
.gate.active{border-color:var(--accent);color:var(--accent);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 14%,transparent)}
.lanes{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:14px}
.lane{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:14px;box-shadow:var(--shadow);min-width:0}
.lane h3{margin:0 0 10px;font-size:12px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--muted);display:flex;justify-content:space-between;gap:8px;font-weight:650}
.count{background:var(--chip);border-radius:999px;padding:1px 8px;color:var(--ink);
  font-size:11px;letter-spacing:0}
.card{border:1px solid var(--line);border-radius:9px;padding:10px 11px;margin-bottom:8px;
  background:var(--bg);min-width:0}
.card .id{font:11.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--accent)}
.card .t{font-size:13.5px;margin-top:3px;overflow-wrap:anywhere}
.chips{display:flex;gap:4px;flex-wrap:wrap;margin-top:7px}
.chip{font-size:10.5px;background:var(--chip);border-radius:5px;padding:2px 6px;color:var(--muted);
  font-weight:550}
.chip.warn{color:var(--warn)} .chip.bad{color:var(--bad)} .chip.ok{color:var(--ok)}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);
  border-radius:12px;overflow:hidden;box-shadow:var(--shadow)}
th,td{text-align:left;padding:10px 13px;border-bottom:1px solid var(--line);font-size:13px;
  vertical-align:middle}
th{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);font-weight:650}
tr:last-child td{border-bottom:none}
td.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.bar{height:6px;background:var(--chip);border-radius:999px;overflow:hidden;min-width:80px}
.bar span{display:block;height:100%;background:var(--accent);border-radius:999px}
.bar.warn span{background:var(--warn)} .bar.bad span{background:var(--bad)}
.state{font-size:11px;font-weight:650;padding:2px 8px;border-radius:999px;background:var(--chip)}
.state.running{color:var(--ok)} .state.quiet,.state.overdue{color:var(--warn)}
.state.stuck{color:var(--bad)} .state.done{color:var(--muted)}
.scroll{overflow-x:auto}
.empty{color:var(--muted);font-size:13px;padding:14px 0}
footer{margin-top:44px;color:var(--muted);font-size:12px}
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def pct_class(pct: float, thr: float) -> str:
    return "bad" if pct >= thr else ("warn" if pct >= thr * 0.8 else "")


def render(root: Path) -> str:
    tasks = all_tasks(root)
    sessions = all_sessions(root)
    decisions = sorted((root / "decisions").glob("D*.md")) if (root / "decisions").is_dir() else []

    done_ids = {t["id"] for t in tasks if t["status"] == "done"}
    total = len(tasks)

    # Gate progress is inferred from artefacts on disk. A gate counts as passed
    # only when EVERY task has cleared it — the project is as far along as its
    # least-advanced task, not its most.
    rank = {"backlog": 0, "planned": 0, "awaiting_human": 0, "blocked": 0,
            "in_progress": 1, "in_test": 2, "beta": 3, "done": 4}
    reqs = root / "REQUIREMENTS.md"
    reached = 0
    if reqs.exists() and reqs.read_text(errors="replace").strip() and \
            "[NEEDS CLARIFICATION]" not in reqs.read_text(errors="replace"):
        reached = 1                                   # G0 Intake cleared
    if tasks and reached >= 1:
        reached = 2                                   # G1 Plan produced tasks
        if (root / "CRITIQUE.md").exists():
            reached = 3                               # G2 Critique recorded
            floor = min(rank[t["status"]] for t in tasks)
            reached = 3 + min(floor, 3)               # G3/G4/G5 by weakest task
            if total and len(done_ids) == total:
                reached = 6                           # G6 Handoff

    p = [f"<style>{CSS}</style>",
         '<div class="wrap"><header><h1>Foreman</h1>',
         f'<span class="sub">{esc(root.parent.name)} · {len(done_ids)}/{total} tasks complete · '
         f'generated {time.strftime("%Y-%m-%d %H:%M")}</span></header>',
         '<div class="gates">']
    for i, g in enumerate(GATES):
        cls = "done" if i < reached else ("active" if i == reached else "")
        p.append(f'<div class="gate {cls}">{esc(g)}</div>')
    p.append("</div>")

    # Board
    p.append("<h2>Board</h2>")
    if not tasks:
        p.append('<div class="empty">No tasks yet — G1 has not produced a decomposition.</div>')
    else:
        p.append('<div class="lanes">')
        live = {s.get("name"): s for s in sessions}
        for key, label in LANES:
            items = [t for t in tasks if t["status"] == key]
            p.append(f'<div class="lane"><h3>{esc(label)}<span class="count">{len(items)}</span></h3>')
            for t in items:
                chips = []
                if t["parallel"]:
                    chips.append('<span class="chip">parallel</span>')
                if t["acceptance_total"]:
                    c = "ok" if t["acceptance_done"] == t["acceptance_total"] else ""
                    chips.append(f'<span class="chip {c}">AC {t["acceptance_done"]}/{t["acceptance_total"]}</span>')
                if t["needs_clarification"]:
                    chips.append('<span class="chip warn">needs clarification</span>')
                s = live.get(t["session"])
                if s and s.get("state") in ("stuck", "overdue"):
                    chips.append(f'<span class="chip bad">{esc(s["state"])}</span>')
                if t["session"]:
                    chips.append(f'<span class="chip">{esc(t["session"])}</span>')
                p.append(f'<div class="card"><div class="id">{esc(t["id"])}</div>'
                         f'<div class="t">{esc(t["title"])}</div>'
                         f'<div class="chips">{"".join(chips)}</div></div>')
            p.append("</div>")
        p.append("</div>")

    # Sessions
    p.append("<h2>Sessions</h2>")
    if not sessions:
        p.append('<div class="empty">No worker sessions have been spawned.</div>')
    else:
        p.append('<div class="scroll"><table><tr><th>Session</th><th>Agent</th><th>State</th>'
                 '<th>Context</th><th>Spend</th><th>Turns</th><th>Deadline</th></tr>')
        for s in sessions:
            pct = float(s.get("context_pct") or 0)
            thr = float(s.get("compact_pct") or 55)
            cls = pct_class(pct, thr)
            cost = float(s.get("cost_usd") or 0)
            budget = float(s.get("budget_usd") or 0)
            bcls = pct_class(100 * cost / budget if budget else 0, 100)
            dl = s.get("deadline_ts")
            dl_s = time.strftime("%H:%M", time.localtime(dl)) if dl else "—"
            if dl and time.time() > dl:
                dl_s = f'<span class="chip bad">{dl_s}</span>'
            p.append(
                f'<tr><td class="mono">{esc(s.get("name"))}</td><td>{esc(s.get("agent"))}</td>'
                f'<td><span class="state {esc(str(s.get("state","")).split(":")[0])}">{esc(s.get("state"))}</span></td>'
                f'<td><div class="bar {cls}"><span style="width:{min(pct,100):.0f}%"></span></div>'
                f'<span class="chip">{pct:.0f}% of {thr:.0f}%</span></td>'
                f'<td><div class="bar {bcls}"><span style="width:{min(100*cost/budget if budget else 0,100):.0f}%"></span></div>'
                f'<span class="chip">${cost:.2f} / ${budget:.0f}</span></td>'
                f'<td class="mono">{esc(s.get("turns"))}</td><td class="mono">{dl_s}</td></tr>')
        p.append("</table></div>")

    # Decisions
    p.append("<h2>Decisions</h2>")
    if not decisions:
        p.append('<div class="empty">No decisions recorded.</div>')
    else:
        p.append('<div class="scroll"><table><tr><th>ID</th><th>Decision</th><th>How</th></tr>')
        for d in decisions:
            txt = d.read_text(errors="replace")
            first = next((l.lstrip("# ").strip() for l in txt.splitlines() if l.startswith("# ")), d.stem)
            auto = "auto_selected: true" in txt
            how = ('<span class="chip warn">auto-selected</span>' if auto
                   else '<span class="chip ok">you decided</span>')
            p.append(f'<tr><td class="mono">{esc(d.stem)}</td><td>{esc(first)}</td><td>{how}</td></tr>')
        p.append("</table></div>")

    p.append('<footer>Task files are the source of truth. This page is derived — '
             'regenerate with <code>/foreman:board</code>.</footer></div>')
    return "\n".join(p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".foreman")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        sys.exit(f"dashboard.py: no such directory: {root}")
    body = render(root)
    out = root / "dashboard.html"
    out.write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Foreman — {html.escape(root.parent.name)}</title></head><body>{body}</body></html>\n"
    )
    print(f"wrote {out}")
    if a.open:
        subprocess.run(["open", str(out)], check=False)
