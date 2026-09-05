"""Refresh machine facts in memory without replacing the manager's working notes."""
from __future__ import annotations

import re
import time
from pathlib import Path

from foreman_lib import all_sessions, atomic_write, infer_gate
from ops import lock


def sync(root: Path) -> None:
    with lock(root, "memory"):
        path = root / "work" / "memory.md"
        text = path.read_text() if path.is_file() else "# Working memory\n\n"
        gate = infer_gate(root)
        if re.search(r"^\*\*Gate\*\*[^\n]*$", text, re.M):
            text = re.sub(r"^\*\*Gate\*\*[^\n]*$", f"**Gate** {gate}", text, flags=re.M)
        else:
            text = text.rstrip() + f"\n\n**Gate** {gate}\n"
        rows = ["<!-- foreman:runtime:start -->", "## Verified runtime facts", "",
                f"Last sweep/view refresh: {time.strftime('%Y-%m-%d %H:%M:%S')}", "",
                "Pending events: run `events.py`; prose notes are not proof of preserved branches.", ""]
        active = [s for s in all_sessions(root) if not s.get("integrated_at") and not s.get("retired_at")]
        active.sort(key=lambda s: (s.get("state", "").split(":")[0] in ("starting", "running", "quiet", "stuck", "overdue"), s.get("started_at", 0)), reverse=True)
        rows.append(f"{len(active)} unresolved sessions; showing at most 20 recent/live entries.\n")
        for status in active[:20]:
            rows.append(f"- {status.get('name')}: {status.get('state', 'unknown')}; "
                        f"worker commits={status.get('commits_ahead', 'unknown')}; "
                        f"uncommitted={status.get('uncommitted_count', 'unknown')}; cwd={status.get('cwd', 'unknown')}")
        rows += ["", "<!-- foreman:runtime:end -->"]
        block = "\n".join(rows)
        pattern = r"<!-- foreman:runtime:start -->.*?<!-- foreman:runtime:end -->"
        if re.search(pattern, text, re.S):
            text = re.sub(pattern, lambda _: block, text, flags=re.S)
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
        atomic_write(path, text)
