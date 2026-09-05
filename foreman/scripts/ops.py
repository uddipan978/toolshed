"""Shared coordination primitives. Task Markdown remains the source of truth."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import re
from pathlib import Path

from foreman_lib import all_tasks, atomic_write, load_json, pid_alive, read_stream, run, save_json


class WorkflowError(ValueError):
    pass


@contextmanager
def lock(root: Path, name: str = "state", blocking: bool = True):
    path = root / "work" / "locks" / f"{name}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as exc:
            raise WorkflowError(f"another {name} operation is running") from exc
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", value):
        raise WorkflowError(f"invalid identifier: {value!r}")
    return value


def read_document(path: Path) -> dict:
    import json
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkflowError(f"{path} must contain a JSON object")
    return data


def task_index(root: Path) -> dict:
    tasks = all_tasks(root)
    problems = [f"{t['path'].name}: {p}" for t in tasks for p in t["problems"]]
    if problems:
        raise WorkflowError("invalid task files:\n- " + "\n- ".join(problems))
    return {t["id"]: t for t in tasks}


def brief_task(root: Path, brief: str, cwd: Path | None = None) -> dict:
    refs = re.findall(r"^\*\*Task file\*\*\s*([^\n]+)$", brief, re.M)
    if len(refs) != 1:
        raise WorkflowError("brief needs exactly one **Task file**")
    path = Path(refs[0].strip().strip("`"))
    if not path.is_absolute():
        path = (cwd or root.parent) / path
    if cwd:
        try:
            path = root.parent / path.resolve().relative_to(cwd.resolve())
        except ValueError as exc:
            raise WorkflowError("task file is outside the worker checkout") from exc
    matches = [t for t in task_index(root).values() if t["path"].resolve() == path.resolve()]
    if len(matches) != 1:
        raise WorkflowError(f"brief must name one canonical task under {root}/modules: {path}")
    return matches[0]


def set_field(text: str, field: str, value: str) -> str:
    head, sep, body = text.partition("\n## ")
    pattern = re.compile(r"(\*\*" + re.escape(field) + r"\*\*\s*)([^*\n]*?)((?:\s*·\s*)?(?=\*\*|$))", re.M)
    def replace(m):
        return m[1] + value + m[3]
    head, count = pattern.subn(replace, head)
    if count > 1:
        raise WorkflowError(f"duplicate {field} field; repair the header before writing")
    if not count:
        head = head.rstrip() + f"\n**{field}** {value}\n"
    return head + sep + body


def update_session(sdir: Path, **fields) -> dict:
    # Both hooks and the supervisor update status; merge under the same lock.
    root = sdir.parent.parent.parent if sdir.parent.name == "sessions" and sdir.parent.parent.name == "work" else sdir
    with lock(root, "session-" + identifier(sdir.name)):
        status = read_document(sdir / "status.json") if (sdir / "status.json").exists() else {}
        status.update(fields)
        save_json(sdir / "status.json", status)
        return status


def session_alive(status: dict) -> bool:
    """A runner's exit marker wins over a recycled PID. Older sessions use PID."""
    if status.get("integrated_at") or status.get("retired_at"):
        return False
    root = status.get("root")
    name = status.get("name")
    if root and name:
        sdir = Path(root) / "work" / "sessions" / name
        if (sdir / "exit.json").is_file():
            return False
        if status.get("runner_pid"):
            if not pid_alive(status["runner_pid"]):
                return False
            expected = status.get("runner_identity")
            current = process_identity(status["runner_pid"]) if expected else None
            return current is None or current == expected
        if read_stream(sdir / "stream.jsonl")["finished"]:
            # A final stream frame does not guarantee the process has exited.
            return pid_alive(status.get("pid"))
    return pid_alive(status.get("pid"))


def process_identity(pid: int) -> str | None:
    rc, out, _ = run(["ps", "-p", str(int(pid)), "-o", "lstart="], timeout=5)
    return out.strip() if rc in (0, 1) else None


def mark_views_dirty(root: Path) -> None:
    atomic_write(root / "work" / "views-dirty", "refresh required\n")
