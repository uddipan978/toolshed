#!/usr/bin/env python3
"""Foreman supervisor: watch worker sessions and emit one line per state change.

Designed to run under the Monitor tool with persistent:true. Every stdout line
becomes a notification the manager reacts to, so the filter is deliberately
narrow: state transitions and threshold crossings only, never routine progress.

  supervise.py --root .foreman [--interval 30] [--once]

Escalation ladder (minutes without a new stream event):
  10  log only        15  POKE      30  ESCALATE      deadline/budget  STOP
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import (append_log, load_json, pid_alive, read_stream,  # noqa: E402
                         save_json, sessions_dir)

QUIET_LOG = 10 * 60
QUIET_POKE = 15 * 60
QUIET_ESCALATE = 30 * 60


def emit(line: str) -> None:
    """One stdout line == one manager notification."""
    print(line, flush=True)


def assess(sdir: Path, now: float) -> dict:
    """Compute the current picture for one session. Pure; no side effects."""
    status = load_json(sdir / "status.json")
    if not status:
        return {}
    stream = read_stream(sdir / "stream.jsonl")

    quiet = now - (stream["last_event_ts"] or status.get("started_at", now))
    alive = pid_alive(status.get("pid"))
    deadline_ts = status.get("deadline_ts", 0)
    budget = float(status.get("budget_usd") or 0)
    compact_pct = float(status.get("compact_pct") or 55)

    if stream["finished"] or not alive:
        # error_max_budget_usd / error_max_turns are real result subtypes.
        sub = stream["result_subtype"] or ("exited" if not alive else "done")
        state = "done" if sub in ("success", "done") else f"stopped:{sub}"
    elif deadline_ts and now > deadline_ts:
        state = "overdue"
    elif quiet > QUIET_ESCALATE:
        state = "stuck"
    elif quiet > QUIET_POKE:
        state = "quiet"
    else:
        state = "running"

    # Cost only appears in the final result event, so mid-run spend is unknown.
    # Turns are reported on every assistant message, so they are the live proxy
    # for a worker running out of room.
    max_turns = int(status.get("max_turns") or 0)
    turn_pressure = bool(max_turns and stream["turns"] >= 0.8 * max_turns)

    return {
        "status": status,
        "stream": stream,
        "quiet": quiet,
        "alive": alive,
        "state": state,
        "over_budget": bool(budget and stream["cost_usd"] >= budget),
        "over_context": stream["context_pct"] >= compact_pct,
        "turn_pressure": turn_pressure,
    }


def sweep(root: Path, once: bool = False) -> None:
    sdirs = sessions_dir(root)
    seen: dict[str, str] = {}

    while True:
        now = time.time()
        if sdirs.is_dir():
            for sdir in sorted(p for p in sdirs.iterdir() if p.is_dir()):
                a = assess(sdir, now)
                if not a:
                    continue
                name = a["status"].get("name", sdir.name)
                s, st = a["state"], a["stream"]

                # Persist the live picture so the board, the dashboard and the
                # manager all read the same numbers.
                a["status"].update(
                    state=s,
                    context_pct=st["context_pct"],
                    context_tokens=st["context_tokens"],
                    context_window=st["context_window"],
                    cost_usd=round(st["cost_usd"], 4),
                    turns=st["turns"],
                    model=st["model"],
                    quiet_seconds=int(a["quiet"]),
                    updated_at=int(now),
                )
                save_json(sdir / "status.json", a["status"])

                metrics = (
                    f"ctx={st['context_pct']}% "
                    f"(${st['cost_usd']:.2f}/${a['status'].get('budget_usd')}) "
                    f"turns={st['turns']}"
                )

                # Threshold crossings are keyed separately from state so a
                # session cannot re-announce the same condition every sweep.
                if a["over_context"] and seen.get(f"{name}:ctx") != "hit":
                    seen[f"{name}:ctx"] = "hit"
                    emit(f"COMPACT {name} — crossed {a['status'].get('compact_pct')}% context, {metrics}")
                    append_log(root, f"`{name}` crossed compaction threshold — {metrics}")

                if a["turn_pressure"] and seen.get(f"{name}:turns") != "hit":
                    seen[f"{name}:turns"] = "hit"
                    emit(f"TURNS {name} — {st['turns']}/{a['status'].get('max_turns')} turns used, "
                         f"{metrics}. It may not finish; consider narrowing the remaining scope.")
                    append_log(root, f"`{name}` passed 80% of its turn cap — {metrics}")

                if a["over_budget"] and seen.get(f"{name}:budget") != "hit":
                    seen[f"{name}:budget"] = "hit"
                    emit(f"BUDGET {name} — spend cap reached, {metrics}")
                    append_log(root, f"`{name}` hit budget cap — {metrics}")

                if seen.get(name) == s:
                    continue
                seen[name] = s

                if s == "quiet":
                    a["status"]["pokes"] = a["status"].get("pokes", 0) + 1
                    save_json(sdir / "status.json", a["status"])
                    emit(f"POKE {name} — no output for {int(a['quiet'] // 60)}m, {metrics}")
                elif s == "stuck":
                    emit(f"STUCK {name} — no output for {int(a['quiet'] // 60)}m, {metrics}. Decide: continue or respawn.")
                    append_log(root, f"`{name}` flagged stuck after {int(a['quiet'] // 60)}m")
                elif s == "overdue":
                    emit(f"OVERDUE {name} — past deadline, {metrics}. Stop and hand over.")
                    append_log(root, f"`{name}` passed deadline — {metrics}")
                elif s == "done":
                    emit(f"DONE {name} — {metrics}")
                    append_log(root, f"`{name}` completed — {metrics}")
                elif s.startswith("stopped:"):
                    emit(f"FAILED {name} — {s.split(':', 1)[1]}, {metrics}")
                    append_log(root, f"`{name}` stopped: {s.split(':', 1)[1]} — {metrics}")

        if once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".foreman")
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--once", action="store_true", help="single sweep, then exit")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.exists():
        sys.exit(f"supervise.py: no such directory: {root}")
    try:
        sweep(root, once=args.once)
    except KeyboardInterrupt:
        pass
