#!/usr/bin/env python3
"""Generate the Foreman mission-control dashboard: a self-contained HTML file.

  dashboard.py [--root .foreman] [--open]

Dark-first agent-ops console. No external assets, no network, no build step.
Every stat and every badge is computed from real run data — nothing here is
decorative, because a dashboard that congratulates you for nothing is noise.
"""
from __future__ import annotations

import argparse
import html
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import (  # noqa: E402
    all_sessions, all_tasks, critique_is_clear, parse_critique,
    sessions_dir, work_dir,
)
from board import LANES  # noqa: E402

GATES = [("G0", "Intake"), ("G1", "Plan"), ("G2", "Critique"), ("G3", "Develop"),
         ("G4", "Test"), ("G5", "Beta"), ("G6", "Handoff")]

CSS = r"""
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#0a0c10; --bg2:#0e1218; --panel:#12171f; --panel2:#161d27;
  --ink:#e6edf6; --dim:#8896a8; --faint:#5b6878; --line:#1e2733; --line2:#2a3542;
  --live:#2ee6a8; --info:#5b9dff; --warn:#ffb340; --bad:#ff5f56; --xp:#a97bff;
  --grid:rgba(255,255,255,.022);
  --mono:ui-monospace,"SF Mono",SFMono-Regular,"JetBrains Mono",Menlo,monospace;
  --sans:ui-sans-serif,-apple-system,"Segoe UI",Inter,system-ui,sans-serif;
}
:root[data-theme="light"]{
  --bg:#f4f6f9; --bg2:#eef1f6; --panel:#fff; --panel2:#f7f9fc;
  --ink:#0b1017; --dim:#4a5768; --faint:#6b7a8d; --line:#d8e0ea; --line2:#bcc8d6;
  --live:#00805c; --info:#1d4ed8; --warn:#8f5200; --bad:#b32d24; --xp:#6d28d9;
  --grid:rgba(0,0,0,.028);
}
@media (prefers-color-scheme:light){:root:not([data-theme="dark"]){
  --bg:#f4f6f9; --bg2:#eef1f6; --panel:#fff; --panel2:#f7f9fc;
  --ink:#0b1017; --dim:#4a5768; --faint:#6b7a8d; --line:#d8e0ea; --line2:#bcc8d6;
  --live:#00805c; --info:#1d4ed8; --warn:#8f5200; --bad:#b32d24; --xp:#6d28d9;
  --grid:rgba(0,0,0,.028);
}}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 var(--sans);
  -webkit-font-smoothing:antialiased;
  background-image:linear-gradient(var(--grid) 1px,transparent 1px),
                   linear-gradient(90deg,var(--grid) 1px,transparent 1px);
  background-size:34px 34px}
.wrap{max-width:1420px;margin:0 auto;padding:26px 22px 72px}

/* ── masthead ─────────────────────────────────────────────── */
.top{display:flex;gap:22px;align-items:stretch;flex-wrap:wrap;margin-bottom:22px}
.brand{flex:1 1 320px;min-width:0;display:flex;flex-direction:column;justify-content:center}
.mark{display:flex;align-items:center;gap:10px}
.dot{width:9px;height:9px;border-radius:50%;background:var(--live);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--live) 22%,transparent)}
.dot.idle{background:var(--faint);box-shadow:none}
h1{margin:0;font:650 21px/1.1 var(--sans);letter-spacing:-.02em}
.slug{font:11.5px/1.4 var(--mono);color:var(--faint);margin-top:5px;letter-spacing:.02em}
.ring{flex:0 0 auto;display:flex;align-items:center;gap:16px;background:var(--panel);
  border:1px solid var(--line);border-radius:14px;padding:14px 20px}
.ring svg{display:block}
.ring .pct{font:650 21px/1 var(--sans);letter-spacing:-.02em}
.ring .lbl{font:10.5px/1.4 var(--mono);color:var(--faint);text-transform:uppercase;
  letter-spacing:.1em;margin-top:4px}

/* ── stat rail ────────────────────────────────────────────── */
.rail{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:10px;margin-bottom:22px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:12px 13px;
  position:relative;overflow:hidden;min-width:0}
.stat::after{content:"";position:absolute;inset:0 auto 0 0;width:2px;background:var(--line2)}
.stat.live::after{background:var(--live)} .stat.warn::after{background:var(--warn)}
.stat.bad::after{background:var(--bad)}
.stat .k{font:10px/1.3 var(--mono);color:var(--faint);text-transform:uppercase;letter-spacing:.1em}
.stat .v{font:650 22px/1.15 var(--sans);letter-spacing:-.02em;margin-top:6px;
  font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.stat .s{font:11px/1.4 var(--mono);color:var(--dim);margin-top:3px}

/* ── gate track ───────────────────────────────────────────── */
h2{font:600 11px/1 var(--mono);text-transform:uppercase;letter-spacing:.14em;color:var(--faint);
  margin:30px 0 12px;display:flex;align-items:center;gap:10px}
h2::after{content:"";flex:1;height:1px;background:var(--line)}
.track{display:flex;align-items:flex-start;gap:0;overflow-x:auto;padding:4px 0 2px;
  background:var(--panel);border:1px solid var(--line);border-radius:12px}
.node{flex:1 1 0;min-width:104px;text-align:center;position:relative;padding:16px 6px 14px}
.node::before{content:"";position:absolute;top:29px;left:0;right:50%;height:2px;background:var(--line2)}
.node::after{content:"";position:absolute;top:29px;left:50%;right:0;height:2px;background:var(--line2)}
.node:first-child::before,.node:last-child::after{display:none}
.node.done::before,.node.done::after,.node.now::before{background:var(--live)}
.pip{position:relative;z-index:1;width:26px;height:26px;margin:0 auto 9px;border-radius:50%;
  background:var(--panel);border:2px solid var(--line2);display:grid;place-items:center;
  font:600 10px/1 var(--mono);color:var(--faint)}
.node.done .pip{background:var(--live);border-color:var(--live);color:var(--bg)}
.node.now .pip{border-color:var(--live);color:var(--live);
  box-shadow:0 0 0 4px color-mix(in srgb,var(--live) 16%,transparent)}
.node .nm{font:11.5px/1.3 var(--sans);color:var(--faint)}
.node.done .nm,.node.now .nm{color:var(--ink);font-weight:550}

/* ── board ────────────────────────────────────────────────── */
.lanes{display:flex;gap:11px;align-items:flex-start;overflow-x:auto;padding-bottom:8px;
  scrollbar-width:thin}
.lanes::-webkit-scrollbar{height:8px}
.lanes::-webkit-scrollbar-thumb{background:var(--line2);border-radius:8px}
.lane{flex:0 0 246px;background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:11px;min-width:0}
.lane.hot{border-color:color-mix(in srgb,var(--live) 40%,var(--line))}
.lane.void{flex:0 0 42px;padding:11px 6px;background:var(--bg2);border-style:dashed}
.lane.void h3{writing-mode:vertical-rl;margin:0 auto;gap:9px;justify-content:flex-start;
  height:132px;color:var(--faint);opacity:.75}
.lane.void .n{padding:1px 5px;font-size:9px;writing-mode:horizontal-tb}
.lane h3{margin:0 0 9px;font:600 10px/1 var(--mono);text-transform:uppercase;letter-spacing:.11em;
  color:var(--faint);display:flex;justify-content:space-between;align-items:center;gap:8px}
.n{background:var(--panel2);border:1px solid var(--line);border-radius:20px;padding:2px 8px;
  color:var(--dim);font-variant-numeric:tabular-nums}
.card{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:10px;
  margin-bottom:7px;min-width:0}
.card .cid{font:11px/1.3 var(--mono);color:var(--info);letter-spacing:.02em}
.card .ct{font:13px/1.4 var(--sans);margin-top:3px;overflow-wrap:anywhere}
.meter{height:3px;background:var(--line);border-radius:3px;margin-top:9px;overflow:hidden}
.meter i{display:block;height:100%;background:var(--live);border-radius:3px}
.tags{display:flex;gap:4px;flex-wrap:wrap;margin-top:8px}
.tag{display:inline-block;max-width:100%;font:10px/1.4 var(--mono);background:var(--panel);
  border:1px solid var(--line);border-radius:5px;padding:1px 6px;color:var(--dim);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;vertical-align:bottom}
.tag.p{color:var(--info);border-color:color-mix(in srgb,var(--info) 34%,var(--line))}
.tag.w{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 34%,var(--line))}
.tag.b{color:var(--bad);border-color:color-mix(in srgb,var(--bad) 40%,var(--line))}
.tag.ok{color:var(--live);border-color:color-mix(in srgb,var(--live) 34%,var(--line))}

/* ── sessions ─────────────────────────────────────────────── */
.sess{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:11px}
.sc{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;min-width:0}
.sc.alert{border-color:color-mix(in srgb,var(--bad) 45%,var(--line))}
.sc header{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:12px}
.sc .nm{font:12.5px/1.3 var(--mono);overflow-wrap:anywhere}
.sc .ag{font:10.5px/1.3 var(--mono);color:var(--faint);margin-top:2px}
.pill{font:600 10px/1 var(--mono);text-transform:uppercase;letter-spacing:.09em;
  padding:4px 8px;border-radius:20px;border:1px solid var(--line2);color:var(--dim);white-space:nowrap}
.pill.running{color:var(--live);border-color:color-mix(in srgb,var(--live) 44%,var(--line))}
.pill.quiet,.pill.overdue{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 44%,var(--line))}
.pill.stuck,.pill.stopped{color:var(--bad);border-color:color-mix(in srgb,var(--bad) 50%,var(--line))}
.gauges{display:grid;gap:9px}
.g{display:grid;grid-template-columns:56px 1fr auto;align-items:center;gap:9px}
.g .gk{font:10px/1.3 var(--mono);color:var(--faint);text-transform:uppercase;letter-spacing:.08em}
.g .gb{height:5px;background:var(--line);border-radius:4px;overflow:hidden;position:relative}
.g .gb i{display:block;height:100%;background:var(--info);border-radius:4px}
.g.warn .gb i{background:var(--warn)} .g.bad .gb i{background:var(--bad)}
.g .gv{font:11px/1.3 var(--mono);color:var(--dim);font-variant-numeric:tabular-nums;white-space:nowrap}
.thr{position:absolute;top:-2px;bottom:-2px;width:1px;background:var(--faint);opacity:.8}

/* ── badges ───────────────────────────────────────────────── */
.badges{display:grid;grid-template-columns:repeat(auto-fill,minmax(178px,1fr));gap:10px}
.badge{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:12px;
  display:flex;gap:11px;align-items:flex-start;min-width:0;opacity:.4;filter:saturate(.2)}
.badge.on{opacity:1;filter:none;border-color:color-mix(in srgb,var(--xp) 34%,var(--line))}
.badge .ic{font-size:18px;line-height:1;flex:0 0 auto}
.badge .bt{font:600 12px/1.3 var(--sans)}
.badge .bd{font:10.5px/1.45 var(--mono);color:var(--faint);margin-top:3px;overflow-wrap:anywhere}

table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);
  border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:10px 13px;border-bottom:1px solid var(--line);font-size:13px}
th{font:600 10px/1 var(--mono);text-transform:uppercase;letter-spacing:.11em;color:var(--faint)}
tr:last-child td{border-bottom:none}
td.m{font-family:var(--mono);font-size:12px;color:var(--dim)}
.scroll{overflow-x:auto}
.empty{color:var(--faint);font:12px/1.6 var(--mono);padding:14px;background:var(--panel);
  border:1px dashed var(--line2);border-radius:11px}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);
  color:var(--faint);font:11px/1.7 var(--mono)}
code{font-family:var(--mono);color:var(--dim)}
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def ring(pct: float, size: int = 62) -> str:
    """Progress ring. Stroke-dasharray on a circle — no JS, no library."""
    r = (size - 8) / 2
    c = 2 * 3.14159265 * r
    filled = max(0.0, min(1.0, pct / 100)) * c
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" aria-hidden="true">'
        f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="var(--line)" stroke-width="5"/>'
        f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="var(--live)" stroke-width="5"'
        f' stroke-linecap="round" stroke-dasharray="{filled:.2f} {c-filled:.2f}"'
        f' transform="rotate(-90 {size/2} {size/2})"/></svg>'
    )


def gauge(key: str, pct: float, label: str, threshold: float | None = None) -> str:
    cls = "bad" if pct >= 90 else ("warn" if pct >= 70 else "")
    thr = (f'<span class="thr" style="left:{min(threshold,100):.0f}%"></span>'
           if threshold is not None else "")
    return (f'<div class="g {cls}"><span class="gk">{esc(key)}</span>'
            f'<span class="gb">{thr}<i style="width:{min(pct,100):.0f}%"></i></span>'
            f'<span class="gv">{esc(label)}</span></div>')


def compute(root: Path):
    tasks = all_tasks(root)
    sessions = all_sessions(root)
    total = len(tasks)
    done = [t for t in tasks if t["status"] == "done"]
    ac_total = sum(t["acceptance_total"] for t in tasks)
    ac_done = sum(t["acceptance_done"] for t in tasks)

    spend = sum(float(s.get("cost_usd") or 0) for s in sessions)
    turns = sum(int(s.get("turns") or 0) for s in sessions)
    handovers = sum(len(list((sessions_dir(root) / s["name"]).glob("handover-*.md")))
                    for s in sessions if s.get("name"))
    reworked = sum(1 for s in sessions if int(s.get("gate_blocks") or 0) > 0)
    live = [s for s in sessions if str(s.get("state", "")).startswith(("running", "quiet"))]
    alerts = [s for s in sessions if s.get("state") in ("stuck", "overdue")]

    # XP is a real read on progress: criteria are the atoms of verified work.
    reqs = root / "REQUIREMENTS.md"
    rank = {"backlog": 0, "planned": 0, "awaiting_human": 0, "blocked": 0,
            "in_progress": 1, "in_test": 2, "beta": 3, "done": 4}
    reached = 0
    if reqs.exists() and reqs.read_text(errors="replace").strip() and \
            "[NEEDS CLARIFICATION]" not in reqs.read_text(errors="replace"):
        reached = 1
    g2_clear = critique_is_clear(parse_critique(root / "CRITIQUE.md"))
    if tasks and reached >= 1:
        reached = 2
        if g2_clear:
            reached = 3 + min(min(rank[t["status"]] for t in tasks), 3)
            if total and len(done) == total:
                reached = 6

    badges = [
        ("🎯", "Clean Sweep", "every acceptance criterion met",
         ac_total > 0 and ac_done == ac_total),
        ("⚡", "First Pass", "no worker blocked by the stop gate",
         len(sessions) > 0 and reworked == 0),
        ("🧠", "No Handover", "no session outgrew its context",
         len(sessions) > 0 and handovers == 0),
        ("💰", "Under Budget", "every session finished under half its cap",
         len(sessions) > 0 and all(
             float(s.get("cost_usd") or 0) <= 0.5 * float(s.get("budget_usd") or 1)
             for s in sessions if s.get("state") == "done")
         and any(s.get("state") == "done" for s in sessions)),
        ("🛡️", "Critiqued", "every G2 finding fixed or refuted",
         g2_clear),
        ("🚢", "Shipped", "all gates cleared, handed to the human",
         reached >= 6),
    ]
    return dict(tasks=tasks, sessions=sessions, total=total, done=done, ac_total=ac_total,
                ac_done=ac_done, spend=spend, turns=turns, handovers=handovers,
                reworked=reworked, live=live, alerts=alerts,
                reached=reached, badges=badges)


def render(root: Path, static: bool = False) -> str:
    """static=True produces the tracked board.html: no timestamp, no live session
    state. That makes the file deterministic, so it only shows a diff when task
    state actually changed — which is the only diff a reviewer wants to see."""
    d = compute(root)
    tasks, sessions = d["tasks"], d["sessions"]
    total, done = d["total"], d["done"]
    pct = (100.0 * len(done) / total) if total else 0.0
    live_now = bool(d["live"])

    p = [f"<style>{CSS}</style>", '<div class="wrap">']

    # masthead
    p.append('<div class="top"><div class="brand"><div class="mark">'
             f'<span class="dot{"" if live_now and not static else " idle"}"></span><h1>FOREMAN</h1></div>'
             f'<div class="slug">{esc(root.parent.name)}'
             + ('' if static else
                f' · {"● " + str(len(d["live"])) + " session(s) live" if live_now else "idle"}'
                f' · {time.strftime("%Y-%m-%d %H:%M")}')
             + '</div></div>')
    p.append(f'<div class="ring">{ring(pct)}<div><div class="pct">{pct:.0f}%</div>'
             f'<div class="lbl">{len(done)}/{total} tasks</div></div></div></div>')

    # stat rail
    tiles = [
        ("live" if d["ac_total"] and d["ac_done"] == d["ac_total"] else "", "Criteria met",
         f'{d["ac_done"]}/{d["ac_total"]}', "verified, not claimed"),
        ("", "Tasks", f'{len(done)}/{total}', "shipped / planned"),
    ]
    if not static:
        tiles += [
            ("", "Sessions", f'{len(sessions)}', f'{len(d["live"])} live'),
            ("", "Turns", f'{d["turns"]:,}', "across all workers"),
            ("", "Spend", f'${d["spend"]:.2f}', "settled runs only"),
            ("warn" if d["handovers"] else "", "Handovers", f'{d["handovers"]}',
             "context compactions"),
            ("bad" if d["alerts"] else "", "Alerts", f'{len(d["alerts"])}',
             "stuck or overdue" if d["alerts"] else "all clear"),
        ]
    p.append('<div class="rail">')
    for cls, k, v, s in tiles:
        p.append(f'<div class="stat {cls}"><div class="k">{esc(k)}</div>'
                 f'<div class="v">{esc(v)}</div><div class="s">{esc(s)}</div></div>')
    p.append("</div>")

    # gate track
    p.append("<h2>Lifecycle</h2><div class=\"track\">")
    for i, (code, name) in enumerate(GATES):
        cls = "done" if i < d["reached"] else ("now" if i == d["reached"] else "")
        mark = "✓" if i < d["reached"] else code
        p.append(f'<div class="node {cls}"><div class="pip">{mark}</div>'
                 f'<div class="nm">{esc(name)}</div></div>')
    p.append("</div>")

    # board
    p.append("<h2>Board</h2>")
    if not tasks:
        p.append('<div class="empty">no tasks yet — G1 has not produced a decomposition</div>')
    else:
        livemap = {s.get("name"): s for s in sessions}
        p.append('<div class="lanes">')
        for key, label in LANES:
            items = [t for t in tasks if t["status"] == key]
            if not items:
                # Collapsed rail: keeps the pipeline legible without eating width.
                p.append(f'<div class="lane void" title="{esc(label)} — empty">'
                         f'<h3>{esc(label)}<span class="n">0</span></h3></div>')
                continue
            hot = " hot" if key == "in_progress" else ""
            p.append(f'<div class="lane{hot}"><h3>{esc(label)}<span class="n">{len(items)}</span></h3>')
            for t in items:
                tg = []
                if t["parallel"]:
                    tg.append('<span class="tag p">// parallel</span>')
                if t["needs_clarification"]:
                    tg.append('<span class="tag w">needs clarification</span>')
                s = None if static else livemap.get(t["session"])
                if s and s.get("state") in ("stuck", "overdue"):
                    tg.append(f'<span class="tag b">{esc(s["state"])}</span>')
                if t["session"]:
                    tg.append(f'<span class="tag">{esc(t["session"])}</span>')
                if t["estimate"]:
                    tg.append(f'<span class="tag">{esc(t["estimate"])}</span>')
                bar = ""
                if t["acceptance_total"]:
                    w = 100 * t["acceptance_done"] / t["acceptance_total"]
                    cl = "ok" if w == 100 else ""
                    tg.insert(0, f'<span class="tag {cl}">AC {t["acceptance_done"]}/{t["acceptance_total"]}</span>')
                    bar = f'<div class="meter"><i style="width:{w:.0f}%"></i></div>'
                p.append(f'<div class="card"><div class="cid">{esc(t["id"])}</div>'
                         f'<div class="ct">{esc(t["title"])}</div>{bar}'
                         f'<div class="tags">{"".join(tg)}</div></div>')
            p.append("</div>")
        p.append("</div>")

    # sessions
    # Sessions are live, machine-local state — excluded from the tracked board.
    if not static:
        p.append("<h2>Sessions</h2>")
        if not sessions:
            p.append('<div class="empty">no worker sessions spawned</div>')
        else:
            p.append('<div class="sess">')
            for s in sessions:
                state = str(s.get("state") or "unknown")
                base = state.split(":")[0]
                alert = " alert" if base in ("stuck", "overdue") else ""
                cpct = float(s.get("context_pct") or 0)
                thr = float(s.get("compact_pct") or 55)
                cost = float(s.get("cost_usd") or 0)
                budget = float(s.get("budget_usd") or 0)
                turns = int(s.get("turns") or 0)
                mt = int(s.get("max_turns") or 0)
                dl = s.get("deadline_ts")
                start = s.get("started_at")
                settled = base in ("done", "stopped", "unknown")
                dl_txt = "—"
                dl_pct = 0.0
                if settled:
                    dl = None          # a finished session is not "overdue"
                if dl and start:
                    span = max(dl - start, 1)
                    dl_pct = 100.0 * (time.time() - start) / span
                    left = int((dl - time.time()) // 60)
                    dl_txt = f"{left}m left" if left > 0 else f"{-left}m over"
                p.append(f'<div class="sc{alert}"><header><div><div class="nm">{esc(s.get("name"))}</div>'
                         f'<div class="ag">{esc(s.get("agent"))} · {esc(s.get("model") or "—")}</div></div>'
                         f'<span class="pill {esc(base)}">{esc(state)}</span></header><div class="gauges">')
                p.append(gauge("ctx", cpct, f"{cpct:.0f}% / {thr:.0f}%", threshold=thr))
                if budget:
                    p.append(gauge("spend", 100 * cost / budget, f"${cost:.2f} / ${budget:.0f}"))
                if mt:
                    p.append(gauge("turns", 0 if settled else 100 * turns / mt, f"{turns} / {mt}"))
                if dl:
                    p.append(gauge("time", dl_pct, dl_txt))
                if settled:
                    took = ""
                    if start and s.get("updated_at"):
                        took = f' in {int((int(s["updated_at"]) - int(start)) // 60)}m'
                    p.append(f'<div class="g"><span class="gk">ran</span>'
                             f'<span class="gv" style="grid-column:2/4">{esc(turns)} turns{esc(took)}</span></div>')
                p.append("</div></div>")
            p.append("</div>")

    # badges
    session_derived = {"First Pass", "No Handover", "Under Budget"}
    badges = [b for b in d["badges"] if not (static and b[1] in session_derived)]
    p.append("<h2>Run badges</h2><div class=\"badges\">")
    for icon, title, desc, earned in badges:
        p.append(f'<div class="badge{" on" if earned else ""}"><span class="ic">{icon}</span>'
                 f'<div><div class="bt">{esc(title)}</div><div class="bd">{esc(desc)}</div></div></div>')
    p.append("</div>")

    # decisions
    dec = sorted((root / "decisions").glob("D*.md")) if (root / "decisions").is_dir() else []
    p.append("<h2>Decision ledger</h2>")
    if not dec:
        p.append('<div class="empty">no decisions recorded</div>')
    else:
        p.append('<div class="scroll"><table><tr><th>ID</th><th>Decision</th><th>Made by</th></tr>')
        for f in dec:
            txt = f.read_text(errors="replace")
            first = next((l.lstrip("# ").strip() for l in txt.splitlines() if l.startswith("# ")), f.stem)
            auto = "auto_selected: true" in txt
            who = ('<span class="tag w">auto-selected · you were away</span>' if auto
                   else '<span class="tag ok">you decided</span>')
            p.append(f'<tr><td class="m">{esc(f.stem)}</td><td>{esc(first)}</td><td>{who}</td></tr>')
        p.append("</table></div>")

    p.append('<footer>task files are the source of truth · this page is derived · '
             'regenerate with <code>/foreman:board</code></footer></div>')
    return "\n".join(p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".foreman")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--static", action="store_true",
                    help="write the tracked board.html: no timestamp, no live session state")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        sys.exit(f"dashboard.py: no such directory: {root}")

    if a.static:
        out = root / "board.html"          # tracked, deterministic
    else:
        out = work_dir(root) / "dashboard.html"   # scratchpad, live
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Foreman — {html.escape(root.parent.name)}</title></head><body>"
        f"{render(root, static=a.static)}</body></html>\n")
    print(f"wrote {out}")
    if a.open:
        subprocess.run(["open", str(out)], check=False)
