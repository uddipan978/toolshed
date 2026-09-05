#!/usr/bin/env python3
"""Foreman supervisor: watch worker sessions and emit one line per state change.

Designed to run under the Monitor tool with persistent:true. Every stdout line
becomes a notification the manager reacts to, so the filter is deliberately
narrow: state transitions and threshold crossings only, never routine progress.

  supervise.py --root .foreman [--interval 30] [--once]

Escalation ladder (minutes without a new stream event):
  10  log only        15  POKE      30  ESCALATE      deadline/budget  STOP

Git ladder:
  40% of turn cap + dirty  CHECKPOINT     stopped + dirty  SALVAGE

Terminal classification:
  normal success + complete artefacts  DONE
  abnormal exit + complete artefacts   READY:<subtype>
  terminal + incomplete artefacts      REVIEW:<subtype>
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import (  # noqa: E402
    append_log, load_json, pid_alive, read_stream, save_json, sessions_dir,
    worktree_snapshot,
)
from verify_gate import GATED_AGENTS, session_completion_problems  # noqa: E402
from ops import lock, session_alive, update_session
from events import publish, pending

QUIET_LOG = 10 * 60
QUIET_POKE = 15 * 60
QUIET_ESCALATE = 30 * 60
CHECKPOINT_TURN_FRACTION = 0.40


def emit(line: str) -> None:
    """One stdout line == one manager notification."""
    print(line, flush=True)


def assess(sdir: Path, now: float) -> dict:
    """Compute the current picture for one session. Pure; no side effects."""
    status = load_json(sdir / "status.json")
    if not status:
        return {}
    if status.get("integrated_at") or status.get("retired_at"):
        return {}  # avoid rereading historical transcripts after safe cleanup
    stream = read_stream(sdir / "stream.jsonl")

    quiet = now - (stream["last_event_ts"] or status.get("started_at", now))
    alive = session_alive(status)
    deadline_ts = status.get("deadline_ts", 0)
    budget = float(status.get("budget_usd") or 0)
    compact_pct = float(status.get("compact_pct") or 55)

    # One repository read feeds dirty monitoring, provenance reporting, and the
    # terminal completion gate. This matters on runs with dozens of sessions.
    git_state = {
        "is_repo": False, "dirty_paths": [], "commits_ahead": 0,
        "committed_paths": [], "head": "", "effective_start_commit": "",
        "start_commit_source": "not-checked",
    }
    cwd_raw = status.get("cwd") or ""
    cwd = Path(cwd_raw) if cwd_raw else None
    repository_snapshot = None
    if status.get("branch") and cwd is not None and cwd.is_dir():
        git_state = worktree_snapshot(
            cwd, status.get("start_commit"), status.get("base_commit")
        )
        repository_snapshot = git_state

    starting = status.get("state") == "starting" and now - status.get("started_at", now) < 60
    terminated = bool(not alive and not starting)
    completion_problems: list[str] = []
    termination_subtype = ""
    if status.get("integrated_at") or status.get("retired_at"):
        return {}  # archived receipts own these sessions; deleted worktrees are expected
    if terminated:
        # error_max_budget_usd / error_max_turns are real result subtypes.
        termination_subtype = (
            "gate_deferred" if status.get("gate_deferred")
            else stream["result_subtype"] or ("exited" if not alive else "done")
        )
        short_agent = (status.get("agent") or "").split(":")[-1]
        if short_agent in GATED_AGENTS:
            completion_problems = session_completion_problems(
                sdir, status, repository_snapshot
            )
            if completion_problems:
                review_subtype = (
                    "gate_incomplete"
                    if termination_subtype in ("success", "done")
                    else termination_subtype
                )
                state = f"review:{review_subtype}"
            elif termination_subtype in ("success", "done"):
                state = "done"
            else:
                state = f"ready:{termination_subtype}"
        else:
            state = (
                "done" if termination_subtype in ("success", "done")
                else f"stopped:{termination_subtype}"
            )
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
    dirty = bool(git_state["dirty_paths"])
    checkpoint_pressure = bool(
        dirty and max_turns
        and stream["turns"] >= CHECKPOINT_TURN_FRACTION * max_turns
    )

    return {
        "status": status,
        "stream": stream,
        "quiet": quiet,
        "alive": alive,
        "state": state,
        "termination_subtype": termination_subtype,
        "completion_problems": completion_problems,
        "over_budget": bool(budget and stream["cost_usd"] >= budget),
        "over_context": stream["context_pct"] >= compact_pct,
        "turn_pressure": turn_pressure,
        "git": git_state,
        "checkpoint_pressure": checkpoint_pressure,
        "needs_salvage": bool(dirty and terminated),
    }


def sweep(root: Path, once: bool = False, interval: int = 30, prefix: str = "",
          regenerate: bool = True) -> None:
    sdirs = sessions_dir(root)

    while True:
        # Persist deduplication across manager/supervisor restarts. Notifications
        # are hints; the outbox remains queryable until disposition is acknowledged.
        seen = load_json(root / "work" / "supervisor.json")
        now = time.time()
        emitted = 0
        def announce(line):
            nonlocal emitted
            kind, name, detail = line.split(" ", 2)
            status = load_json(sdirs / name / "status.json")
            item = publish(root, name, kind, detail.lstrip("— "),
                           f"{status.get('session_id', '')}:{s if kind in ('DONE', 'READY', 'REVIEW', 'FAILED') else kind}")
            if emitted < 20:
                emit(f"{line} [event={item['id']}]")
                emitted += 1
        if sdirs.is_dir():
            for sdir in sorted(p for p in sdirs.iterdir() if p.is_dir()):
                if not sdir.name.startswith(prefix):
                    continue
                try:
                    a = assess(sdir, now)
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    publish(root, sdir.name, "REVIEW", f"cannot assess session: {exc}", "assessment-error")
                    continue
                if not a:
                    continue
                name = a["status"].get("name", sdir.name)
                s, st = a["state"], a["stream"]

                # Persist the live picture so the board, the dashboard and the
                # manager all read the same numbers.
                a["status"] = update_session(sdir,
                    state=s,
                    context_pct=st["context_pct"],
                    context_tokens=st["context_tokens"],
                    context_window=st["context_window"],
                    cost_usd=round(st["cost_usd"], 4),
                    turns=st["turns"],
                    model=st["model"],
                    quiet_seconds=int(a["quiet"]),
                    uncommitted_count=len(a["git"]["dirty_paths"]),
                    uncommitted_paths=a["git"]["dirty_paths"][:20],
                    commits_ahead=a["git"]["commits_ahead"],
                    committed_paths=a["git"]["committed_paths"][:50],
                    effective_start_commit=a["git"]["effective_start_commit"],
                    start_commit_source=a["git"]["start_commit_source"],
                    termination_subtype=a["termination_subtype"],
                    completion_problems=a["completion_problems"],
                    updated_at=int(now),
                )

                metrics = (
                    f"ctx={st['context_pct']}% "
                    f"(${st['cost_usd']:.2f}/${a['status'].get('budget_usd')}) "
                    f"turns={st['turns']}"
                )

                # A copy is recovery material, not a commit. Never remove the
                # original worktree or tell a successor its branch preserved it.
                if a["git"]["dirty_paths"] and (a["needs_salvage"] or a["checkpoint_pressure"] or now - a["status"].get("started_at", now) >= 120):
                    last = a["status"].get("checkpoint_at", 0)
                    if a["needs_salvage"] or now - last >= 300:
                        from checkpoint import preserve
                        recovery = preserve(sdir, a["status"])
                        update_session(sdir, checkpoint_at=now, recovery=recovery)

                # Threshold crossings are keyed separately from state so a
                # session cannot re-announce the same condition every sweep.
                if a["needs_salvage"] and seen.get(f"{name}:salvage") != "hit":
                    seen[f"{name}:salvage"] = "hit"
                    paths = ", ".join(a["git"]["dirty_paths"][:6])
                    announce(
                        f"SALVAGE {name} — worker stopped with uncommitted work: {paths}. "
                        "Do not integrate, remove the worktree, or claim the branch preserved it."
                    )
                    append_log(root, f"`{name}` stopped with uncommitted work requiring salvage")
                elif a["checkpoint_pressure"] and seen.get(f"{name}:checkpoint") != "hit":
                    seen[f"{name}:checkpoint"] = "hit"
                    announce(
                        f"CHECKPOINT {name} — {st['turns']}/{a['status'].get('max_turns')} "
                        "turns used with uncommitted work. Commit explicit task-scoped paths now."
                    )
                    append_log(
                        root,
                        f"`{name}` reached {CHECKPOINT_TURN_FRACTION:.0%} of its turn cap "
                        "with uncommitted work",
                    )

                terminal = s.split(":")[0] in ("done", "ready", "review", "stopped")
                if not terminal and a["over_context"] and seen.get(f"{name}:ctx") != "hit":
                    seen[f"{name}:ctx"] = "hit"
                    announce(f"COMPACT {name} — crossed {a['status'].get('compact_pct')}% context, {metrics}")
                    append_log(root, f"`{name}` crossed compaction threshold — {metrics}")

                if not terminal and a["turn_pressure"] and seen.get(f"{name}:turns") != "hit":
                    seen[f"{name}:turns"] = "hit"
                    announce(f"TURNS {name} — {st['turns']}/{a['status'].get('max_turns')} turns used, "
                         f"{metrics}. It may not finish; consider narrowing the remaining scope.")
                    append_log(root, f"`{name}` passed 80% of its turn cap — {metrics}")

                if not terminal and a["over_budget"] and seen.get(f"{name}:budget") != "hit":
                    seen[f"{name}:budget"] = "hit"
                    announce(f"BUDGET {name} — spend cap reached, {metrics}")
                    append_log(root, f"`{name}` hit budget cap — {metrics}")

                if seen.get(name) == s:
                    continue
                seen[name] = s

                if s == "quiet":
                    a["status"]["pokes"] = a["status"].get("pokes", 0) + 1
                    update_session(sdir, pokes=a["status"]["pokes"])
                    announce(f"POKE {name} — no output for {int(a['quiet'] // 60)}m, {metrics}")
                elif s == "stuck":
                    announce(f"STUCK {name} — no output for {int(a['quiet'] // 60)}m, {metrics}. Decide: continue or respawn.")
                    append_log(root, f"`{name}` flagged stuck after {int(a['quiet'] // 60)}m")
                elif s == "overdue":
                    announce(f"OVERDUE {name} — past deadline, {metrics}. Stop and hand over.")
                    append_log(root, f"`{name}` passed deadline — {metrics}")
                elif s == "done":
                    announce(f"DONE {name} — {metrics}")
                    append_log(root, f"`{name}` completed — {metrics}")
                elif s.startswith("ready:"):
                    subtype = s.split(":", 1)[1]
                    announce(
                        f"READY {name} — gates pass despite {subtype}, {metrics}. "
                        "Review the verdict, then advance or route it."
                    )
                    append_log(root, f"`{name}` ready after {subtype} — {metrics}")
                elif s.startswith("review:"):
                    subtype = s.split(":", 1)[1]
                    detail = a["completion_problems"][0] if a["completion_problems"] else "inspect evidence"
                    announce(f"REVIEW {name} — {subtype}: {detail}, {metrics}")
                    append_log(root, f"`{name}` needs review after {subtype} — {metrics}")
                elif s.startswith("stopped:"):
                    announce(f"FAILED {name} — {s.split(':', 1)[1]}, {metrics}")
                    append_log(root, f"`{name}` stopped: {s.split(':', 1)[1]} — {metrics}")

        save_json(root / "work" / "supervisor.json", seen)
        outstanding = pending(root, prefix)
        previous = load_json(root / "work" / "heartbeat.json")
        if now - previous.get("emitted_at", 0) >= 300:
            emit(f"HEARTBEAT foreman — {len(outstanding)} unacknowledged events; inspect events.py. Supervisor sweep completed.")
            save_json(root / "work" / "heartbeat.json", {"emitted_at": now, "pending": len(outstanding)})
        if regenerate:
            from refresh import refresh
            refresh(root)
        if once:
            return
        time.sleep(interval)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".foreman")
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--once", action="store_true", help="single sweep, then exit")
    ap.add_argument("--prefix", default="", help="session name prefix; never filter by live PID")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.exists():
        sys.exit(f"supervise.py: no such directory: {root}")
    try:
        with lock(root, "supervisor", blocking=False):
            sweep(root, once=args.once, interval=max(1, args.interval), prefix=args.prefix)
    except KeyboardInterrupt:
        pass
