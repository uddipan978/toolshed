#!/usr/bin/env python3
"""Regenerate every projection together; retain a repair marker on interruption."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from foreman_lib import atomic_write, load_json, save_json
from ops import lock, mark_views_dirty


def refresh(root: Path) -> None:
    from board import render, render_status
    from dashboard import write_html
    with lock(root, "views"):
        mark_views_dirty(root)
        from runtime_memory import sync
        sync(root)
        for filename, body in (("board.md", render(root)), ("STATUS.md", render_status(root))):
            path = root / filename
            if not path.is_file() or path.read_text() != body:
                atomic_write(path, body)
        write_html(root, root / "board.html", static=True)
        write_html(root, root / "work" / "dashboard.html", static=False)
        save_json(root / "work" / "views.json", {"refreshed_at": time.time()})
        (root / "work" / "views-dirty").unlink(missing_ok=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".foreman")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.exit(f"no such directory: {root}")
    refresh(root)
    print("refreshed STATUS.md, board.md, board.html and work/dashboard.html")
