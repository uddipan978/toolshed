#!/usr/bin/env python3
"""sidecar.py — write the evidence sidecar for one screenshot. A shot without a
sidecar does not count at g4: if you did not record how it was taken, you did not
prove anything.

Usage:
  sidecar.py PNG --url URL --viewport WxH --theme light|dark [--dpr N] [--a11y FILE]

Writes PNG.json next to the image: url, viewport, theme, dpr, build SHA (git),
sha256 of the image and of the a11y snapshot if given. Exit 0 ok · 2 error.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_sha(cwd):
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           text=True, cwd=cwd, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else "NOT-A-GIT-REPO"
    except Exception:
        return "UNKNOWN"


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    png = Path(argv[0])
    if not png.is_file():
        print(f"no such image: {png}")
        return 2
    args = dict(zip(argv, argv[1:]))
    side = {
        "image": png.name,
        "url": args.get("--url", "UNRECORDED"),
        "viewport": args.get("--viewport", "UNRECORDED"),
        "theme": args.get("--theme", "UNRECORDED"),
        "dpr": args.get("--dpr", "1"),
        "build_sha": git_sha(png.parent),
        "sha256": sha256(png),
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    a11y = args.get("--a11y")
    if a11y and Path(a11y).is_file():
        side["a11y_snapshot"] = Path(a11y).name
        side["a11y_sha256"] = sha256(a11y)
    out = png.with_name(png.name + ".json")
    out.write_text(json.dumps(side, indent=2))
    print(f"sidecar: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
