#!/usr/bin/env python3
"""Generate the Foreman mission-control dashboard: a self-contained HTML file.

  dashboard.py [--root .foreman] [--open]

Dark-first agent-ops console. No external assets, no network, no build step.
Every stat and every badge is computed from real run data — nothing here is
decorative, because a dashboard that congratulates you for nothing is noise.
Live dashboard: click a session or in-flight card to read stream.jsonl as a
chat transcript with rendered Markdown and expandable tool/code viewers.
`--watch N` rewrites the file every N seconds so a browser refresh stays current.
"""
from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import (  # noqa: E402
    all_sessions, all_tasks, critique_is_clear, parse_critique,
    parse_stream_activity, sessions_dir, work_dir,
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
.card[data-open-session],.sc[data-open-session]{cursor:pointer}
.card[data-open-session]:hover,.sc[data-open-session]:hover{
  border-color:color-mix(in srgb,var(--info) 45%,var(--line))}
.card[data-open-session]:focus-visible,.sc[data-open-session]:focus-visible{
  outline:2px solid var(--info);outline-offset:2px}
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
.pill.ready{color:var(--live);border-color:color-mix(in srgb,var(--live) 44%,var(--line))}
.pill.quiet,.pill.overdue,.pill.review{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 44%,var(--line))}
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

/* ── session transcript (stream.jsonl) ────────────────────── */
body.feed-lock{overflow:hidden}
.feed{position:fixed;inset:0;z-index:20;pointer-events:none}
.feed.open{pointer-events:auto}
.feed-scrim{position:absolute;inset:0;background:rgba(3,5,8,.60);opacity:0;
  backdrop-filter:blur(2px);transition:opacity .18s ease}
.feed.open .feed-scrim{opacity:1}
.feed-pane{position:absolute;top:0;right:0;bottom:0;width:min(860px,100%);background:var(--bg);
  border-left:1px solid var(--line2);transform:translateX(100%);transition:transform .2s ease;
  display:flex;flex-direction:column;box-shadow:-30px 0 70px rgba(0,0,0,.38)}
.feed.open .feed-pane{transform:none}
.feed-pane>header{display:flex;align-items:center;justify-content:space-between;gap:18px;
  padding:15px 18px;background:color-mix(in srgb,var(--bg) 94%,transparent);
  border-bottom:1px solid var(--line);flex:0 0 auto}
.feed-heading{min-width:0}
.feed-eyebrow{display:block;font:600 9.5px/1.2 var(--mono);letter-spacing:.12em;
  text-transform:uppercase;color:var(--info);margin-bottom:4px}
.feed-pane h3{margin:0;font:650 16px/1.25 var(--sans);letter-spacing:-.02em;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.feed-meta{font:10.5px/1.45 var(--mono);color:var(--dim);margin-top:4px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.feed-actions{display:flex;align-items:center;gap:6px;flex:0 0 auto}
.feed-btn{min-height:44px;background:transparent;border:1px solid var(--line);color:var(--dim);
  border-radius:9px;padding:0 11px;font:11px/1 var(--mono);cursor:pointer;white-space:nowrap;
  touch-action:manipulation}
.feed-btn:hover{color:var(--ink);border-color:var(--line2);background:var(--panel)}
.feed-btn:active{background:var(--panel2)}
.feed-btn:focus-visible,.code-action:focus-visible,.tool-summary:focus-visible{
  outline:2px solid var(--info);outline-offset:2px}
.feed-note{margin:0;padding:7px 18px;font:10.5px/1.45 var(--mono);color:var(--dim);
  background:var(--bg2);border-bottom:1px solid var(--line);flex:0 0 auto}
.feed-body{flex:1;overflow:auto;overscroll-behavior:contain;padding:24px 24px 42px;
  scroll-behavior:smooth}
.feed-panel{max-width:780px;margin:0 auto}
.feed-list{list-style:none;margin:0;padding:0}

/* Transcript rhythm: assistant messages read as prose; tool calls recede until opened. */
.chat-row{display:grid;grid-template-columns:32px minmax(0,1fr);gap:11px;position:relative;
  margin:0 0 18px}
.chat-row::before{content:"";position:absolute;top:32px;bottom:-18px;left:15px;width:1px;
  background:var(--line)}
.chat-row:last-child::before{display:none}
.chat-avatar{position:relative;z-index:1;width:32px;height:32px;border-radius:9px;
  display:grid;place-items:center;background:var(--panel2);border:1px solid var(--line2);
  color:var(--ink);font:650 11px/1 var(--mono)}
.chat-main{min-width:0}
.chat-label{font:600 10px/1.3 var(--mono);letter-spacing:.08em;text-transform:uppercase;
  color:var(--dim);margin:1px 0 6px}
.message-bubble{background:var(--panel);border:1px solid var(--line);border-radius:4px 12px 12px 12px;
  padding:14px 16px;box-shadow:0 6px 22px rgba(0,0,0,.08)}

/* Safe, server-rendered Markdown. Raw HTML is always escaped by the renderer. */
.md{font:14px/1.68 var(--sans);color:var(--ink);overflow-wrap:anywhere}
.md>:first-child{margin-top:0}.md>:last-child{margin-bottom:0}
.md p{margin:0 0 11px}.md h1,.md h2,.md h3,.md h4,.md h5,.md h6{
  color:var(--ink);font-family:var(--sans);font-weight:650;line-height:1.3;
  text-transform:none;letter-spacing:-.015em;
  display:block;margin:19px 0 8px}.md h1::after,.md h2::after{display:none}
.md h1{font-size:20px}.md h2{font-size:17px}.md h3{font-size:15px}.md h4,.md h5,.md h6{font-size:14px}
.md ul,.md ol{margin:8px 0 12px;padding-left:24px}.md li{margin:4px 0;padding-left:2px}
.md li::marker{color:var(--faint)}
.md blockquote{margin:12px 0;padding:2px 0 2px 13px;border-left:3px solid var(--info);
  color:var(--dim)}
.md a{color:var(--info);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--info) 45%,transparent)}
.md a:hover{border-color:var(--info)}
.md code.md-inline{padding:2px 5px;border:1px solid var(--line);border-radius:5px;
  background:var(--bg2);color:var(--ink);font-size:.88em}
.md hr{height:1px;border:0;background:var(--line);margin:17px 0}
.md-table-wrap{overflow:auto;margin:12px 0;border:1px solid var(--line);border-radius:9px}
.md table{border:0;border-radius:0;background:transparent;min-width:100%}
.md th,.md td{padding:8px 10px;font-size:12.5px;vertical-align:top}
.md th{font-size:9.5px}.md-url{color:var(--faint);font-family:var(--mono);font-size:.9em}
.md-task{list-style:none;margin-left:-20px}.md-check{display:inline-block;width:16px;color:var(--faint)}
.md-check.on{color:var(--live)}

/* Tool calls and code/script viewers. */
.chat-row.tool-event .chat-avatar{color:var(--info);background:color-mix(in srgb,var(--info) 9%,var(--panel2))}
.tool-card{background:var(--panel);border:1px solid var(--line);border-radius:11px;overflow:hidden}
.tool-card[open]{border-color:var(--line2)}
.tool-card.bad{border-color:color-mix(in srgb,var(--bad) 48%,var(--line))}
.tool-summary{min-height:52px;display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;
  align-items:center;gap:10px;padding:8px 12px;cursor:pointer;list-style:none;user-select:none;
  touch-action:manipulation}
.tool-summary::-webkit-details-marker{display:none}
.tool-summary:active{background:var(--panel2)}
.tool-glyph{width:27px;height:27px;border-radius:7px;display:grid;place-items:center;
  color:var(--info);background:color-mix(in srgb,var(--info) 10%,var(--bg2));
  font:650 10px/1 var(--mono)}
.tool-copy{min-width:0;display:flex;align-items:baseline;gap:7px}.tool-name{font:650 10px/1.3 var(--mono);letter-spacing:.08em;
  text-transform:uppercase;color:var(--info)}
.tool-title{font:12.5px/1.4 var(--sans);color:var(--ink);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;margin-top:2px;min-width:0}
.tool-state{display:flex;align-items:center;gap:6px;color:var(--faint);font:10px/1 var(--mono)}
.tool-state::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--faint)}
.tool-card.ok .tool-state::before{background:var(--live)}
.tool-card.ok .tool-state{color:var(--live)}
.tool-card.bad .tool-state::before{background:var(--bad)}
.tool-card.bad .tool-state{color:var(--bad)}
.tool-summary::after{content:"›";color:var(--faint);font:18px/1 var(--mono);transition:transform .15s}
.tool-card[open]>.tool-summary::after{transform:rotate(90deg)}
.tool-body{border-top:1px solid var(--line);padding:10px;background:var(--bg2);display:grid;gap:10px}
.code-viewer{min-width:0;border:1px solid var(--line);border-radius:9px;overflow:hidden;background:#080b10}
:root[data-theme="light"] .code-viewer{background:#f3f6fa}
@media (prefers-color-scheme:light){:root:not([data-theme="dark"]) .code-viewer{background:#f3f6fa}}
.code-head{min-height:38px;display:flex;align-items:center;gap:8px;padding:0 8px 0 11px;
  background:var(--panel);border-bottom:1px solid var(--line)}
.code-label{font:600 9.5px/1 var(--mono);text-transform:uppercase;letter-spacing:.1em;color:var(--dim)}
.code-lang{font:9.5px/1 var(--mono);color:var(--dim)}
.code-actions{margin-left:auto;display:flex;gap:3px}
.code-action{min-height:44px;border:0;background:transparent;color:var(--dim);border-radius:6px;
  padding:0 8px;font:9.5px/1 var(--mono);cursor:pointer;touch-action:manipulation}
.code-action:hover{color:var(--ink);background:var(--panel2)}
.code-action:active{background:var(--line)}
.code-viewer pre{margin:0;padding:12px 0;max-height:390px;overflow:auto;tab-size:2;
  font:11.5px/1.58 var(--mono);color:var(--ink);white-space:pre}
.code-viewer code{display:block;min-width:max-content;color:inherit;font:inherit}
.code-viewer.wrap-code pre{white-space:pre-wrap;overflow-wrap:anywhere}
.code-viewer.wrap-code code{min-width:0}
.code-line{display:block;min-height:1.58em;padding:0 14px 0 52px;position:relative}
.code-line::before{counter-increment:line;content:counter(line);position:absolute;left:0;width:38px;
  padding-right:10px;text-align:right;color:var(--faint);border-right:1px solid var(--line);user-select:none}
.code-viewer pre{counter-reset:line}
.code-viewer.terminal pre{padding:12px 14px;color:#b9c7d8}
:root[data-theme="light"] .code-viewer.terminal pre{color:#263446}
@media (prefers-color-scheme:light){:root:not([data-theme="dark"]) .code-viewer.terminal pre{color:#263446}}
.code-viewer.terminal code{min-width:max-content}
.md>.code-viewer{margin:13px 0}

.event-line{display:flex;align-items:flex-start;gap:9px;margin:12px 0 18px 43px;padding:9px 11px;
  border:1px dashed var(--line2);border-radius:9px;color:var(--dim);font:11px/1.5 var(--mono)}
.event-mark{width:7px;height:7px;margin:5px 3px 0 1px;background:var(--warn);transform:rotate(45deg);
  flex:0 0 auto}
.result-event .chat-avatar{color:var(--xp);background:color-mix(in srgb,var(--xp) 9%,var(--panel2))}
.result-card{padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
.result-card.ok{border-color:color-mix(in srgb,var(--live) 34%,var(--line))}
.result-card.bad{border-color:color-mix(in srgb,var(--bad) 44%,var(--line))}
.result-title{font:600 11px/1.4 var(--mono);color:var(--dim)}
.result-card.ok .result-title{color:var(--live)}.result-card.bad .result-title{color:var(--bad)}
.result-card .md{margin-top:8px;font-size:12.5px;color:var(--dim)}

@media (max-width:700px){
  .feed-pane{width:100%;border-left:0}.feed-pane>header{padding:11px 12px;gap:10px}
  .feed-actions .tools-toggle{display:none}.feed-btn{min-width:44px;padding:0 9px}
  .feed-body{padding:18px 12px 32px}.chat-row{grid-template-columns:28px minmax(0,1fr);gap:8px}
  .chat-avatar{width:28px;height:28px}.chat-row::before{left:13px;top:28px}
  .message-bubble{padding:12px}.event-line{margin-left:36px}.tool-state span{display:none}
}
@media (prefers-reduced-motion:reduce){.feed-scrim,.feed-pane,.tool-summary::after{transition:none}.feed-body{scroll-behavior:auto}}
"""

JS = r"""
(function(){
  var feed = document.getElementById("feed");
  if (!feed) return;
  var title = document.getElementById("feed-title");
  var meta = document.getElementById("feed-meta");
  var empty = document.getElementById("feed-empty");
  var body = feed.querySelector(".feed-body");
  var closeButton = feed.querySelector("button[data-close-feed]");
  var toolsButton = feed.querySelector("[data-toggle-tools]");
  var currentPanel = null;
  var lastFocus = null;

  function updateToolsButton(){
    if (!toolsButton || !currentPanel) return;
    var tools = currentPanel.querySelectorAll("details.tool-card");
    toolsButton.hidden = tools.length === 0;
    if (!tools.length) return;
    var allOpen = true;
    for (var i = 0; i < tools.length; i++) if (!tools[i].open) allOpen = false;
    toolsButton.textContent = allOpen ? "Collapse tools" : "Expand tools";
  }

  function openSession(name){
    if (!name) return;
    var panels = document.querySelectorAll(".feed-panel");
    currentPanel = null;
    for (var i = 0; i < panels.length; i++) {
      var on = panels[i].getAttribute("data-session") === name;
      panels[i].hidden = !on;
      if (on) currentPanel = panels[i];
    }
    lastFocus = document.activeElement;
    title.textContent = currentPanel ? (currentPanel.getAttribute("data-title") || name) : name;
    meta.textContent = currentPanel ? (currentPanel.getAttribute("data-summary") || "") : "";
    empty.hidden = !!currentPanel;
    feed.classList.add("open");
    feed.setAttribute("aria-hidden", "false");
    feed.removeAttribute("inert");
    document.body.classList.add("feed-lock");
    updateToolsButton();
    requestAnimationFrame(function(){
      if (body) {
        var live = currentPanel && currentPanel.getAttribute("data-live") === "true";
        body.scrollTop = live ? body.scrollHeight : 0;
      }
      if (closeButton) closeButton.focus({preventScroll:true});
    });
    try { history.replaceState(null, "", "#session=" + encodeURIComponent(name)); }
    catch (e) {}
  }
  function close(){
    feed.classList.remove("open");
    feed.setAttribute("aria-hidden", "true");
    feed.setAttribute("inert", "");
    document.body.classList.remove("feed-lock");
    try {
      if (location.hash.indexOf("#session=") === 0)
        history.replaceState(null, "", location.pathname + location.search);
    } catch (e) {}
    if (lastFocus && lastFocus.focus) lastFocus.focus({preventScroll:true});
  }

  function copyText(value, button){
    function done(){
      var old = button.textContent;
      button.textContent = "Copied";
      setTimeout(function(){ button.textContent = old; }, 1200);
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(value).then(done, function(){ fallback(); });
      return;
    }
    fallback();
    function fallback(){
      var area = document.createElement("textarea");
      area.value = value; area.setAttribute("readonly", "");
      area.style.position = "fixed"; area.style.opacity = "0";
      document.body.appendChild(area); area.select();
      try { document.execCommand("copy"); done(); } catch (e) {}
      document.body.removeChild(area);
    }
  }

  document.addEventListener("click", function(e){
    var closeHit = e.target.closest("[data-close-feed]");
    if (closeHit) { close(); return; }
    var copy = e.target.closest("[data-copy-code]");
    if (copy) {
      var viewer = copy.closest(".code-viewer");
      var code = viewer && viewer.querySelector("code");
      if (code) {
        var lines = code.querySelectorAll(".code-line");
        var value = code.textContent;
        if (lines.length) {
          var values = [];
          for (var i = 0; i < lines.length; i++) values.push(lines[i].textContent);
          value = values.join("\n");
        }
        copyText(value.replace(/\n$/, ""), copy);
      }
      return;
    }
    var wrap = e.target.closest("[data-wrap-code]");
    if (wrap) {
      var wrapViewer = wrap.closest(".code-viewer");
      var on = wrapViewer.classList.toggle("wrap-code");
      wrap.setAttribute("aria-pressed", on ? "true" : "false");
      wrap.textContent = on ? "Unwrap" : "Wrap";
      return;
    }
    var latest = e.target.closest("[data-feed-latest]");
    if (latest) { if (body) body.scrollTop = body.scrollHeight; return; }
    var toggleTools = e.target.closest("[data-toggle-tools]");
    if (toggleTools && currentPanel) {
      var tools = currentPanel.querySelectorAll("details.tool-card");
      var open = false;
      for (var j = 0; j < tools.length; j++) if (!tools[j].open) open = true;
      for (var k = 0; k < tools.length; k++) tools[k].open = open;
      updateToolsButton();
      return;
    }
    var hit = e.target.closest("[data-open-session]");
    if (hit) {
      var name = hit.getAttribute("data-open-session");
      if (name) { e.preventDefault(); openSession(name); }
    }
  });
  document.addEventListener("keydown", function(e){
    if (e.key === "Escape" && feed.classList.contains("open")) { close(); return; }
    if (e.key === "Tab" && feed.classList.contains("open")) {
      var candidates = feed.querySelectorAll('button:not([hidden]),summary,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])');
      var focusable = [];
      for (var f = 0; f < candidates.length; f++) {
        if (!candidates[f].closest("[hidden]") && candidates[f].offsetParent !== null)
          focusable.push(candidates[f]);
      }
      if (focusable.length) {
        var first = focusable[0], last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    if (e.key === "Enter" || e.key === " ") {
      var el = document.activeElement;
      if (el && el.getAttribute && el.getAttribute("data-open-session")) {
        e.preventDefault();
        openSession(el.getAttribute("data-open-session"));
      }
    }
  });
  feed.addEventListener("toggle", updateToolsButton, true);
  var m = location.hash.match(/session=([^&]+)/);
  if (m) openSession(decodeURIComponent(m[1]));
})();
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _safe_href(value: str) -> str | None:
    value = html.unescape((value or "").strip())
    if not value or re.search(r"[\x00-\x20]", value):
        return None
    low = value.lower()
    if low.startswith(("https://", "http://", "mailto:", "#", "/", "./", "../")):
        return value
    return None


def _inline_markdown(value: str) -> str:
    """Render a deliberately safe Markdown inline subset.

    Raw HTML is escaped. Links are restricted to web/mail/relative targets, so
    an agent transcript cannot smuggle executable markup into the dashboard.
    """
    tokens: list[str] = []

    def stash(markup: str) -> str:
        key = f"\ue000{len(tokens)}\ue001"
        tokens.append(markup)
        return key

    def code_repl(match: re.Match) -> str:
        return stash(f'<code class="md-inline">{esc(match.group(1))}</code>')

    value = re.sub(r"`([^`\n]+)`", code_repl, value)

    def link_repl(match: re.Match) -> str:
        label, target = match.group(1), match.group(2)
        href = _safe_href(target)
        if href is None:
            return stash(f'{esc(label)} <span class="md-url">{esc(target)}</span>')
        external = href.lower().startswith(("http://", "https://"))
        attrs = ' target="_blank" rel="noopener noreferrer"' if external else ""
        return stash(f'<a href="{esc(href)}"{attrs}>{esc(label)}</a>')

    value = re.sub(r"(?<!!)\[([^\]\n]+)\]\(([^)\s]+)\)", link_repl, value)

    def auto_link_repl(match: re.Match) -> str:
        href = _safe_href(match.group(1))
        if href is None:
            return match.group(0)
        return stash(
            f'<a href="{esc(href)}" target="_blank" rel="noopener noreferrer">'
            f'{esc(href)}</a>'
        )

    value = re.sub(r"<(https?://[^ >]+)>", auto_link_repl, value)
    value = html.escape(value, quote=False)
    value = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"__([^_\n]+)__", r"<strong>\1</strong>", value)
    value = re.sub(r"~~([^~\n]+)~~", r"<del>\1</del>", value)
    value = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", value)
    value = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<em>\1</em>", value)
    value = value.replace("\n", "<br>")
    for i, markup in enumerate(tokens):
        value = value.replace(f"\ue000{i}\ue001", markup)
    return value


def _code_lines(value: str) -> str:
    lines = value.split("\n")
    return "".join(f'<span class="code-line">{esc(line)}</span>' for line in lines)


def render_code_view(
    value: str,
    label: str,
    language: str = "",
    *,
    terminal: bool = False,
) -> str:
    language = re.sub(r"[^a-zA-Z0-9_+.#-]", "", language or "")
    cls = "code-viewer terminal" if terminal else "code-viewer"
    lang = f'<span class="code-lang">{esc(language)}</span>' if language else ""
    content = esc(value) if terminal else _code_lines(value)
    return (
        f'<div class="{cls}" role="group" aria-label="{esc(label)} viewer"><div class="code-head">'
        f'<span class="code-label">{esc(label)}</span>{lang}'
        '<span class="code-actions">'
        f'<button type="button" class="code-action" data-wrap-code aria-pressed="false" '
        f'aria-label="Toggle line wrapping for {esc(label)}">Wrap</button>'
        f'<button type="button" class="code-action" data-copy-code '
        f'aria-label="Copy {esc(label)}">Copy</button>'
        '</span></div>'
        f'<pre><code class="language-{esc(language or "text")}">{content}</code></pre></div>'
    )


def _table_cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith(r"\|"):
        line = line[:-1]
    return [c.replace(r"\|", "|").strip() for c in re.split(r"(?<!\\)\|", line)]


def _table_delimiter(line: str) -> bool:
    cells = _table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


def _markdown_block_start(line: str) -> bool:
    return bool(
        re.match(r"^ {0,3}(#{1,6})\s+", line)
        or re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        or re.match(r"^\s*>\s?", line)
        or re.match(r"^\s*[-+*]\s+", line)
        or re.match(r"^\s*\d+[.)]\s+", line)
        or re.fullmatch(r"\s{0,3}([-*_])(?:\s*\1){2,}\s*", line)
        or line.startswith("    ")
    )


def render_markdown(value: str) -> str:
    """Render common agent Markdown without external assets or raw HTML."""
    lines = (value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = ['<div class="md">']
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        fence = re.match(r"^ {0,3}(`{3,}|~{3,})\s*([^ ]*)\s*$", line)
        if fence:
            marker, language = fence.group(1), fence.group(2)
            i += 1
            body: list[str] = []
            closing = re.compile(rf"^\s*{re.escape(marker[0])}{{{len(marker)},}}\s*$")
            while i < len(lines) and not closing.match(lines[i]):
                body.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            out.append(render_code_view("\n".join(body), "code", language))
            continue

        if line.startswith("    "):
            body = []
            while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                body.append(lines[i][4:] if lines[i].startswith("    ") else "")
                i += 1
            out.append(render_code_view("\n".join(body).rstrip("\n"), "code"))
            continue

        heading = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            level = len(heading.group(1))
            out.append(f'<h{level}>{_inline_markdown(heading.group(2))}</h{level}>')
            i += 1
            continue

        if re.fullmatch(r"\s{0,3}([-*_])(?:\s*\1){2,}\s*", line):
            out.append("<hr>")
            i += 1
            continue

        if i + 1 < len(lines) and "|" in line and _table_delimiter(lines[i + 1]):
            headers = _table_cells(line)
            dividers = _table_cells(lines[i + 1])
            aligns = [
                "center" if c.startswith(":") and c.endswith(":")
                else "right" if c.endswith(":") else "left"
                for c in dividers
            ]
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                rows.append(_table_cells(lines[i]))
                i += 1
            out.append('<div class="md-table-wrap"><table><thead><tr>')
            for n, cell in enumerate(headers):
                align = aligns[n] if n < len(aligns) else "left"
                out.append(f'<th style="text-align:{align}">{_inline_markdown(cell)}</th>')
            out.append("</tr></thead><tbody>")
            for row in rows:
                out.append("<tr>")
                for n in range(len(headers)):
                    cell = row[n] if n < len(row) else ""
                    align = aligns[n] if n < len(aligns) else "left"
                    out.append(f'<td style="text-align:{align}">{_inline_markdown(cell)}</td>')
                out.append("</tr>")
            out.append("</tbody></table></div>")
            continue

        if re.match(r"^\s*>\s?", line):
            quoted: list[str] = []
            while i < len(lines) and re.match(r"^\s*>\s?", lines[i]):
                quoted.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f'<blockquote>{render_markdown("\n".join(quoted))}</blockquote>')
            continue

        bullet = re.match(r"^\s*[-+*]\s+(.+)", line)
        ordered = re.match(r"^\s*\d+[.)]\s+(.+)", line)
        if bullet or ordered:
            tag = "ul" if bullet else "ol"
            pattern = r"^\s*[-+*]\s+(.+)" if bullet else r"^\s*\d+[.)]\s+(.+)"
            out.append(f"<{tag}>")
            while i < len(lines):
                item = re.match(pattern, lines[i])
                if not item:
                    break
                body = item.group(1)
                task = re.match(r"^\[([ xX])\]\s+(.+)", body)
                if task:
                    on = task.group(1).lower() == "x"
                    mark = "✓" if on else "○"
                    out.append(
                        f'<li class="md-task"><span class="md-check{" on" if on else ""}">'
                        f'{mark}</span>{_inline_markdown(task.group(2))}</li>'
                    )
                else:
                    out.append(f'<li>{_inline_markdown(body)}</li>')
                i += 1
            out.append(f"</{tag}>")
            continue

        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip():
            if _markdown_block_start(lines[i]):
                break
            if i + 1 < len(lines) and "|" in lines[i] and _table_delimiter(lines[i + 1]):
                break
            paragraph.append(lines[i])
            i += 1
        out.append(f'<p>{_inline_markdown("\n".join(paragraph))}</p>')

    out.append("</div>")
    return "".join(out)


def render_feed(events: list[dict]) -> str:
    if not events:
        return '<div class="empty">stream.jsonl has no activity yet</div>'
    bits = ['<ol class="feed-list" aria-label="Agent activity transcript">']
    for e in events:
        kind = e.get("kind") or "text"
        ok = e.get("ok")
        state_cls = " ok" if ok is True else (" bad" if ok is False else "")

        if kind == "tool":
            tool = str(e.get("tool") or "Tool")
            title = str(e.get("title") or "Tool call")
            prefix = f"{tool} · "
            if title.lower().startswith(prefix.lower()):
                title = title[len(prefix):]
            inp = e.get("input")
            output = e.get("output")
            if inp is None and output is None:
                inp = e.get("detail") or ""
                output = ""
            state = "completed" if ok is True else ("failed" if ok is False else "pending")
            opened = " open" if ok is False else ""
            bits.append(
                f'<li class="chat-row tool-event"><div class="chat-avatar" aria-hidden="true">&gt;_</div>'
                f'<div class="chat-main"><div class="chat-label">Tool activity</div>'
                f'<details class="tool-card{state_cls}"{opened}><summary class="tool-summary">'
                f'<span class="tool-glyph" aria-hidden="true">&gt;_</span><span class="tool-copy">'
                f'<span class="tool-name">{esc(tool)}</span><span class="tool-title">{esc(title)}</span>'
                f'</span><span class="tool-state"><span>{esc(state)}</span></span></summary>'
                '<div class="tool-body">'
            )
            if inp:
                bits.append(render_code_view(
                    str(inp), str(e.get("input_label") or "input"),
                    str(e.get("language") or ""), terminal=False,
                ))
            if output:
                output_language = str(e.get("output_language") or "text")
                bits.append(render_code_view(
                    str(output), "error output" if ok is False else "output",
                    output_language, terminal=output_language == "terminal",
                ))
            if not inp and not output:
                bits.append('<div class="empty">no captured tool input or output</div>')
            bits.append("</div></details></div></li>")
            continue

        if kind == "notice":
            title = e.get("title") or e.get("detail") or "session notice"
            bits.append(
                f'<li class="event-line" role="status"><span class="event-mark" aria-hidden="true"></span>'
                f'<span>{esc(title)}</span></li>'
            )
            continue

        if kind == "result":
            bits.append(
                f'<li class="chat-row result-event"><div class="chat-avatar" aria-hidden="true">R</div>'
                f'<div class="chat-main"><div class="chat-label">Session result</div>'
                f'<div class="result-card{state_cls}"><div class="result-title">'
                f'{esc(e.get("title") or "done")}</div>'
            )
            if e.get("detail"):
                bits.append(render_markdown(str(e["detail"])))
            bits.append("</div></div></li>")
            continue

        bits.append(
            '<li class="chat-row assistant-message"><div class="chat-avatar" aria-hidden="true">A</div>'
            '<div class="chat-main"><div class="chat-label">Agent</div><div class="message-bubble">'
            f'{render_markdown(str(e.get("detail") or e.get("title") or ""))}'
            '</div></div></li>'
        )
    bits.append("</ol>")
    return "".join(bits)


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
    alerts = [
        s for s in sessions
        if str(s.get("state") or "").split(":")[0] in ("stuck", "overdue", "review", "stopped")
        or (
            int(s.get("uncommitted_count") or 0) > 0
            and str(s.get("state") or "").split(":")[0] in ("done", "stopped")
        )
    ]

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
    if d["ac_total"]:
        progress_done = d["ac_done"]
        progress_total = d["ac_total"]
        progress_label = "criteria met"
    else:
        # Before tasks have acceptance criteria, shipped tasks are the only
        # available denominator. Once criteria exist, they are the honest read
        # on implemented/verified work while [x] remains reserved for post-G5.
        progress_done = len(done)
        progress_total = total
        progress_label = "tasks shipped"
    pct = (100.0 * progress_done / progress_total) if progress_total else 0.0
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
             f'<div class="lbl">{progress_done}/{progress_total} {progress_label}</div>'
             '</div></div></div>')

    from delivery import summary
    from ops import WorkflowError
    try:
        delivery = summary(root)
        if delivery["mode"] == "sprint":
            p.append(f'<h2>{esc(delivery["milestone"])} · {esc(delivery["id"])}</h2>'
                     f'<p>{esc(delivery["goal"])}</p><p>'
                     f'{delivery["done"]}/{delivery["current"]} after G5 · '
                     f'{delivery["committed"]} originally committed · '
                     f'+{delivery["added"]}/−{delivery["removed"]} scope changes · '
                     f'{delivery["in_test"]} awaiting G4 · {delivery["beta"]} awaiting G5</p>')
            p.append(f'<p>Demo: <code>{esc(delivery["demo"])}</code></p>')
            if delivery.get("preview"):
                p.append(f'<p>Early frontend preview: {esc(delivery["preview"])}</p>')
        else:
            p.append(f'<p>{esc(delivery["message"])}</p>')
    except (WorkflowError, KeyError, TypeError) as exc:
        p.append(f'<p role="alert">Invalid delivery plan: {esc(str(exc))}</p>')
    problems = [f'{t["id"]}: {problem}' for t in tasks for problem in t.get("problems", [])]
    if problems:
        p.append('<p role="alert">Task integrity errors; counts are provisional: '
                 + esc('; '.join(problems)) + '</p>')
    if not static:
        from foreman_lib import load_json
        from events import pending
        resource = load_json(root / "work" / "resources.json")
        if resource:
            p.append(f'<p>Worker admission: {"paused" if resource.get("paused") else "open"} · '
                     f'{esc(resource.get("reason", "unknown"))}</p>')
        waiting = pending(root)
        p.append(f'<p>{len(waiting)} events awaiting manager disposition. '
                 'Full history: <code>work/events/</code></p>')
        queue = load_json(root / "work" / "queue.json", {"jobs": []})
        held = [j for j in queue.get("jobs", []) if j.get("state") in ("pending", "failed", "interrupted")]
        for job in held[:10]:
            p.append(f'<p>{esc(job.get("name"))}: {esc(job.get("state"))} · {esc(job.get("error", "queued"))}</p>')

    # stat rail
    tiles = [
        ("live" if d["ac_total"] and d["ac_done"] == d["ac_total"] else "", "Criteria met",
         f'{d["ac_done"]}/{d["ac_total"]}', "verified, not claimed"),
        ("", "Shipped", f'{len(done)}/{total}', "tasks after G5 / planned"),
    ]
    if not static:
        tiles += [
            ("", "Sessions", f'{len(sessions)}', f'{len(d["live"])} live'),
            ("", "Turns", f'{d["turns"]:,}', "across all workers"),
            ("", "Spend", f'${d["spend"]:.2f}', "settled runs only"),
            ("warn" if d["handovers"] else "", "Handovers", f'{d["handovers"]}',
             "context compactions"),
            ("bad" if d["alerts"] else "", "Alerts", f'{len(d["alerts"])}',
             "stuck, stopped, review or salvage" if d["alerts"] else "all clear"),
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
                if s and int(s.get("uncommitted_count") or 0) > 0:
                    tg.append(
                        f'<span class="tag b">{int(s.get("uncommitted_count") or 0)} uncommitted</span>'
                    )
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
                click = ""
                if not static and t.get("session"):
                    click = (f' data-open-session="{esc(t["session"])}" tabindex="0" '
                             'role="button" title="open agent transcript"')
                p.append(f'<div class="card"{click}><div class="cid">{esc(t["id"])}</div>'
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
                alert = " alert" if base in ("stuck", "overdue", "review", "stopped") else ""
                cpct = float(s.get("context_pct") or 0)
                thr = float(s.get("compact_pct") or 55)
                cost = float(s.get("cost_usd") or 0)
                budget = float(s.get("budget_usd") or 0)
                turns = int(s.get("turns") or 0)
                mt = int(s.get("max_turns") or 0)
                dl = s.get("deadline_ts")
                start = s.get("started_at")
                settled = base in ("done", "ready", "review", "stopped", "unknown")
                dl_txt = "—"
                dl_pct = 0.0
                if settled:
                    dl = None          # a finished session is not "overdue"
                if dl and start:
                    span = max(dl - start, 1)
                    dl_pct = 100.0 * (time.time() - start) / span
                    left = int((dl - time.time()) // 60)
                    dl_txt = f"{left}m left" if left > 0 else f"{-left}m over"
                sess_name = esc(s.get("name"))
                dirty = int(s.get("uncommitted_count") or 0)
                dirty_label = f" · {dirty} uncommitted" if dirty else ""
                p.append(f'<div class="sc{alert}" data-open-session="{sess_name}" tabindex="0" '
                         f'role="button" title="open agent transcript"><header><div><div class="nm">{sess_name}</div>'
                         f'<div class="ag">{esc(s.get("agent"))} · {esc(s.get("model") or "—")}'
                         f'{esc(dirty_label)}</div></div>'
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
             'regenerate with <code>/foreman:board</code>'
             + ('' if static else ' · click a session or in-flight card to read its agent transcript')
             + '</footer></div>')

    if not static:
        p.append('<div id="feed" class="feed" aria-hidden="true" inert>')
        p.append('<div class="feed-scrim" data-close-feed></div>')
        p.append('<aside class="feed-pane" role="dialog" aria-modal="true" '
                 'aria-labelledby="feed-title" aria-describedby="feed-note">')
        p.append('<header><div class="feed-heading"><span class="feed-eyebrow">Task activity</span>'
                 '<h3 id="feed-title">session</h3><div id="feed-meta" class="feed-meta"></div></div>'
                 '<div class="feed-actions">'
                 '<button type="button" class="feed-btn tools-toggle" data-toggle-tools>Expand tools</button>'
                 '<button type="button" class="feed-btn" data-feed-latest>Latest</button>'
                 '<button type="button" class="feed-btn" data-close-feed>Close</button>'
                 '</div></header>')
        p.append('<p id="feed-note" class="feed-note">Chat transcript from stream.jsonl · '
                 'refreshes when the dashboard regenerates (or runs with <code>--watch</code>)</p>')
        p.append('<div class="feed-body">')
        p.append('<div id="feed-empty" class="empty">Transcript not embedded in this bounded preview. '
                 'The full captured stream remains in work/sessions/&lt;session-name&gt;/stream.jsonl.</div>')
        sdir = sessions_dir(root)
        task_by_session = {t.get("session"): t for t in tasks if t.get("session")}
        # Keep the console proportional to live work. Old complete transcripts
        # remain in their session directories instead of inflating every refresh.
        ordered = sorted(sessions, key=lambda s: (s.get("state", "").split(":")[0] in ("starting", "running", "quiet", "stuck", "overdue"), s.get("started_at", 0)), reverse=True)
        for s in ordered[:12]:
            name = s.get("name")
            if not name:
                continue
            events = parse_stream_activity(sdir / name / "stream.jsonl", max_events=60, max_detail=1200)
            state = str(s.get("state") or "unknown")
            task = task_by_session.get(name)
            display_title = (
                f'{task["id"]} — {task["title"]}' if task else str(name)
            )
            summary = " · ".join(filter(None, [
                str(name), str(s.get("agent") or "agent"), state,
                f'{int(s.get("turns") or 0)} turns', f'{len(events)} events',
            ]))
            is_live = state.split(":")[0] in ("starting", "running", "quiet")
            p.append(f'<div class="feed-panel" data-session="{esc(name)}" '
                     f'data-title="{esc(display_title)}" data-summary="{esc(summary)}" '
                     f'data-live="{str(is_live).lower()}" hidden>'
                     f'{render_feed(events)}</div>')
        p.append("</div></aside></div>")
        p.append(f"<script>{JS}</script>")

    return "\n".join(p)


def write_html(root: Path, out: Path, static: bool, refresh: int | None = None) -> None:
    refresh_tag = (f'<meta http-equiv="refresh" content="{int(refresh)}">'
                   if refresh and not static else "")
    out.parent.mkdir(parents=True, exist_ok=True)
    content = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{refresh_tag}"
        f"<title>Foreman — {html.escape(root.parent.name)}</title></head><body>"
        f"{render(root, static=static)}</body></html>\n")
    from foreman_lib import atomic_write
    if not static or not out.is_file() or out.read_text() != content:
        atomic_write(out, content)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".foreman")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--static", action="store_true",
                    help="write the tracked board.html: no timestamp, no live session state")
    ap.add_argument("--watch", nargs="?", const=8, type=int, metavar="SEC",
                    help="rewrite the live dashboard every SEC seconds (default 8)")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        sys.exit(f"dashboard.py: no such directory: {root}")

    if a.static:
        out = root / "board.html"          # tracked, deterministic
        write_html(root, out, static=True)
        print(f"wrote {out}")
        if a.open:
            subprocess.run(["open", str(out)], check=False)
    else:
        out = work_dir(root) / "dashboard.html"   # scratchpad, live
        interval = a.watch
        write_html(root, out, static=False, refresh=interval)
        print(f"wrote {out}")
        if a.open:
            subprocess.run(["open", str(out)], check=False)
        if interval:
            print(f"watching every {interval}s · ctrl-c to stop", flush=True)
            try:
                while True:
                    time.sleep(interval)
                    write_html(root, out, static=False, refresh=interval)
                    print(f"rewrote {out}", flush=True)
            except KeyboardInterrupt:
                print("stopped")
