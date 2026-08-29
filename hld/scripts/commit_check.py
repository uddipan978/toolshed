#!/usr/bin/env python3
"""commit_check.py — the mechanical half of the commit doctrine. Wraps HLD's OWN
task commits only; it is NEVER installed as a hook on the product repository.

Checks (all on the currently staged state of the repo at --repo, default cwd):
  1. something is actually staged
  2. no binary rows in the staged diff (a Bin file is invisible to every reviewer)
  3. no Co-Authored-By (or any co-author) trailer in the message (--msg / --msg-file)
  4. every newly added source module has an importer at this commit
     (page/route/config/test entrypoints exempt)
  5. with --task Tn --plan BUILD-PLAN.md: staged paths sit inside that task's scope
     (paths under .hld/ are always allowed)

Usage:
  commit_check.py [--repo DIR] [--msg "..."|--msg-file F] [--task Tn --plan FILE]
  commit_check.py --self-test

Exit 0 = commit is clean · 2 = refuse, reasons printed. Stdlib only.
"""
import re
import subprocess
import sys
from pathlib import Path

ENTRYPOINT_RE = re.compile(
    r"(^|/)(page|layout|route|index|main|app)\.[jt]sx?$|"
    r"\.(test|spec|stories|config|d)\.[jt]sx?$|\.config\.[jt]s$")
SOURCE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs"}
TRAILER_RE = re.compile(r"^\s*co-authored-by\s*:", re.I | re.M)


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout


TEXT_EXT = SOURCE_EXT | {".css", ".scss", ".html", ".md", ".json", ".svg", ".yaml",
                         ".yml", ".txt", ".csv", ".vue", ".svelte"}


def binary_rows(numstat):
    """Only a TEXT file recorded as binary is a defect (stray control chars make it
    invisible to reviewers). Real assets (.png, .woff2, ...) are legitimate."""
    return [ln.split("\t")[2] for ln in numstat.splitlines()
            if ln.startswith("-\t-\t") and Path(ln.split("\t")[2]).suffix in TEXT_EXT]


def added_modules(name_status):
    out = []
    for ln in name_status.splitlines():
        parts = ln.split("\t")
        if len(parts) >= 2 and parts[0] == "A":
            p = parts[-1]
            if Path(p).suffix in SOURCE_EXT and not ENTRYPOINT_RE.search(p):
                out.append(p)
    return out


def has_importer(repo, path):
    """Search the INDEX (the exact tree being committed) with portable word matching:
    git's default ERE has no \\b on macOS, so -w does the word boundary."""
    stem = Path(path).stem
    if not re.fullmatch(r"[\w.-]+", stem):
        return True  # unusual name; don't false-positive
    code, out = git(repo, "grep", "--cached", "-l", "-w", "-e", stem)
    importers = [f for f in out.splitlines() if f and f != path]
    return code == 0 and bool(importers)


def scope_of(plan_text, task_id):
    m = re.search(rf"^- \[.\] {task_id} · worker=\S+ · scope=(\S+) ·",
                  plan_text, re.M)
    return m.group(1).split(",") if m else None


def in_scope(path, scope):
    if path.startswith(".hld/") or "/.hld/" in path:
        return True
    for s in scope:
        s = s.rstrip("/")
        if path == s or path.startswith(s + "/"):
            return True
    return False


def check(repo, msg=None, task=None, plan_path=None):
    errs = []
    _, staged = git(repo, "diff", "--cached", "--name-only")
    files = [f for f in staged.splitlines() if f]
    if not files:
        return ["nothing staged — stage the task's exact paths (never `git add -A`)"]
    _, numstat = git(repo, "diff", "--cached", "--numstat")
    for b in binary_rows(numstat):
        errs.append(f"binary diff: {b} — reviewers can't see it; check for stray "
                    "control characters or a wrong file")
    if msg and TRAILER_RE.search(msg):
        errs.append("commit message carries a co-author trailer — plain messages only")
    _, ns = git(repo, "diff", "--cached", "--name-status")
    for mod in added_modules(ns):
        if not has_importer(repo, mod):
            errs.append(f"new module {mod} has zero importers at this commit — "
                        "it ships dead code; commit it with its first caller")
    if task and plan_path:
        plan = Path(plan_path)
        if not plan.is_file():
            errs.append(f"--plan {plan_path} not found")
        else:
            scope = scope_of(plan.read_text(), task)
            if scope is None:
                errs.append(f"task {task} not found in {plan_path}")
            else:
                for f in files:
                    if not in_scope(f, scope):
                        errs.append(f"{f} is outside {task}'s scope ({','.join(scope)})")
    return errs


def self_test():
    assert TRAILER_RE.search("fix\n\nCo-Authored-By: X <x@y.z>")
    assert not TRAILER_RE.search("fix: co-authored the doc review flow")
    assert binary_rows("-\t-\tlogo.png\n3\t1\ta.ts") == [], "assets are legitimate"
    assert binary_rows("-\t-\tsrc/a.ts\n3\t1\tb.ts") == ["src/a.ts"], \
        "text file recorded as binary is the defect"
    assert added_modules("A\tsrc/util/fmt.ts\nA\tsrc/app/page.tsx\nM\tb.ts") == \
        ["src/util/fmt.ts"]
    plan = "- [ ] T1 · worker=drive · scope=src/chip/,src/styles/chip.css · Chip"
    assert scope_of(plan, "T1") == ["src/chip/", "src/styles/chip.css"]
    assert in_scope("src/chip/Chip.tsx", ["src/chip/"])
    assert in_scope(".hld/BUILD-PLAN.md", ["src/chip/"])
    assert not in_scope("src/other.ts", ["src/chip/"])
    print("commit_check.py self-test: ok")
    return 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    args = dict(zip(argv, argv[1:]))
    repo = args.get("--repo", ".")
    msg = args.get("--msg")
    if "--msg-file" in args:
        msg = Path(args["--msg-file"]).read_text()
    errs = check(repo, msg=msg, task=args.get("--task"), plan_path=args.get("--plan"))
    if errs:
        print("commit_check REFUSED:")
        for e in errs:
            print(f"  - {e}")
        return 2
    print("commit_check: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
