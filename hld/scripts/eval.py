#!/usr/bin/env python3
"""eval.py — HLD's deterministic tier-1 suite. Replays the fixtures through the real
scripts and compares against expected results. Run before every commit to the plugin.

Usage: eval.py            Exit 0 all green / 2 failures (listed). Stdlib only.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIX = ROOT / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import gate  # noqa: E402
import slop  # noqa: E402

RESULTS = []


def case(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))


def run_gate(gname, root):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "gate.py"), "check", gname, "--root", str(root)],
        capture_output=True, text=True).returncode


def main():
    print("HLD eval — deterministic fixture suite")

    # 1. self-tests are part of the suite
    for s in ("gate.py", "slop.py", "commit_check.py"):
        rc = subprocess.run([sys.executable, str(SCRIPTS / s), "--self-test"],
                            capture_output=True).returncode
        case(f"self-test {s}", rc == 0)
    rc = subprocess.run([sys.executable, str(SCRIPTS / "data_check.py")],
                        capture_output=True).returncode
    case("data_check", rc == 0)

    # 2. the kill door fires — and is a valid terminal, not a failure
    case("kill door fires (exit 3)", run_gate("g1", FIX / "should-kill") == 3)
    case("killed run still passes g5 (handoff ships the no)",
         run_gate("g5", FIX / "should-kill") == 0)

    # 3. a healthy run walks g0→g3
    for g in ("g0", "g1", "g2", "g3"):
        case(f"drive-loop fixture passes {g}", run_gate(g, FIX / "drive-loop") == 0)

    # 4. g3 rejects overlapping scopes and unparseable tasks
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        hld = Path(d) / ".hld"
        hld.mkdir()
        src = FIX / "drive-loop" / ".hld"
        for f in ("BRIEF.md",):
            (hld / f).write_text((src / f).read_text())
        (hld / "BUILD-PLAN.md").write_text(
            "- [ ] T1 · worker=drive · scope=src/x/ · A\n"
            "- [ ] T2 · worker=drive · scope=src/x/y.css · B\n")
        case("g3 rejects overlapping scopes", run_gate("g3", d) == 2)
        (hld / "BUILD-PLAN.md").write_text("- [ ] T1 no grammar here\n")
        case("g3 rejects unparseable task lines", run_gate("g3", d) == 2)

    # 5. the agentic trigger is deterministic, both ways
    with tempfile.TemporaryDirectory() as d:
        hld = Path(d) / ".hld"
        hld.mkdir()
        (hld / "BRIEF.md").write_text(
            "# Brief\nContract: NONE-EXISTS\nDesign the run console for an autonomous "
            "execution dashboard where sub-agent workers stream progress.\n")
        (hld / "BUILD-PLAN.md").write_text(
            "- [ ] T1 · worker=drive · scope=src/console/ · Build the console\n")
        case("agentic run without verdict block fails g3", run_gate("g3", d) == 2)
        (hld / "BUILD-PLAN.md").write_text(
            "- [ ] T1 · worker=drive · scope=src/console/ · Build the console\n\n"
            "## Workflow architecture\nAgent-as-graph: hybrid — gates outside, loop inside\n"
            "SDD: none — single surface\nWorkflow-conversion: direct — no fan-out\n")
        case("agentic run with verdict block passes g3", run_gate("g3", d) == 0)
    case("non-agentic run never asked for a verdict block",
         run_gate("g3", FIX / "drive-loop") == 0)

    # 6. contract slop rules: slop page vs clean page
    for fixture in ("slop-page", "clean-page"):
        fdir = FIX / fixture
        contract = json.loads((fdir / "contract.json").read_text())
        found = slop.contract_rules(fdir, contract)
        exp = json.loads((fdir / "expected.json").read_text())
        ok = len(found) >= exp.get("min_findings", 0)
        if "max_findings" in exp:
            ok = ok and len(found) <= exp["max_findings"]
        rules = {f["rule"] for f in found}
        for r in exp.get("must_include_rules", []):
            ok = ok and r in rules
        case(f"contract rules on {fixture} ({len(found)} findings)", ok,
             f"rules={sorted(rules)}")

    # 7. the scope boundary, from the fixture table
    for line in (FIX / "boundary" / "cases.tsv").read_text().splitlines():
        expected, desc = line.split("\t", 1)
        got = gate.boundary(desc)
        case(f"boundary: {desc[:48]}", got.split(" ")[0] == expected, got)

    # 8. gate --final refuses a FALSE done, allows an honest pause
    with tempfile.TemporaryDirectory() as d:
        hld = Path(d) / ".hld"
        hld.mkdir()
        (hld / "STATUS.md").write_text("state: done\ngate: H5\n")
        r = subprocess.run([sys.executable, str(SCRIPTS / "gate.py"), "--final"],
                           input=json.dumps({"cwd": d}), capture_output=True, text=True)
        case("--final refuses STATUS=done with failing gates", r.returncode == 2)
        (hld / "STATUS.md").write_text("state: running\ngate: H2\n")
        r = subprocess.run([sys.executable, str(SCRIPTS / "gate.py"), "--final"],
                           input=json.dumps({"cwd": d}), capture_output=True, text=True)
        case("--final allows an honest mid-run pause", r.returncode == 0)

    # 9. g5: [!] failed and [~] review block; [b] blocked + [x] done pass
    with tempfile.TemporaryDirectory() as d:
        hld = Path(d) / ".hld"
        hld.mkdir()
        (hld / "HANDOFF.md").write_text("# H\n## Auto-decisions\n- D1: x\n")
        (hld / "BUILD-PLAN.md").write_text(
            "- [!] T1 · worker=drive · scope=a/ · A\n"
            "- [~] T2 · worker=drive · scope=b/ · B\n")
        case("g5 blocks [!] and [~] tasks", run_gate("g5", d) == 2)
        (hld / "BUILD-PLAN.md").write_text(
            "- [x] T1 · worker=drive · scope=a/ · A\n"
            "- [b] T2 · worker=drive · scope=b/ · B (STOP — named for Foreman)\n")
        case("g5 passes [x] done + [b] packaged-blocked", run_gate("g5", d) == 0)

    # 10. g4 accepts an annotated shot line, rejects a malformed one
    with tempfile.TemporaryDirectory() as d:
        hld = Path(d) / ".hld"
        (hld / "work" / "screenshots").mkdir(parents=True)
        (hld / "TEST-PLAN.md").write_text(
            "- H4-mobile-m-light-export-01-error.png — the 90-day error state\n")
        (hld / "TEST-REPORT.md").write_text(
            "COULD-NOT-RUN: H4-mobile-m-light-export-01-error.png — no browser on host\n")
        case("g4 accepts annotated shot line + COULD-NOT-RUN", run_gate("g4", d) == 0)
        (hld / "TEST-PLAN.md").write_text("- H4-mobile-m-light-export-01-error\n")
        case("g4 errors on malformed - H4- line", run_gate("g4", d) == 2)

    # 11. commit_check against real git: module+caller clean, lone module refused
    import commit_check
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q", d], check=True)
        subprocess.run(["git", "-C", d, "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", d, "config", "user.name", "t"], check=True)
        Path(d, "fmt.ts").write_text("export const fmt = (x) => x;\n")
        Path(d, "app.ts").write_text("import { fmt } from './fmt';\nfmt(1);\n")
        subprocess.run(["git", "-C", d, "add", "fmt.ts", "app.ts"], check=True)
        case("commit_check passes module staged with its caller",
             commit_check.check(d, msg="feat: fmt") == [])
        subprocess.run(["git", "-C", d, "commit", "-qm", "base"], check=True)
        Path(d, "orphan.ts").write_text("export const orphan = 1;\n")
        subprocess.run(["git", "-C", d, "add", "orphan.ts"], check=True)
        errs = commit_check.check(d, msg="feat: orphan")
        case("commit_check refuses a zero-importer module",
             any("zero importers" in e for e in errs), str(errs))

    # 12. slop re-run appends nothing new (dedupe by finding id)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "findings.csv"
        fs = [{"severity": "3", "rule": "literal-color", "source": "contract",
               "file": "a.css", "line": "1", "note": "x"}]
        first = slop.append_findings(out, fs)
        second = slop.append_findings(out, fs)
        case("slop dedupe: re-run writes 0 new rows", first == 1 and second == 0,
             f"first={first} second={second}")

    # 13. --final never tracebacks on a corrupt findings.csv — still refuses honestly
    with tempfile.TemporaryDirectory() as d:
        hld = Path(d) / ".hld"
        hld.mkdir()
        (hld / "STATUS.md").write_text("state: done\ngate: H5\n")
        (hld / "findings.csv").write_text(
            "id,severity,rule,source,file,line,note,disposition\nF1\n")
        r = subprocess.run([sys.executable, str(SCRIPTS / "gate.py"), "--final"],
                           input=json.dumps({"cwd": d}), capture_output=True, text=True)
        case("--final survives corrupt findings.csv and still refuses false done",
             r.returncode == 2 and "Traceback" not in r.stderr, r.stderr[:120])

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
