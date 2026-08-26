"""Shared helpers for Foreman scripts. No third-party dependencies."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

# Context windows by model family. Foreman reads the model from the stream, so a
# worker on a different model is still measured against the right denominator.
CONTEXT_WINDOWS = {
    "opus-5[1m]": 1_000_000,
    "opus-5": 200_000,
    "sonnet-5": 1_000_000,
    "opus-4": 200_000,
    "sonnet-4": 200_000,
    "haiku": 200_000,
}
DEFAULT_CONTEXT_WINDOW = 200_000

STATUS_ORDER = ["backlog", "planned", "in_progress", "in_test", "beta", "awaiting_human", "done", "blocked"]

# Task checkbox legend -> lane. Kept in one place so board.py and dashboard.py agree.
# Every lane needs a token, or that lane can never be populated.
LEGEND = {
    " ": "backlog",
    ">": "planned",
    "~": "in_progress",
    "t": "in_test",
    "b": "beta",
    "x": "done",
    "!": "blocked",
    "?": "awaiting_human",
}


def context_window_for(model: str | None) -> int:
    """Best-effort context window for a model id. Falls back to the safe 200k."""
    if not model:
        return DEFAULT_CONTEXT_WINDOW
    m = model.lower()
    if "[1m]" in m or m.endswith("-1m"):
        return 1_000_000
    for key, size in CONTEXT_WINDOWS.items():
        if key.replace("[1m]", "") in m:
            return size
    return DEFAULT_CONTEXT_WINDOW


def read_stream(path: Path) -> dict:
    """Extract live metrics from a captured --output-format stream-json file.

    This is the supported interface. Claude Code's own session transcripts under
    ~/.claude/projects are documented as an internal format that changes between
    versions, so Foreman never parses those.

    Returns keys: context_tokens, context_window, context_pct, cost_usd, model,
    turns, last_event_ts, finished, result_subtype.
    """
    out = {
        "context_tokens": 0,
        "context_window": DEFAULT_CONTEXT_WINDOW,
        "context_pct": 0.0,
        "cost_usd": 0.0,
        "model": None,
        "turns": 0,
        "last_event_ts": None,
        "finished": False,
        "result_subtype": None,
    }
    if not path.exists():
        return out

    # The file is appended to while we read it; a torn final line is normal.
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return out

    for line in lines:
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue  # torn tail line, or interleaved stderr

        etype = ev.get("type")
        if etype == "assistant":
            msg = ev.get("message") or {}
            usage = msg.get("usage") or {}
            if usage:
                # Matches how Claude Code computes context usage for the status
                # line: input side only, output tokens excluded.
                out["context_tokens"] = (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                )
                out["turns"] += 1
            if msg.get("model"):
                out["model"] = msg["model"]
        elif etype == "result":
            out["finished"] = True
            out["result_subtype"] = ev.get("subtype")
            if isinstance(ev.get("total_cost_usd"), (int, float)):
                out["cost_usd"] = float(ev["total_cost_usd"])

    out["context_window"] = context_window_for(out["model"])
    if out["context_window"]:
        out["context_pct"] = round(100.0 * out["context_tokens"] / out["context_window"], 1)

    try:
        out["last_event_ts"] = path.stat().st_mtime
    except OSError:
        pass
    return out


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        return False
    return True


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)  # atomic; the supervisor may be read concurrently


def append_log(root: Path, message: str) -> None:
    """Append one timestamped line to .foreman/log.md."""
    log = root / "log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log.open("a") as fh:
        fh.write(f"- `{stamp}` {message}\n")


def slugify(text: str, maxlen: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:maxlen].rstrip("-")) or "untitled"


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """Run a command, never raise. Returns (rc, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: not found"


# --- task files ---------------------------------------------------------------

TASK_HEADING = re.compile(r"^#\s+(T-[\w.-]+)\s*[—–-]\s*(.+)$", re.M)
# Several fields share one line: "**Module** M01 · **Status** `[~]` · **Parallel** [P]".
# The value runs until the next bold marker, so it must not be anchored to the line.
TASK_FIELD = re.compile(r"\*\*([\w ]+?)\*\*\s*([^*\n]*)")
STATUS_TOKEN = re.compile(r"`\[(.)\]`")
CHECKBOX = re.compile(r"^\s*-\s+\[([ xX])\]\s+(.+)$", re.M)


def parse_task(path: Path) -> dict:
    """Read one task file into a dict. Tolerant: a malformed file still yields a
    card rather than breaking the whole board."""
    text = path.read_text(errors="replace")
    heading = TASK_HEADING.search(text)
    task = {
        "path": path,
        "id": heading.group(1) if heading else path.stem,
        "title": heading.group(2).strip() if heading else path.stem,
        "status": "backlog",
        "module": "",
        "depends_on": "",
        "session": "",
        "estimate": "",
        "parallel": False,
        "acceptance_total": 0,
        "acceptance_done": 0,
        "needs_clarification": "[NEEDS CLARIFICATION]" in text,
    }

    # Fields live on the two bold-prefixed lines under the heading.
    head = text[: text.find("\n## ")] if "\n## " in text else text
    for m in TASK_FIELD.finditer(head):
        key = m.group(1).strip().lower()
        value = m.group(2).strip().rstrip("·").strip()
        if key == "status":
            tok = STATUS_TOKEN.search(value)
            task["status"] = LEGEND.get(tok.group(1) if tok else " ", "backlog")
        elif key == "module":
            task["module"] = value
        elif key in ("depends on", "depends_on"):
            task["depends_on"] = "" if value in ("—", "-", "") else value
        elif key == "session":
            task["session"] = "" if value in ("—", "-", "") else value
        elif key == "est":
            task["estimate"] = value
        elif key == "parallel":
            task["parallel"] = "[P]" in value

    # Acceptance progress, counted only inside the Acceptance section.
    acc = re.search(r"^##\s+Acceptance.*?$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if acc:
        boxes = CHECKBOX.findall(acc.group(1))
        task["acceptance_total"] = len(boxes)
        task["acceptance_done"] = sum(1 for b, _ in boxes if b.lower() == "x")

    # A task in flight whose session has been flagged still reads as in_progress
    # from the file; the board overlays live session state separately.
    if task["needs_clarification"] and task["status"] == "backlog":
        task["status"] = "awaiting_human"
    return task


def parse_status_token(text: str) -> str:
    """Public helper: map a raw legend character to a lane name."""
    return LEGEND.get(text, "backlog")


def all_tasks(root: Path) -> list[dict]:
    """Every task file under .foreman/modules/*/tasks/, sorted by id."""
    tasks = []
    modules = root / "modules"
    if modules.is_dir():
        for tf in sorted(modules.glob("*/tasks/*.md")):
            try:
                tasks.append(parse_task(tf))
            except Exception:  # noqa: BLE001 - one bad file must not break the board
                continue
    return sorted(tasks, key=lambda t: t["id"])


def all_sessions(root: Path) -> list[dict]:
    out = []
    sdir = root / "sessions"
    if sdir.is_dir():
        for d in sorted(p for p in sdir.iterdir() if p.is_dir()):
            st = load_json(d / "status.json")
            if st:
                out.append(st)
    return out
