#!/usr/bin/env python3
"""Preserve uncommitted worker files without asserting that its branch has them."""
from __future__ import annotations

import hashlib
import os
import shutil
import time
from pathlib import Path

from foreman_lib import atomic_write, git_status_paths, load_json, run, save_json


def preserve(sdir: Path, status: dict) -> dict:
    cwd = Path(status.get("cwd") or "")
    if not status.get("cwd") or not cwd.is_dir():
        return {"error": "worktree missing; recovery cannot reconstruct lost files"}
    paths = git_status_paths(cwd)
    if not paths:
        return {"paths": [], "preserved": True}
    manifest = {"paths": [], "skipped": [], "cwd": str(cwd), "created_at": time.time()}
    digest = hashlib.sha256()
    total = 0
    for rel in paths:
        path = cwd / rel
        if path.is_symlink() or not path.resolve().is_relative_to(cwd.resolve()):
            manifest["skipped"].append(rel)
            continue
        if path.is_file():
            size = path.stat().st_size
            if size > 20 * 1024**2 or total + size > 100 * 1024**2:
                manifest["skipped"].append(rel)
                continue
            total += size
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        elif not path.exists():
            checksum = "deleted"
        else:
            manifest["skipped"].append(rel)
            continue
        digest.update(f"{rel}\n{checksum}\n".encode())
        manifest["paths"].append({"path": rel, "sha256": checksum})
    key = digest.hexdigest()[:20]
    dest = sdir / "recovery" / key
    if (dest / "manifest.json").exists():
        return load_json(dest / "manifest.json")
    for item in manifest["paths"]:
        if item["sha256"] == "deleted":
            continue
        target = dest / "files" / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cwd / item["path"], target)
        os.chmod(target, 0o600)
        if hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
            manifest["skipped"].append(item["path"] + " changed during snapshot")
    rc, patch, error = run(["git", "-C", str(cwd), "diff", "--binary", "HEAD"], timeout=30)
    if rc == 0:
        atomic_write(dest / "tracked.patch", patch)
    else:
        manifest["skipped"].append("tracked diff failed: " + error)
    manifest["preserved"] = not manifest["skipped"]
    manifest["location"] = str(dest)
    save_json(dest / "manifest.json", manifest)
    save_json(sdir / "recovery" / "latest.json", manifest)
    return manifest
