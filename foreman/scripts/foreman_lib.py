"""Shared helpers for Foreman scripts. No third-party dependencies."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
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


MAX_ACTIVITY_EVENTS = 200
MAX_ACTIVITY_DETAIL = 2400


def _clip_activity(text: str, limit: int = MAX_ACTIVITY_DETAIL) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    keep = max(200, limit // 2 - 8)
    return text[:keep].rstrip() + "\n…\n" + text[-keep:].lstrip()


def _tool_title(name: str, inp: dict) -> str:
    name = name or "tool"
    if not isinstance(inp, dict):
        return name
    if name in ("Bash", "bash"):
        desc = (inp.get("description") or "").strip()
        cmd = (inp.get("command") or "").strip().splitlines()
        head = cmd[0] if cmd else ""
        if desc:
            return f"{name} · {desc}"
        return f"{name} · {head[:140]}" if head else name
    for key in ("path", "file_path", "target_file", "file", "url"):
        if inp.get(key):
            return f"{name} · {inp[key]}"
    if inp.get("pattern"):
        return f"{name} · {inp['pattern']}"
    if inp.get("skill"):
        return f"{name} · {inp['skill']}"
    return name


def _content_blocks(ev: dict) -> list:
    msg = ev.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
    else:
        content = ev.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [c for c in content if isinstance(c, dict)]
    return []


def parse_stream_activity(
    path: Path,
    max_events: int = MAX_ACTIVITY_EVENTS,
    max_detail: int = MAX_ACTIVITY_DETAIL,
) -> list[dict]:
    """Turn stream.jsonl into a UI feed. Drops init `system` frames.

    Each item: kind (text|tool|notice|result), tool, title, detail, ok.
    """
    events: list[dict] = []
    pending: dict[str, int] = {}
    if not path.exists():
        return events

    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return events

    for line in lines:
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = ev.get("type")
        if etype == "system":
            continue
        if etype == "rate_limit_event":
            events.append({
                "kind": "notice", "tool": "", "title": "rate limited",
                "detail": "", "ok": None,
            })
            continue
        if etype == "assistant":
            for block in _content_blocks(ev):
                btype = block.get("type")
                if btype == "text":
                    text = (block.get("text") or "").strip()
                    if text:
                        events.append({
                            "kind": "text", "tool": "", "title": "",
                            "detail": _clip_activity(text, max_detail),
                            "ok": None,
                        })
                elif btype == "tool_use":
                    name = str(block.get("name") or "tool")
                    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
                    tid = str(block.get("id") or "")
                    detail = inp.get("command") or inp.get("content") or ""
                    if not isinstance(detail, str):
                        detail = json.dumps(inp, ensure_ascii=False)[:max_detail]
                    item = {
                        "kind": "tool", "tool": name,
                        "title": _tool_title(name, inp),
                        "detail": _clip_activity(str(detail), max_detail),
                        "ok": None,
                    }
                    if tid:
                        pending[tid] = len(events)
                    events.append(item)
            continue
        if etype == "user":
            for block in _content_blocks(ev):
                if block.get("type") != "tool_result":
                    continue
                tid = str(block.get("tool_use_id") or "")
                body = block.get("content")
                if not isinstance(body, str):
                    body = json.dumps(body, ensure_ascii=False) if body else ""
                ok = not bool(block.get("is_error"))
                idx = pending.get(tid)
                clipped = _clip_activity(body, max_detail)
                if idx is not None and 0 <= idx < len(events):
                    events[idx]["ok"] = ok
                    prev = events[idx].get("detail") or ""
                    if clipped:
                        events[idx]["detail"] = (
                            (prev + "\n——\n" + clipped) if prev else clipped
                        )
                        events[idx]["detail"] = _clip_activity(
                            events[idx]["detail"], max_detail
                        )
                elif clipped:
                    events.append({
                        "kind": "tool", "tool": "", "title": "tool result",
                        "detail": clipped, "ok": ok,
                    })
            continue
        if etype in ("result", "end"):
            sub = ev.get("subtype") or ev.get("stop_reason") or ev.get("stopReason") or ""
            err = bool(ev.get("is_error"))
            body = ev.get("result")
            if not isinstance(body, str):
                body = ""
            title = sub or ("error" if err else "done")
            extra = []
            if isinstance(ev.get("total_cost_usd"), (int, float)):
                extra.append(f"${ev['total_cost_usd']:.2f}")
            if isinstance(ev.get("num_turns"), int):
                extra.append(f"{ev['num_turns']} turns")
            if extra:
                title = f"{title} · {' · '.join(extra)}"
            events.append({
                "kind": "result", "tool": "", "title": title,
                "detail": _clip_activity(body, max_detail),
                "ok": not err and sub not in (
                    "error_max_turns", "error_max_budget_usd", "error_during_execution"
                ),
            })

    if len(events) > max_events:
        events = events[-max_events:]
    return events


def pid_alive(pid: int | None) -> bool:
    try:
        value = int(pid or 0)
    except (TypeError, ValueError):
        return False
    if value <= 0:
        return False
    try:
        os.kill(value, 0)
    except OSError:
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


# --- worker git state ---------------------------------------------------------


class WorktreeError(RuntimeError):
    """A worker worktree cannot be created without risking lost or stale work."""


MANAGER_OWNED_PATHS = frozenset({
    ".foreman/log.md",
    ".foreman/STATUS.md",
    ".foreman/board.md",
    ".foreman/board.html",
})


def git_status_paths(cwd: Path) -> list[str]:
    """Changed paths in a worktree, including untracked files.

    Ignored files are deliberately absent. Foreman session evidence lives outside
    worker worktrees, so a non-empty result is product/task work that must be
    committed explicitly before a successor or integration can safely proceed.
    """
    cwd = Path(cwd)
    rc, out, _ = run(
        ["git", "-C", str(cwd), "status", "--porcelain=v1", "-z",
         "--untracked-files=all"],
        timeout=20,
    )
    if rc != 0:
        return []
    paths: list[str] = []
    parts = out.split("\0")
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if not entry:
            continue
        # porcelain v1: XY<space>path. Renames have a second NUL-delimited path.
        if len(entry) >= 4 and entry[2] == " ":
            paths.append(entry[3:])
            if entry[0] in "RC" or entry[1] in "RC":
                if i < len(parts) and parts[i]:
                    paths.append(parts[i])
                    i += 1
        else:
            paths.append(entry)
    return paths


BOOKKEEPING_COMMIT_PREFIX = "foreman: bookkeeping before spawning"


def _infer_worker_start(cwd: Path, base_commit: str | None = None) -> tuple[str, str]:
    """Best-effort start for pre-0.4 sessions that did not record one.

    Prefer the recorded base when available. Otherwise use the merge-base with
    the primary checkout. In both cases, advance over Foreman's synthetic launch
    commit so it is not mistaken for worker output or charged to committed paths.
    Returns (commit, source); an empty commit means provenance is unknowable.
    """
    anchor = ""
    source = "unknown"
    if base_commit:
        rc, resolved, _ = run(
            ["git", "-C", str(cwd), "rev-parse", f"{base_commit}^{{commit}}"],
            timeout=15,
        )
        if rc == 0:
            rc, _, _ = run(
                ["git", "-C", str(cwd), "merge-base", "--is-ancestor",
                 resolved.strip(), "HEAD"],
                timeout=15,
            )
            if rc == 0:
                anchor = resolved.strip()
                source = "inferred:base_commit"

    if not anchor:
        rc, raw, _ = run(
            ["git", "-C", str(cwd), "worktree", "list", "--porcelain"],
            timeout=20,
        )
        primary_head = ""
        if rc == 0:
            # Git lists the primary checkout first. A worker is a linked
            # worktree, so the first different path is the manager checkout.
            try:
                cwd_resolved = cwd.resolve()
            except OSError:
                cwd_resolved = cwd
            for record in raw.split("\n\n"):
                path = ""
                head = ""
                for line in record.splitlines():
                    if line.startswith("worktree "):
                        path = line[len("worktree "):]
                    elif line.startswith("HEAD "):
                        head = line[len("HEAD "):]
                if not path or not head:
                    continue
                try:
                    same = Path(path).resolve() == cwd_resolved
                except OSError:
                    same = Path(path) == cwd
                if not same:
                    primary_head = head
                    break
        if primary_head:
            rc, merged, _ = run(
                ["git", "-C", str(cwd), "merge-base", "HEAD", primary_head],
                timeout=15,
            )
            if rc == 0 and merged.strip():
                anchor = merged.strip()
                source = "inferred:primary-merge-base"

    if not anchor:
        return "", "unknown"

    rc, raw, _ = run(
        ["git", "-C", str(cwd), "rev-list", "--reverse", f"{anchor}..HEAD"],
        timeout=20,
    )
    if rc != 0:
        return "", "unknown"
    effective = anchor
    for commit in raw.splitlines():
        rc, subject, _ = run(
            ["git", "-C", str(cwd), "show", "-s", "--format=%s", commit],
            timeout=15,
        )
        if rc == 0 and subject.startswith(BOOKKEEPING_COMMIT_PREFIX):
            effective = commit
            continue
        break
    return effective, source


def worktree_snapshot(
    cwd: Path,
    start_commit: str | None = None,
    base_commit: str | None = None,
) -> dict:
    """Read-only git state used by the stop gate and supervisor.

    `commits_ahead=None` means the start could not be established. It must never
    be interpreted as zero worker commits.
    """
    cwd = Path(cwd)
    rc, head, _ = run(
        ["git", "-C", str(cwd), "rev-parse", "HEAD"], timeout=15
    )
    if rc != 0:
        return {
            "is_repo": False,
            "head": "",
            "dirty_paths": [],
            "commits_ahead": 0,
            "committed_paths": [],
            "effective_start_commit": "",
            "start_commit_source": "not-a-repository",
        }
    dirty = git_status_paths(cwd)
    effective_start = (start_commit or "").strip()
    start_source = "recorded" if effective_start else "unknown"
    if not effective_start:
        effective_start, start_source = _infer_worker_start(cwd, base_commit)
    ahead: int | None = None
    committed_paths: list[str] = []
    if effective_start:
        rc, _, _ = run(
            ["git", "-C", str(cwd), "merge-base", "--is-ancestor",
             effective_start, "HEAD"],
            timeout=15,
        )
        if rc != 0:
            effective_start = ""
            start_source = "invalid"
    if effective_start:
        rc, raw, _ = run(
            ["git", "-C", str(cwd), "rev-list", "--count",
             f"{effective_start}..HEAD"],
            timeout=15,
        )
        if rc == 0 and raw.strip().isdigit():
            ahead = int(raw.strip())
        rc, raw, _ = run(
            ["git", "-C", str(cwd), "diff", "--name-only", "-z",
             f"{effective_start}..HEAD"],
            timeout=20,
        )
        if rc == 0:
            committed_paths = [p for p in raw.split("\0") if p]
    return {
        "is_repo": True,
        "head": head.strip(),
        "dirty_paths": dirty,
        "commits_ahead": ahead,
        "committed_paths": committed_paths,
        "effective_start_commit": effective_start,
        "start_commit_source": start_source,
    }


def _git_or_raise(project: Path, args: list[str], *, timeout: int = 30) -> str:
    rc, out, err = run(["git", "-C", str(project), *args], timeout=timeout)
    if rc != 0:
        detail = (err or out).strip()
        raise WorktreeError(
            f"git {' '.join(args)} failed" + (f": {detail}" if detail else "")
        )
    return out.strip()


def _attached_worktree(project: Path, branch: str) -> Path | None:
    """Return the worktree currently holding `branch`, if any."""
    rc, out, _ = run(
        ["git", "-C", str(project), "worktree", "list", "--porcelain"],
        timeout=20,
    )
    if rc != 0:
        return None
    wanted = branch if branch.startswith("refs/heads/") else f"refs/heads/{branch}"
    current_path: Path | None = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line[len("worktree "):])
        elif line == f"branch {wanted}" and current_path is not None:
            return current_path
        elif not line.strip():
            current_path = None
    return None


def session_for_branch(root: Path, branch: str) -> dict | None:
    """Session status owning a worker branch."""
    for status in all_sessions(Path(root)):
        if status.get("branch") == branch:
            return status
    return None


def _bookkeeping_snapshot(project: Path, root: Path, base_commit: str,
                          message: str) -> str:
    """Snapshot current tracked Foreman inputs without moving HEAD or its index.

    This is used only for a root worker launched from project HEAD. A successor
    or tester uses its predecessor commit exactly; overlaying manager files there
    would replace the task evidence the predecessor just produced.
    """
    try:
        root_rel = root.resolve().relative_to(project.resolve()).as_posix()
    except ValueError as exc:
        raise WorktreeError(f"Foreman root {root} is outside project {project}") from exc

    fd, index_name = tempfile.mkstemp(prefix="foreman-index-")
    os.close(fd)
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = index_name
    try:
        def call(args: list[str]) -> str:
            try:
                p = subprocess.run(
                    ["git", "-C", str(project), *args],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise WorktreeError(f"git {' '.join(args)} failed: {exc}") from exc
            if p.returncode != 0:
                raise WorktreeError(
                    f"git {' '.join(args)} failed: {(p.stderr or p.stdout).strip()}"
                )
            return p.stdout.strip()

        call(["read-tree", base_commit])
        paths = []
        if root.exists():
            paths.append(root_rel)
        if (project / ".gitignore").exists():
            paths.append(".gitignore")
        if paths:
            add_paths = list(paths)
            # These files are manager-owned projections/activity. Workers do not
            # need a fresh uncommitted copy, and putting it in the synthetic
            # snapshot makes every later manager append look like a merge conflict.
            add_paths.extend(
                f":(exclude){root_rel}/{Path(p).name}"
                for p in MANAGER_OWNED_PATHS
                if p.startswith(".foreman/")
            )
            call(["add", "-A", "--", *add_paths])
        tree = call(["write-tree"])
    finally:
        try:
            Path(index_name).unlink()
        except OSError:
            pass

    base_tree = _git_or_raise(project, ["rev-parse", f"{base_commit}^{{tree}}"])
    if tree == base_tree:
        return base_commit
    return _git_or_raise(
        project,
        ["commit-tree", tree, "-p", base_commit, "-m", message],
    )


def prepare_worker_worktree(
    project: Path,
    root: Path,
    *,
    name: str,
    agent: str,
    harness: str,
    requested_base: str | None = None,
    use_worktree: bool = True,
) -> dict:
    """Create or validate a worker worktree and its predecessor ancestry.

    Testers default to `foreman/dev-<same suffix>`. Predecessor sessions must be
    stopped and clean; developer predecessors also need a commit beyond their own
    session start. These checks turn "your predecessor's work is preserved" from
    prompt text into a launch precondition.
    """
    project = Path(project).resolve()
    root = Path(root).resolve()
    is_git = run(
        ["git", "-C", str(project), "rev-parse", "--git-dir"], timeout=15
    )[0] == 0
    if not is_git:
        if use_worktree or requested_base:
            raise WorktreeError(f"{project} is not a git repository")
        return {
            "cwd": str(project), "branch": "", "base_ref": "",
            "base_commit": "", "start_commit": "",
            "lineage_start_commit": "", "base_session": "", "reused": False,
        }

    short_agent = agent.split(":")[-1]
    if not use_worktree and short_agent in (
        "foreman-developer", "foreman-tester"
    ):
        raise WorktreeError(
            f"{short_agent} requires an isolated git worktree; `--worktree no` "
            "cannot guarantee that the recorded base is the tree being changed or tested"
        )
    target_branch = f"foreman/{name}"
    existing_target = session_for_branch(root, target_branch)
    base_ref = (requested_base or "").strip()
    implicit_tester_base = False
    if not base_ref and existing_target:
        # Same-name retries resume the recorded branch even if manager HEAD moved
        # meanwhile. A new successor uses a new name plus explicit --base.
        base_ref = (
            existing_target.get("base_commit")
            or existing_target.get("base_ref")
            or "HEAD"
        )
    elif not base_ref and short_agent == "foreman-tester":
        if not name.startswith("test-") or len(name) <= len("test-"):
            raise WorktreeError(
                "tester names must start with `test-`, or pass `--base <developer-branch>`"
            )
        base_ref = "foreman/dev-" + name[len("test-"):]
        implicit_tester_base = True
    if not base_ref:
        base_ref = "HEAD"

    try:
        base_commit = _git_or_raise(project, ["rev-parse", f"{base_ref}^{{commit}}"])
    except WorktreeError as exc:
        if implicit_tester_base:
            raise WorktreeError(
                f"tester `{name}` expected developer branch `{base_ref}`, but it does "
                "not exist. Do not fall back to HEAD; pass the actual `--base` branch"
            ) from exc
        raise

    session_base_ref = (
        base_ref[len("refs/heads/"):]
        if base_ref.startswith("refs/heads/") else base_ref
    )
    predecessor = session_for_branch(root, session_base_ref)
    if session_base_ref.startswith("foreman/") and predecessor is None:
        raise WorktreeError(
            f"Foreman base `{base_ref}` has no matching session metadata under "
            f"{sessions_dir(root)}. Its live/dirty state and session commits cannot "
            "be verified; restore the status file or use a reviewed non-Foreman ref"
        )
    lineage_start = base_commit
    if predecessor:
        pred_name = predecessor.get("name") or base_ref
        pred_agent = (predecessor.get("agent") or "").split(":")[-1]
        pred_cwd_raw = predecessor.get("cwd") or ""
        if pid_alive(predecessor.get("pid")):
            raise WorktreeError(
                f"predecessor `{pred_name}` is still running; wait for DONE before "
                "branching from or removing its worktree"
            )
        if pred_cwd_raw and Path(pred_cwd_raw).is_dir():
            pred_cwd = Path(pred_cwd_raw)
            dirty = git_status_paths(pred_cwd)
            if dirty:
                sample = ", ".join(dirty[:8])
                more = f" (+{len(dirty) - 8} more)" if len(dirty) > 8 else ""
                raise WorktreeError(
                    f"predecessor `{pred_name}` has uncommitted work: {sample}{more}. "
                    "Commit the task-scoped files explicitly before spawning a successor"
                )
        recorded_lineage = (
            predecessor.get("lineage_start_commit")
            or predecessor.get("start_commit")
            or predecessor.get("base_commit")
        )
        if recorded_lineage:
            lineage_start = recorded_lineage
            rc, _, _ = run(
                ["git", "-C", str(project), "merge-base", "--is-ancestor",
                 lineage_start, base_commit],
                timeout=15,
            )
            if rc != 0:
                raise WorktreeError(
                    f"predecessor `{pred_name}` does not contain its recorded "
                    f"lineage start `{lineage_start}`; refusing an unverifiable handoff"
                )
            session_start = predecessor.get("start_commit") or lineage_start
            rc, _, _ = run(
                ["git", "-C", str(project), "merge-base", "--is-ancestor",
                 session_start, base_commit],
                timeout=15,
            )
            if rc != 0:
                raise WorktreeError(
                    f"predecessor `{pred_name}` does not contain its recorded "
                    f"session start `{session_start}`; refusing an unverifiable handoff"
                )
            rc, raw, _ = run(
                ["git", "-C", str(project), "rev-list", "--count",
                 f"{session_start}..{base_commit}"],
                timeout=20,
            )
            ahead = int(raw.strip()) if rc == 0 and raw.strip().isdigit() else 0
        else:
            # Pre-0.4 status files had no ancestry metadata. Infer the fork point,
            # but do not count Foreman's synthetic bookkeeping commit as worker
            # progress—the exact lost-session case this check exists to catch.
            lineage_start = _git_or_raise(
                project, ["merge-base", "HEAD", base_commit]
            )
            rc, raw, _ = run(
                ["git", "-C", str(project), "rev-list", "--reverse",
                 f"{lineage_start}..{base_commit}"],
                timeout=20,
            )
            ahead = 0
            for commit in raw.splitlines() if rc == 0 else []:
                subject = _git_or_raise(project, ["show", "-s", "--format=%s", commit])
                if subject.startswith(BOOKKEEPING_COMMIT_PREFIX) and ahead == 0:
                    lineage_start = commit
                else:
                    ahead += 1
        # Tester evidence is stored in its session directory, so a tester may
        # legitimately leave its branch at the exact developer commit. A
        # developer, however, must contribute a commit after *its own* start;
        # inherited commits from an earlier worker do not prove its work survived.
        if ahead == 0 and pred_agent != "foreman-tester":
            raise WorktreeError(
                f"predecessor `{pred_name}` has no worker commit beyond its session start "
                f"commit. Its work is not preserved on `{base_ref}`"
            )

    if not use_worktree:
        return {
            "cwd": str(project),
            "branch": "",
            "base_ref": base_ref,
            "base_commit": base_commit,
            "start_commit": base_commit,
            "lineage_start_commit": lineage_start,
            "base_session": predecessor.get("name", "") if predecessor else "",
            "reused": False,
        }

    branch = target_branch
    wt_parent = project / (".grok" if harness == "grok" else ".claude") / "worktrees"
    wt = wt_parent / f"foreman-{name}"

    # A same-name retry resumes its existing branch only when it still contains
    # the requested base. Never silently attach a stale branch to a new brief.
    branch_exists = run(
        ["git", "-C", str(project), "show-ref", "--verify", "--quiet",
         f"refs/heads/{branch}"],
        timeout=15,
    )[0] == 0
    attached = _attached_worktree(project, branch) if branch_exists else None
    if branch_exists:
        rc, _, _ = run(
            ["git", "-C", str(project), "merge-base", "--is-ancestor",
             base_commit, branch],
            timeout=15,
        )
        if rc != 0:
            raise WorktreeError(
                f"existing `{branch}` does not contain requested base `{base_ref}`; "
                "use a new session name"
            )
        if attached and attached.resolve() != wt.resolve():
            raise WorktreeError(
                f"`{branch}` is already checked out at {attached}; use that session "
                "or choose a new name"
            )
        if not wt.is_dir():
            wt.parent.mkdir(parents=True, exist_ok=True)
            _git_or_raise(project, ["worktree", "add", "-q", str(wt), branch], timeout=60)
        status = session_for_branch(root, branch) or {}
        start_commit = status.get("start_commit") or base_commit
        return {
            "cwd": str(wt),
            "branch": branch,
            "base_ref": base_ref,
            "base_commit": base_commit,
            "start_commit": start_commit,
            "lineage_start_commit": status.get("lineage_start_commit") or lineage_start,
            "base_session": (
                status.get("base_session")
                or (predecessor.get("name", "") if predecessor else "")
            ),
            "reused": True,
        }

    # Root workers need current uncommitted Foreman inputs. Successors and testers
    # use their predecessor commit exactly so its task evidence cannot be replaced
    # by the manager checkout's older copy.
    start_commit = base_commit
    if not requested_base and not implicit_tester_base and base_ref == "HEAD":
        start_commit = _bookkeeping_snapshot(
            project, root, base_commit,
            f"foreman: bookkeeping before spawning {name}",
        )
        lineage_start = start_commit

    wt.parent.mkdir(parents=True, exist_ok=True)
    _git_or_raise(
        project,
        ["worktree", "add", "-q", "-b", branch, str(wt), start_commit],
        timeout=60,
    )
    rc, _, _ = run(
        ["git", "-C", str(project), "merge-base", "--is-ancestor",
         base_commit, branch],
        timeout=15,
    )
    if rc != 0:
        raise WorktreeError(
            f"spawn verification failed: `{branch}` does not contain `{base_ref}`"
        )
    return {
        "cwd": str(wt),
        "branch": branch,
        "base_ref": base_ref,
        "base_commit": base_commit,
        "start_commit": start_commit,
        "lineage_start_commit": lineage_start,
        "base_session": predecessor.get("name", "") if predecessor else "",
        "reused": False,
    }


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

# [ \t]* not \s*: an empty **Disposition** must not swallow the next **Field**.
CRITIQUE_FIELD = re.compile(r"\*\*([A-Za-z0-9][A-Za-z0-9 _-]*)\*\*[ \t]*(.*)$", re.M)
CRITIQUE_FINDING = re.compile(r"^##\s+(F-\d+)\s*[—–-]\s*(.+)$", re.M)
ATTACKS_HELD = re.compile(
    r"^##\s+Attacks that did not land\s*$", re.M | re.I
)
CITES_IDS = re.compile(r"F-\d+", re.I)
FID_NUM = re.compile(r"(\d+)")
VERDICT_VALUES = {"fit", "not-fit"}
RECRITIQUE_VALUES = {"not-required", "pending", "done"}
STATUS_VALUES = {"open", "fixed", "refuted"}
ATTACK_VALUES = {
    "traceability", "decomposition", "acceptance",
    "missing-work", "over-engineering", "other",
}
# Graph-changing attacks: a severity-3 fix here may buy another G2a round.
# acceptance / over-engineering / other are manager-verifiable and do not.
RECITIQUE_FORCE_ATTACKS = frozenset({
    "decomposition", "missing-work", "traceability",
})
MAX_G2A_ROUNDS = 4
MAX_G2A_SCHEMA_RETRIES = 3
G2_STATE_FILE = "g2.json"


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


def _parse_round(val: str, recrit: str | None = None) -> int:
    """**Round** 1–4. Explicit values clamp to the cap.

    Missing: `not-required`/`pending` → 1; `done` → 2 (a recritique already
    completed). An in-flight file from before **Round** existed must not reset
    the cap to zero.
    """
    m = re.search(r"\d+", (val or "").strip())
    if m:
        n = int(m.group(0))
        if n < 1:
            return 1
        return min(n, MAX_G2A_ROUNDS)
    if recrit == "done":
        return 2
    return 1


def _fid_num(fid: str) -> int | None:
    m = FID_NUM.search(fid or "")
    return int(m.group(1)) if m else None


def _parse_cites(val: str) -> list[str]:
    return CITES_IDS.findall(val or "")


def critique_round(d: dict) -> int:
    r = d.get("round")
    return r if isinstance(r, int) and r >= 1 else 1


def finding_forces_recritique(f: dict) -> bool:
    """A closed-as-fixed finding that is allowed to set **Re-critique** pending."""
    if f.get("status") != "fixed":
        return False
    sev = f.get("severity")
    if sev == 4:
        return True
    return sev == 3 and f.get("attack") in RECITIQUE_FORCE_ATTACKS


def parse_critique(path: Path) -> dict:
    """Parse `.foreman/CRITIQUE.md`. Missing or malformed files still return a
    dict — `problems` lists every schema failure; `critique_is_clear` is the
    G2 exit predicate the router and dashboard must use."""
    result = {
        "exists": False,
        "path": path,
        "verdict": None,
        "re_critique": None,
        "round": 1,
        "round_explicit": False,
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
    round_raw = meta.get("round", "")
    result["round_explicit"] = bool(re.search(r"\d+", round_raw or ""))
    result["round"] = _parse_round(round_raw, result["re_critique"])
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
            "cites": _parse_cites(f.get("cites", "")),
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
    round_n = critique_round(d)
    # Only enforce Cites when the critic wrote **Round** 2+. Inferring round
    # from a pre-field `done` file must not fail-open into a spawn-on-malformed
    # loop.
    if round_n >= 2 and d.get("round_explicit"):
        by_num = {_fid_num(x["id"]): x["id"] for x in d["findings"]
                  if _fid_num(x["id"]) is not None}
        for f in d["findings"]:
            if f["status"] != "open":
                continue
            prefix = f["id"]
            cites = f.get("cites") or []
            if not cites:
                problems.append(
                    f"{prefix}: **Cites** is required on round {round_n}+ "
                    "(name an earlier finding whose fix this attacks)"
                )
                continue
            self_n = _fid_num(prefix)
            for c in cites:
                n = _fid_num(c)
                if n not in by_num:
                    problems.append(f"{prefix}: **Cites** {c} does not exist")
                elif self_n is not None and n >= self_n:
                    problems.append(
                        f"{prefix}: **Cites** must name an earlier finding, not {c}"
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
            rnd = critique_round(d)
            if rnd >= MAX_G2A_ROUNDS:
                problems.append(
                    f"**Re-critique** is `pending` at round cap ({rnd}/{MAX_G2A_ROUNDS}) "
                    "— set it to `done` and close remaining findings. Do not spawn "
                    "another critic"
                )
            else:
                problems.append(
                    f"**Re-critique** is `pending` (round {rnd}/{MAX_G2A_ROUNDS}) "
                    "— run `--g2-spawn` and invoke `/foreman:critique` only if it exits 0"
                )
    return problems


def load_g2_state(root: Path) -> dict:
    """Counted G2a spawns / schema retries. Lives in gitignored work/."""
    data = load_json(root / "work" / G2_STATE_FILE, default={})
    return {
        "spawns": int(data.get("spawns") or 0),
        "schema_retries": int(data.get("schema_retries") or 0),
    }


def save_g2_state(root: Path, state: dict) -> None:
    save_json(root / "work" / G2_STATE_FILE, {
        "spawns": int(state.get("spawns") or 0),
        "schema_retries": int(state.get("schema_retries") or 0),
    })


def should_spawn_critic(root: Path, count: bool = False) -> tuple[bool, str]:
    """Whether G2a should run. The manager must not interpret this itself.

    Exit-0 reasons are spawn; exit-1 reasons are skip. When `count` is true and
    the decision is spawn, persist the increment to work/g2.json so a manager
    that forgets **Round** still cannot fork past MAX_G2A_ROUNDS, and a thin
    file cannot be retried past MAX_G2A_SCHEMA_RETRIES.
    """
    state = load_g2_state(root)
    if state["spawns"] >= MAX_G2A_ROUNDS:
        return False, (
            f"G2a skip: spawn cap reached ({state['spawns']}/{MAX_G2A_ROUNDS}) "
            "— set **Re-critique** to `done` and close remaining findings"
        )

    d = parse_critique(root / "CRITIQUE.md")
    if not d["exists"]:
        if count:
            state["spawns"] += 1
            state["schema_retries"] = 0
            save_g2_state(root, state)
        return True, "G2a spawn: CRITIQUE.md is missing"

    if not critique_is_well_formed(d):
        if state["schema_retries"] >= MAX_G2A_SCHEMA_RETRIES:
            return False, (
                f"G2a skip: schema retry cap ({MAX_G2A_SCHEMA_RETRIES}) — stop "
                "and report. Do not keep forking on a thin file"
            )
        if count:
            state["schema_retries"] += 1
            save_g2_state(root, state)
        why = d["problems"][0] if d.get("problems") else "not well-formed"
        return True, f"G2a spawn: CRITIQUE.md is not well-formed — {why}"

    if d.get("re_critique") == "pending":
        rnd = critique_round(d)
        if rnd >= MAX_G2A_ROUNDS:
            return False, (
                f"G2a skip: round cap reached ({rnd}/{MAX_G2A_ROUNDS}) — set "
                "**Re-critique** to `done` and close remaining findings. Do not spawn"
            )
        if count:
            state["spawns"] += 1
            state["schema_retries"] = 0
            save_g2_state(root, state)
        return True, f"G2a spawn: **Re-critique** pending (round {rnd}/{MAX_G2A_ROUNDS})"

    if critique_is_clear(d):
        return False, "G2a skip: G2 is clear"
    return False, (
        "G2a skip: well-formed and not pending — G2b disposition, do not spawn"
    )


def _this_round_findings(d: dict) -> list[dict]:
    """Findings introduced in the round just completed.

    Round 1 has no **Cites**. Later rounds must cite, so cited findings are
    the new ones. A pre-**Round** `done` file with no cites is treated as
    having nothing new — otherwise historical F-01 keeps buying forks.
    """
    findings = d.get("findings") or []
    cited = [f for f in findings if f.get("cites")]
    if cited:
        return cited
    if critique_round(d) <= 1:
        return list(findings)
    return []


def may_set_pending(d: dict) -> tuple[bool, str]:
    """Whether G2b may rewind Re-critique to pending. `done` is not a toggle."""
    if not critique_is_well_formed(d):
        return False, "CRITIQUE.md is not well-formed"
    if any(f.get("status") == "open" for f in d.get("findings", [])):
        return False, "open findings remain — disposition them first"
    rnd = critique_round(d)
    if rnd >= MAX_G2A_ROUNDS:
        return False, (
            f"round cap ({rnd}/{MAX_G2A_ROUNDS}) — leave **Re-critique** `done`"
        )
    if d.get("re_critique") == "pending":
        return False, "already pending"
    forced = [f["id"] for f in _this_round_findings(d) if finding_forces_recritique(f)]
    if not forced:
        return False, (
            "no severity-4 or graph-changing severity-3 fixes this round "
            "— do not set pending"
        )
    return True, (
        f"may set pending for {', '.join(forced)} "
        f"(round {rnd}/{MAX_G2A_ROUNDS})"
    )


# --- work/memory.md -----------------------------------------------------------
# Gitignored running state. Prompt "keep this current" is not enough — a G0
# label survived six G2 rounds in the wild. **Gate** vs artefacts is the check.

GATE_TOKEN = re.compile(r"G[0-6]", re.I)
MEMORY_GATE_NONE = frozenset({
    "", "_none_", "none", "n/a", "-", "—", "_unknown_",
})


def infer_gate(root: Path) -> str:
    """Where the router would go, from artefacts. Same table as `/foreman` Step 1."""
    req = root / "REQUIREMENTS.md"
    if not req.is_file():
        return "G0"
    text = req.read_text(errors="replace")
    if "[NEEDS CLARIFICATION]" in text:
        return "G0"
    tasks = all_tasks(root)
    if not tasks:
        return "G1"
    if not critique_is_clear(parse_critique(root / "CRITIQUE.md")):
        return "G2"
    if all(t.get("status") == "done" for t in tasks):
        return "G6"
    return "G3"


def _norm_memory_gate(val: str) -> str | None:
    raw = (val or "").strip()
    if raw.lower() in MEMORY_GATE_NONE:
        return None
    m = GATE_TOKEN.search(raw)
    if not m:
        return None
    g = m.group(0).upper()
    if g in ("G4", "G5"):
        return "G3"
    return g


def parse_memory(path: Path) -> dict:
    """Head fields of work/memory.md. Missing file is a dict, not an exception."""
    result = {
        "exists": False,
        "path": path,
        "gate": None,
        "last_updated": "",
    }
    if not path.exists():
        return result
    result["exists"] = True
    text = path.read_text(errors="replace")
    head = text[: text.find("\n## ")] if "\n## " in text else text
    fields = _fields(head)
    result["last_updated"] = fields.get("last updated", "")
    result["gate"] = _norm_memory_gate(fields.get("gate", ""))
    return result


def memory_problems(root: Path) -> list[str]:
    """Stale or missing running state. `--check-memory` reports these."""
    expected = infer_gate(root)
    d = parse_memory(root / "work" / "memory.md")
    if not d["exists"]:
        return [f"memory.md is missing (expected **Gate** {expected})"]
    if d["gate"] is None:
        return [
            f"**Gate** is missing (expected {expected}) — rewrite before routing"
        ]
    if d["gate"] != expected:
        return [
            f"**Gate** is {d['gate']} but artefacts are at {expected} — "
            "rewrite memory.md before routing"
        ]
    return []


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
