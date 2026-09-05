#!/usr/bin/env python3
"""Own a worker process and persist its exit independently of stream notifications."""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from foreman_lib import save_json
from ops import process_identity, update_session


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session-dir", required=True)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    sdir = Path(args.session_dir)
    rc = 127
    child = None
    def forward(signum, _frame):
        if child and child.poll() is None:
            child.send_signal(signum)
    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    try:
        child = subprocess.Popen(command)
        update_session(sdir, pid=child.pid, runner_pid=os.getpid(), runner_identity=process_identity(os.getpid()), state="running")
        rc = child.wait()
    except OSError as exc:
        print(f"worker launch failed: {exc}", file=sys.stderr)
    finally:
        save_json(sdir / "exit.json", {"returncode": rc, "exited_at": time.time()})
        status = update_session(sdir, exited_at=time.time(), returncode=rc)
        from checkpoint import preserve
        if status.get("branch"):
            recovery = preserve(sdir, status)
            update_session(sdir, recovery=recovery)
    return rc


if __name__ == "__main__":
    sys.exit(main())
