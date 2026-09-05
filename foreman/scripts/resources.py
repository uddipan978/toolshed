"""Local RAM/CPU admission control. Pressure pauses launches, never kills work."""
from __future__ import annotations

import os
import platform
import re
from pathlib import Path

from foreman_lib import run


def sample() -> dict:
    cores = os.cpu_count() or 1
    out = {"known": False, "cores": cores, "cpu_pct": None, "available_mb": None,
           "available_pct": None}
    if platform.system() == "Darwin":
        rc, mem, _ = run(["memory_pressure", "-Q"], timeout=10)
        match = re.search(r"System-wide memory free percentage:\s*(\d+)%", mem)
        rc_total, total, _ = run(["sysctl", "-n", "hw.memsize"], timeout=10)
        if rc == 0 and match and rc_total == 0 and total.strip().isdigit():
            pct = float(match[1])
            out.update(available_pct=pct, available_mb=int(total.strip()) * pct / 100 / 1024**2)
    elif platform.system() == "Linux":
        try:
            mem = Path("/proc/meminfo").read_text()
            fields = {k: int(v) for k, v in re.findall(r"^(\w+):\s+(\d+)", mem, re.M)}
            available = fields["MemAvailable"]
            out.update(available_mb=available / 1024,
                       available_pct=100 * available / fields["MemTotal"])
        except (OSError, KeyError, ZeroDivisionError):
            pass
    # ps %cpu is averaged over process lifetime, load captures recent contention.
    # Report the conservative maximum and label it as pressure, not instantaneous CPU.
    rc, raw, _ = run(["ps", "-A", "-o", "%cpu="], timeout=10)
    if rc == 0:
        try:
            busy = sum(float(v) for v in raw.split()) / cores
            load = os.getloadavg()[0] * 100 / cores
            out["cpu_pct"] = round(min(100, max(busy, load)), 1)
        except (ValueError, OSError):
            pass
    out["known"] = out["cpu_pct"] is not None and out["available_mb"] is not None
    return out


def admission(metrics: dict, limits: dict, previous: dict | None = None) -> dict:
    """Hysteresis keeps launches from bouncing around the high watermark."""
    previous = previous or {}
    if not metrics.get("known"):
        return {"paused": True, "reason": "resource metrics unavailable; cannot safely add workers", "metrics": metrics}
    max_cpu = float(limits.get("cpu_pause_pct", 85))
    min_mb = float(limits.get("min_available_mb", 1024))
    min_pct = float(limits.get("min_available_pct", 15))
    margin_cpu = 10 if previous.get("paused") else 0
    margin_ram = 256 if previous.get("paused") else 0
    margin_pct = 5 if previous.get("paused") else 0
    reasons = []
    if metrics["cpu_pct"] >= max_cpu - margin_cpu:
        reasons.append(f"CPU pressure {metrics['cpu_pct']:.0f}%")
    if metrics["available_mb"] < min_mb + margin_ram or metrics["available_pct"] < min_pct + margin_pct:
        reasons.append(f"RAM available {metrics['available_mb']:.0f} MB ({metrics['available_pct']:.0f}%)")
    return {"paused": bool(reasons), "reason": "; ".join(reasons) or "capacity available", "metrics": metrics}
