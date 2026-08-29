#!/usr/bin/env python3
"""probe.py — record what THIS host can actually do, before promising anything.

Writes .hld/work/host.json and prints it. Every gate reads this; a missing capability
becomes COULD-NOT-RUN with the probe as evidence — never a crash, never an install.

Usage: probe.py [--root DIR] [--dry]      Stdlib only. Exit 0 always.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FOREMAN_GLOBS = [
    "~/.claude/plugins/cache/*/*/*/scripts/verify_gate.py",
    "~/.claude/plugins/cache/*/*/scripts/verify_gate.py",
    "~/.claude/marketplace-src/*/foreman/scripts/verify_gate.py",
    "~/.grok/installed-plugins/*/foreman/scripts/verify_gate.py",
    "~/.grok/installed-plugins/*/*/foreman/scripts/verify_gate.py",
]


def which_version(cmd, args=("--version",)):
    path = shutil.which(cmd)
    if not path:
        return None
    try:
        r = subprocess.run([cmd, *args], capture_output=True, text=True, timeout=10)
        return (r.stdout or r.stderr).strip().splitlines()[0][:60]
    except Exception:
        return "present (version check failed)"


def find_runnable_foreman():
    """Runnable = its verify_gate.py --help exits 0. A half-install counts as absent."""
    cands = []
    env = os.environ.get("HLD_FOREMAN_ROOT")
    if env:
        cands.append(Path(env).expanduser() / "scripts" / "verify_gate.py")
    home = Path.home()
    for g in FOREMAN_GLOBS:
        cands += sorted(home.glob(g.replace("~/", "")))
    for c in cands:
        if not c.is_file():
            continue
        try:
            r = subprocess.run([sys.executable, str(c), "--help"],
                               capture_output=True, timeout=8)
            if r.returncode == 0:
                return str(c.parent.parent)
        except Exception:
            continue
    return None


def detect_host():
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return "claude"
    if os.environ.get("GROK_PLUGIN_ROOT") or os.environ.get("GROK_SESSION_ID"):
        return "grok"
    if os.environ.get("CODEX_HOME") or os.environ.get("CODEX_SANDBOX"):
        return "codex"
    return "unknown"


def probe():
    host = detect_host()
    from slop import find_detect  # same directory
    return {
        "host": host,
        "python": sys.version.split()[0],
        "node": which_version("node"),
        "git": which_version("git"),
        "playwright": which_version("playwright"),
        "detect_mjs": str(find_detect()) if find_detect() else None,
        "foreman_root": find_runnable_foreman(),
        "subagents": "likely" if host == "claude" else "unknown",
        "hooks": host in ("claude", "grok"),
        "network": "untested",
    }


def main(argv):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    info = probe()
    root = Path(argv[argv.index("--root") + 1]) if "--root" in argv else Path.cwd()
    print(json.dumps(info, indent=2))
    if "--dry" not in argv:
        hld = root / ".hld" if root.name != ".hld" else root
        work = hld / "work"
        if hld.is_dir():
            work.mkdir(exist_ok=True)
            (work / "host.json").write_text(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
