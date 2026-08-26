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
    "grok-4": 256_000,
    "grok-build": 256_000,
}
DEFAULT_CONTEXT_WINDOW = 200_000
HARNESSES = ("claude", "grok")

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
    if "[1m]" in m or m.endswith("-1m") or "2m" in m:
        return 1_000_000
    for key, size in CONTEXT_WINDOWS.items():
        if key.replace("[1m]", "") in m:
            return size
    if m.startswith("grok"):
        return 256_000
    return DEFAULT_CONTEXT_WINDOW


def detect_harness(root: Path | None = None) -> str:
    """Which worker runtime to use. Default is claude so existing installs
    keep their spawn path. Grok wins when this session is clearly a Grok TUI
    (`GROK_SESSION_ID`) or a stamp file says so. Override with FOREMAN_HARNESS.
    """
    explicit = (os.environ.get("FOREMAN_HARNESS") or "").strip().lower()
    if explicit in HARNESSES:
        return explicit
    if root is not None:
        stamp = Path(root) / "work" / "harness"
        if stamp.is_file():
            val = stamp.read_text(errors="replace").strip().lower()
            if val in HARNESSES:
                return val
    if os.environ.get("GROK_SESSION_ID") or os.environ.get("GROK_AGENT"):
        return "grok"
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE"):
        return "claude"
    if os.environ.get("GROK_PLUGIN_ROOT"):
        return "grok"
    if os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return "claude"
    return "claude"


def stamp_harness(foreman_root: Path, harness: str | None = None) -> str:
    """Write `.foreman/work/harness` so later spawn.sh calls agree."""
    h = harness or detect_harness(foreman_root)
    work = Path(foreman_root) / "work"
    if work.is_dir():
        (work / "harness").write_text(h + "\n")
    return h


def plugin_root() -> Path:
    for key in ("FOREMAN_PLUGIN_ROOT", "GROK_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        v = os.environ.get(key)
        if v:
            return Path(v)
    return Path(__file__).resolve().parent.parent


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
                # line: input side only, output tokens excluded. Grok's
                # streaming-messages-json assistant frames use the same buckets.
                out["context_tokens"] = (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                )
                out["turns"] += 1
            if msg.get("model"):
                out["model"] = msg["model"]
        elif etype in ("result", "end"):
            # Claude: type=result subtype=success|error_max_turns|error_max_budget_usd
            # Grok streaming-messages-json: type=result subtype=success|error_max_turns
            # Grok streaming-json: type=end stopReason=end_turn
            out["finished"] = True
            sub = ev.get("subtype")
            if not sub:
                if ev.get("is_error"):
                    sub = "error_during_execution"
                else:
                    sr = ev.get("stop_reason") or ev.get("stopReason") or "success"
                    sub = "success" if sr in ("end_turn", "stop", "success", "done") else sr
            out["result_subtype"] = sub
            if isinstance(ev.get("total_cost_usd"), (int, float)):
                out["cost_usd"] = float(ev["total_cost_usd"])
            nt = ev.get("num_turns")
            if isinstance(nt, int) and nt > out["turns"]:
                out["turns"] = nt
            if ev.get("model"):
                out["model"] = ev["model"]

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


# --- constitution -------------------------------------------------------------

_NO_UI = frozenset({
    "", "_not yet recorded_", "n/a", "none", "—", "-", "not applicable",
    "tbd", "todo",
})


def constitution_app_url(root: Path) -> str | None:
    """Value of the Commands table's app URL row, or None if missing."""
    path = root / "constitution.md"
    if not path.exists():
        return None
    for line in path.read_text(errors="replace").splitlines():
        if not re.search(r"\|\s*app URL\s*\|", line, re.I):
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c != ""]
        if len(cells) >= 2:
            return cells[1]
    return None


def has_ui(root: Path) -> bool:
    """True when constitution.md records a real http(s) or localhost app URL."""
    url = constitution_app_url(root)
    if url is None:
        return False
    u = url.strip().lower()
    if u in _NO_UI:
        return False
    return u.startswith(("http://", "https://", "localhost"))


# --- CRITIQUE.md --------------------------------------------------------------
# Schema: reference/critique-format.md. This parser is the mechanical twin.

CRITIQUE_FIELD = re.compile(r"\*\*([A-Za-z0-9][A-Za-z0-9 _-]*)\*\*\s*(.*)$", re.M)
CRITIQUE_FINDING = re.compile(r"^##\s+(F-\d+)\s*[—–-]\s*(.+)$", re.M)
ATTACKS_HELD = re.compile(
    r"^##\s+Attacks that did not land\s*$", re.M | re.I
)
VERDICT_VALUES = {"fit", "not-fit"}
RECRITIQUE_VALUES = {"not-required", "pending", "done"}
STATUS_VALUES = {"open", "fixed", "refuted"}
ATTACK_VALUES = {
    "traceability", "decomposition", "acceptance",
    "missing-work", "over-engineering", "other",
}


def _norm_token(val: str) -> str:
    return re.sub(r"\s+", "-", val.strip().lower()).strip("-")


def _fields(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in CRITIQUE_FIELD.finditer(block):
        out[m.group(1).strip().lower()] = m.group(2).strip()
    return out


def _section_nonempty(text: str) -> bool:
    body = text.strip()
    if not body:
        return False
    # Placeholder italics like "_none yet_" do not count.
    stripped = re.sub(r"[_*`#\-]", "", body).strip().lower()
    return stripped not in ("", "none", "n/a", "none yet")


def _parse_severity(val: str) -> int | None:
    m = re.search(r"[0-4]", val.strip())
    return int(m.group(0)) if m else None


def parse_critique(path: Path) -> dict:
    """Parse `.foreman/CRITIQUE.md`. Missing or malformed files still return a
    dict — `problems` lists every schema failure; `critique_is_clear` is the
    G2 exit predicate the router and dashboard must use."""
    result = {
        "exists": False,
        "path": path,
        "verdict": None,
        "re_critique": None,
        "date": "",
        "findings": [],
        "attacks_held": "",
        "problems": [],
    }
    if not path.exists():
        result["problems"] = ["CRITIQUE.md is missing"]
        return result

    text = path.read_text(errors="replace")
    result["exists"] = True

    held_m = ATTACKS_HELD.search(text)
    held_body = ""
    body_for_findings = text
    if held_m:
        held_body = text[held_m.end():]
        next_h = re.search(r"^##\s+", held_body, re.M)
        if next_h:
            held_body = held_body[:next_h.start()]
        body_for_findings = text[:held_m.start()]
        result["attacks_held"] = held_body.strip()

    headings = list(CRITIQUE_FINDING.finditer(body_for_findings))
    head = body_for_findings[:headings[0].start()] if headings else body_for_findings
    meta = _fields(head)
    verdict = _norm_token(meta.get("verdict", ""))
    if verdict in ("notfit", "unfit"):
        verdict = "not-fit"
    recrit = _norm_token(meta.get("re-critique", meta.get("re critique", "")))
    result["verdict"] = verdict if verdict in VERDICT_VALUES else None
    result["re_critique"] = recrit if recrit in RECRITIQUE_VALUES else None
    result["date"] = meta.get("date", "")

    for i, m in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body_for_findings)
        block = body_for_findings[m.end():end]
        f = _fields(block)
        attack = _norm_token(f.get("attack", ""))
        status_raw = _norm_token(f.get("status", ""))
        result["findings"].append({
            "id": m.group(1),
            "title": m.group(2).strip(),
            "severity": _parse_severity(f.get("severity", "")),
            "attack": attack if attack in ATTACK_VALUES else (attack or None),
            "evidence": f.get("evidence", "").strip(),
            "change": f.get("change", "").strip(),
            "status": status_raw if status_raw in STATUS_VALUES else None,
            "disposition": f.get("disposition", "").strip(),
        })

    result["problems"] = _critique_schema_problems(result)
    return result


def _critique_schema_problems(d: dict) -> list[str]:
    if not d["exists"]:
        return ["CRITIQUE.md is missing"]
    problems = []
    if d["verdict"] not in VERDICT_VALUES:
        problems.append("**Verdict** must be `fit` or `not-fit`")
    if d["re_critique"] not in RECRITIQUE_VALUES:
        problems.append(
            "**Re-critique** must be `not-required`, `pending`, or `done`"
        )
    if d["verdict"] == "not-fit" and not d["findings"]:
        problems.append("**Verdict** is `not-fit` but there are no findings")
    if d["verdict"] == "fit" and not _section_nonempty(d["attacks_held"]):
        problems.append(
            "**Verdict** is `fit` but **Attacks that did not land** is empty"
        )
    if d["verdict"] is None and not d["findings"] and not _section_nonempty(d["attacks_held"]):
        problems.append(
            "CRITIQUE.md is too thin — a verdict, findings or attacks that did not land are required"
        )
    for f in d["findings"]:
        prefix = f["id"]
        if f["severity"] is None:
            problems.append(f"{prefix}: **Severity** must be 0–4")
        if f["attack"] not in ATTACK_VALUES:
            problems.append(
                f"{prefix}: **Attack** must be one of {', '.join(sorted(ATTACK_VALUES))}"
            )
        if not f["evidence"]:
            problems.append(f"{prefix}: **Evidence** is empty")
        if not f["change"]:
            problems.append(f"{prefix}: **Change** is empty")
        if f["status"] not in STATUS_VALUES:
            problems.append(
                f"{prefix}: **Status** must be `open`, `fixed`, or `refuted`"
            )
    return problems


def critique_is_well_formed(d: dict) -> bool:
    return bool(d.get("exists")) and not d.get("problems")


def critique_is_clear(d: dict) -> bool:
    """G2 exit: well-formed, no open findings, re-critique not pending."""
    if not critique_is_well_formed(d):
        return False
    if d.get("re_critique") == "pending":
        return False
    return all(f.get("status") in ("fixed", "refuted") for f in d.get("findings", []))


def critique_problems(root: Path, require_clear: bool = False) -> list[str]:
    """Problems that `--check-critique` / `--g2-clear` report."""
    d = parse_critique(root / "CRITIQUE.md")
    problems = list(d["problems"])
    if require_clear and critique_is_well_formed(d) and not critique_is_clear(d):
        open_ids = [f["id"] for f in d["findings"] if f.get("status") == "open"]
        if open_ids:
            problems.append("open findings: " + ", ".join(open_ids))
        if d.get("re_critique") == "pending":
            problems.append("**Re-critique** is `pending` — re-invoke `/foreman:critique`")
    return problems


# --- layout ---------------------------------------------------------------
# .foreman/        tracked   — what the team reads: spec, tasks, decisions, status
# .foreman/work/   ignored   — what the agents use: sessions, memory, evidence
#
# One rule decides which side a file goes on: would a teammate reviewing the PR
# want it? Task files and decisions, yes. A session's churning status.json, no.

WORK = "work"


def work_dir(root: Path) -> Path:
    """The gitignored agent scratchpad inside .foreman/."""
    return root / WORK


def sessions_dir(root: Path) -> Path:
    return root / WORK / "sessions"


def all_sessions(root: Path) -> list[dict]:
    out = []
    sdir = sessions_dir(root)
    if sdir.is_dir():
        for d in sorted(p for p in sdir.iterdir() if p.is_dir()):
            st = load_json(d / "status.json")
            if st:
                out.append(st)
    return out
