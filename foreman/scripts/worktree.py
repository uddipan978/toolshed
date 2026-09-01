#!/usr/bin/env python3
"""Prepare and inspect Foreman worker worktrees.

The spawn adapters share this implementation so Claude and Grok cannot drift on
branch ancestry or dirty-predecessor safety.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import (  # noqa: E402
    WorktreeError,
    prepare_worker_worktree,
    worktree_snapshot,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--project", required=True)
    prep.add_argument("--root", required=True)
    prep.add_argument("--name", required=True)
    prep.add_argument("--agent", required=True)
    prep.add_argument("--harness", choices=("claude", "grok"), required=True)
    prep.add_argument("--base")
    prep.add_argument("--worktree", choices=("yes", "no"), default="yes")

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--cwd", required=True)
    inspect.add_argument("--start-commit")
    inspect.add_argument("--base-commit")

    args = ap.parse_args()
    try:
        if args.command == "prepare":
            result = prepare_worker_worktree(
                Path(args.project),
                Path(args.root),
                name=args.name,
                agent=args.agent,
                harness=args.harness,
                requested_base=args.base,
                use_worktree=args.worktree == "yes",
            )
        else:
            result = worktree_snapshot(
                Path(args.cwd), args.start_commit, args.base_commit
            )
    except WorktreeError as exc:
        print(f"worktree.py: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
