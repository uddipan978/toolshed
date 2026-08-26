#!/usr/bin/env python3
"""Write and restore Foreman handover documents.

Two modes, wired to the two hooks that make compaction survivable:

  --write     PreCompact hook. Assembles sessions/<name>/handover-N.md.
  --restore   SessionStart(matcher=compact) hook. Prints the newest handover to
              stdout, which Claude Code injects into the fresh context. PreCompact
              stdout is NOT injected, which is why this takes two hooks rather than
              one.

Both read the hook payload as JSON on stdin.

The document is assembled from durable artifacts on disk — the brief, the worker's
own progress notes, git state — rather than by summarising the transcript. Claude
Code's transcript format is documented as internal and version-unstable, so
anything parsed from it here is strictly best-effort and clearly labelled.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import load_json, read_stream, run, sessions_dir  # noqa: E402

# Redact anything that looks like a credential before it lands in a file that
# becomes the next session's prompt.
SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{16,})"),
    re.compile(r"(ghp_[A-Za-z0-9]{16,})"),
    re.compile(r"(AKIA[0-9A-Z]{12,})"),
    re.compile(r"((?i:api[_-]?key|secret|password|token)\s*[=:]\s*)(\S+)"),
]


def redact(text: str) -> str:
    text = SECRET_PATTERNS[0].sub("[REDACTED]", text)
    text = SECRET_PATTERNS[1].sub("[REDACTED]", text)
    text = SECRET_PATTERNS[2].sub("[REDACTED]", text)
    return SECRET_PATTERNS[3].sub(r"\1[REDACTED]", text)


def session_dir(payload: dict) -> Path | None:
    """spawn.sh exports FOREMAN_SESSION_DIR; fall back to matching on session_id."""
    import os

    env = os.environ.get("FOREMAN_SESSION_DIR")
    if env and Path(env).is_dir():
        return Path(env)

    root = os.environ.get("FOREMAN_ROOT")
    sid = payload.get("session_id")
    if root and sid:
        sessions = sessions_dir(Path(root))
        if sessions.is_dir():
            for d in sessions.iterdir():
                if load_json(d / "status.json").get("session_id") == sid:
                    return d
    return None


def write_handover(payload: dict) -> int:
    sdir = session_dir(payload)
    if not sdir:
        return 0  # not a Foreman worker; compaction proceeds untouched

    n = len(list(sdir.glob("handover-*.md"))) + 1
    cwd = payload.get("cwd") or str(sdir)
    status = load_json(sdir / "status.json")
    stream = read_stream(sdir / "stream.jsonl")

    _, branch, _ = run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"], timeout=10)
    _, diffstat, _ = run(["git", "-C", cwd, "diff", "--stat", "HEAD"], timeout=15)
    _, untracked, _ = run(["git", "-C", cwd, "ls-files", "--others", "--exclude-standard"], timeout=15)

    brief = (sdir / "brief.md").read_text(errors="replace") if (sdir / "brief.md").exists() else ""
    task_ref = ""
    m = re.search(r"^\*\*Task file\*\*\s*(.+)$", brief, re.M)
    if m:
        task_ref = m.group(1).strip()

    # The worker is instructed to keep this file current as it works. It is the
    # single highest-value input here, because it is the only part written with
    # the next session in mind.
    progress = ""
    for candidate in ("progress.md", "PROGRESS.md"):
        p = sdir / candidate
        if p.exists():
            progress = p.read_text(errors="replace").strip()
            break

    doc = f"""# Handover {n} — {status.get('name', sdir.name)}

Written at {time.strftime('%Y-%m-%d %H:%M:%S')} because context reached
{stream['context_pct']}% of {stream['context_window']:,} tokens
(threshold {status.get('compact_pct', 55)}%).

You are continuing this work, not starting it. Read the references below rather
than re-deriving anything from scratch.

## Assignment
{('See `' + task_ref + '`') if task_ref else 'See `brief.md` in this directory.'}
Full brief: `{sdir / 'brief.md'}`

## Where the work stands
{progress or '_The worker kept no progress notes. Reconstruct from the git state below._'}

## Git state
Branch `{branch.strip() or 'unknown'}` in `{cwd}`

```
{diffstat.strip() or '(no tracked changes yet)'}
```

Untracked files:
```
{untracked.strip() or '(none)'}
```

## Budget consumed so far
- Spend ${stream['cost_usd']:.2f} of ${status.get('budget_usd', '?')}
- Turns {stream['turns']} of {status.get('max_turns', '?')}
- Deadline {time.strftime('%H:%M:%S', time.localtime(status.get('deadline_ts', 0))) if status.get('deadline_ts') else 'none'}

Spend and turns do **not** reset on compaction. Work accordingly.

## Suggested skills for this stretch
`mattpocock-skills:tdd` for the red/green loop · `mattpocock-skills:diagnosing-bugs` if
something is failing and the cause is not obvious · `/foreman:board` to update status.

## Standing rules
- Update the task file's Activity log and acceptance checkboxes as you go. Status
  lives in the file, not in a commit message.
- Do not mark an acceptance box checked until its Verify command has actually run
  and passed.
- Developers set status to `[t]` when Verify passes. Never `[x]` — G4 has not run.
- Keep `progress.md` in this session directory current — it is what the next
  handover is built from.
"""
    out = sdir / f"handover-{n}.md"
    out.write_text(redact(doc))
    print(f"[foreman] wrote {out}", file=sys.stderr)
    return 0


def restore_handover(payload: dict) -> int:
    sdir = session_dir(payload)
    if not sdir:
        return 0
    handovers = sorted(sdir.glob("handover-*.md"), key=lambda p: p.stat().st_mtime)
    if not handovers:
        return 0
    # stdout on exit 0 from SessionStart is injected into the model's context.
    print(handovers[-1].read_text(errors="replace"))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    # A hook that crashes must never take the session down with it.
    try:
        sys.exit(write_handover(payload) if args.write else restore_handover(payload))
    except Exception as exc:  # noqa: BLE001
        print(f"[foreman] handover hook error: {exc}", file=sys.stderr)
        sys.exit(0)
