#!/usr/bin/env python3
"""Durable supervisor outbox. Delivery is acknowledged after manager disposition."""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

from foreman_lib import load_json, save_json
from ops import WorkflowError, identifier, lock, read_document


def publish(root: Path, session: str, kind: str, detail: str, generation: str = "") -> dict:
    key = hashlib.sha256(f"{session}\n{kind}\n{generation}".encode()).hexdigest()[:20]
    path = root / "work" / "events" / f"{key}.json"
    with lock(root, "events"):
        if path.is_file():
            return read_document(path)
        item = {"id": key, "session": session, "kind": kind, "detail": detail,
                "created_at": time.time(), "acknowledged_at": None}
        save_json(path, item)
        return item


def pending(root: Path, prefix: str = "") -> list[dict]:
    result = []
    for path in (root / "work" / "events").glob("*.json"):
        item = load_json(path)
        if item and not item.get("acknowledged_at") and item.get("session", "").startswith(prefix):
            result.append(item)
    return sorted(result, key=lambda e: e["created_at"])


def acknowledge(root: Path, event_id: str, disposition: str) -> None:
    if not disposition.strip():
        raise WorkflowError("acknowledgement requires a disposition")
    with lock(root, "events"):
        path = root / "work" / "events" / f"{identifier(event_id)}.json"
        item = read_document(path)
        item.update(acknowledged_at=time.time(), disposition=disposition)
        save_json(path, item)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".foreman")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--ack")
    ap.add_argument("--disposition", default="")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    try:
        if args.ack:
            acknowledge(root, args.ack, args.disposition)
        else:
            for item in pending(root, args.prefix):
                print(f"{item['id']} {item['kind']} {item['session']} — {item['detail']}")
    except WorkflowError as exc:
        sys.exit(str(exc))
