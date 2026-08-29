#!/usr/bin/env python3
"""doctor.py — environment report. Prints what's present, what's missing, and the exact
command for anything missing. HLD NEVER runs installs or edits files it doesn't own —
every suggested change below is USER ACTION REQUIRED, printed for a human to apply.

Usage: doctor.py      Stdlib only. Exit 0 always (this is a report, not a gate).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe import probe  # noqa: E402

INSTALL_HINTS = {
    "node": "brew install node   (or your platform's package manager)",
    "playwright": "npm i -g playwright && playwright install chromium",
    "detect_mjs": "install the 'impeccable' skill (community; no license in-tree — "
                  "HLD only runs it, never copies it)",
    "foreman_root": "clone github.com/uddipan978/toolshed and register the foreman "
                    "plugin — only needed for parallel multi-worker builds",
}

HLT_HOMES = [
    "~/.claude/skills/human-like-thinking/SKILL.md",
    "~/.agents/skills/human-like-thinking/SKILL.md",
]


OVERLAP_PHRASES = ["HLD", "human-like design", "walk me through", "walkthrough",
                   "UI walkthrough", "wireframe", "mind map"]


def hlt_collision():
    for home in HLT_HOMES:
        p = Path(home).expanduser()
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^description:\s*(.+)$", text, re.M)
        if not m:
            continue
        overlaps = [ph for ph in OVERLAP_PHRASES
                    if re.search(rf"\b{re.escape(ph)}\b", m.group(1), re.I)]
        if overlaps:
            return p, m.group(1), overlaps
    return None, None, []


def main():
    info = probe()
    print("HLD doctor — environment report")
    print("=" * 60)
    for key in ("host", "python", "git", "node", "playwright", "detect_mjs",
                "foreman_root", "subagents", "hooks"):
        val = info.get(key)
        mark = "ok " if val else "-- "
        print(f"  {mark}{key:14} {val if val else 'MISSING'}")
        if not val and key in INSTALL_HINTS:
            print(f"       to add it, YOU run: {INSTALL_HINTS[key]}")
    print()
    if info.get("foreman_root"):
        print("  foreman is runnable: at H3, HLD will DEFER the build to it and keep")
        print("  only the watch seam. Standalone drive stays available if you remove it.")
    else:
        print("  no runnable foreman: HLD drives builds itself, in-session and")
        print("  sequential, within the UI scope boundary (reference/hld-gates.md).")
    print()
    p, desc, overlaps = hlt_collision()
    if p:
        print("  TRIGGER COLLISION (user action required — HLD will NOT edit this file):")
        print(f"  {p}")
        print(f"  its description overlaps this plugin's router on: {', '.join(overlaps)}")
        print("  HLD absorbed human-like-thinking wholesale (data, scripts, reference),")
        print("  so the cleanest fix is disabling that loose skill; the narrower fix is")
        print("  removing the overlapping phrases from its description. Either way it is")
        print("  YOUR edit to make — HLD never touches it, and re-checks on every run.")
        if "HLD" in overlaps:
            i = desc.find("HLD")
            window = desc[max(0, i - 40):i + 60]
            fixed = re.sub(r"(, )?\bHLD\b(, )?",
                           lambda m: ", " if m.group(1) and m.group(2) else "", window)
            print(f"    - ...{window}...")
            print(f"    + ...{fixed.strip()}...")
    else:
        print("  no trigger collision with human-like-thinking detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
