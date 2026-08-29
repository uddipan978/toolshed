#!/usr/bin/env python3
"""effort.py - score one task-goal's effort ledger as a Human Cost Score.

    python3 effort.py <ledger.csv|->                    score one ledger
    python3 effort.py --compare before.csv after.csv    score both, print the delta
    python3 effort.py --example > ledger.csv            write a valid sample to edit
    python3 effort.py --selftest                        run the built-in assertions
    --json          machine-readable output, same numbers
    --frequency N   uses per year; multiplies the score (and the delta) into an annual figure

    HCS = Interaction + Decision + Memory + Wait + Recovery

Weights come from ../data/effort-weights.csv and are RELATIVE units, not seconds. Never
report a total as a time estimate. A bare total is close to meaningless on its own - what
carries a claim is the delta between two ledgers of the SAME flow scored with the SAME
weights, and the component split that says where the cost sits. That is why the summary
always prints all five components: a total hides whether you are looking at a click problem
or a waiting problem, and those have different fixes.

LEDGER FORMAT
-------------
Eight columns, header row required, one row per action the human took:

    step,screen,action,action_type,options,memory_items,wait_ms,notes

    step          1-based ordinal. Yours to keep in order - the script does not sort.
    screen        where the human was: a URL, a route, a screen name. Free text.
    action        what they did, in plain words. Free text, shown in the table only.
    action_type   MUST match an `action` value in effort-weights.csv. An unrecognised
                  value is a hard error - see UNKNOWN ACTION TYPES below.
                  May carry a repeat count: `keystroke-char*20` charges the row 20 times.
                  The multiplier applies to the action weight and to the options-derived
                  decision cost (a repeated step repeats its decision). It does NOT apply
                  to memory_items or wait_ms, which are already absolute per-row counts.
    options       number of choices at this step; 0 when it is not a choice point.
                  Decision cost is log2(options+1) - Hick's Law, 1.0 per bit.
    memory_items  items the human newly has to CARRY OUT of this step because the system
                  would not hold them. Per row, not a running total; the script sums.
    wait_ms       observed transition time in milliseconds.
                  0 means you timed it and it was instant.
                  EMPTY means you did not time it: the step prints as `unmeasured`, adds
                  nothing to Wait, and is counted in a footnote so the total stays honest.
                  Never write 0 for "I did not look" - that silently understates Wait, and
                  an understated Wait sends the fix to the design team when it belongs to
                  engineering.
    notes        free text. Put the screenshot id here so a finding can cite the row.

WHICH COMPONENT AN ACTION LANDS IN
----------------------------------
By name, so the mapping survives edits to the weights file:
    wait-*                                        -> W
    decision-*                                    -> D
    memory-*                                      -> M
    error-*, undo-*, backtrack,
    irreversible-action, confirmation-dialog      -> R
    everything else                               -> I
A new weight row matching no rule counts as Interaction. If you add a recovery-shaped row,
name it `error-*` or `undo-*` or add it to RECOVERY_ACTIONS below, or its cost will be
attributed to the wrong component and the fix class printed at the bottom will be wrong.

DOUBLE-CHARGE RULES
-------------------
Two ways to express the same cost exist, so the script picks one and says which:
  * `options > 0` on a decision-* row: the exact log2(options+1) wins and the bucket weight
    is dropped. The buckets exist for when the count is fuzzy, not to replace arithmetic
    you can do.
  * `memory_items > 0` on a memory-* row: the column is the count, charged once each.
  * `wait_ms` present on a wait-* row: the measurement wins over the declared band.
Charging a select-* row AND its decision cost is NOT a double charge - one is the motor and
scanning cost, the other is the classification cost, and they move independently.

UNKNOWN ACTION TYPES
--------------------
An action_type not present in effort-weights.csv exits 1 naming the value, its row, and the
valid set. It is never defaulted to 1.0: a silent default produces a confident wrong score,
and a wrong score that looks right is worse than no score, because someone will cite it.
"""

import argparse
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_PATH = os.path.normpath(os.path.join(HERE, "..", "data", "effort-weights.csv"))

COMPONENTS = ("I", "D", "M", "W", "R")
COMPONENT_NAMES = {
    "I": "Interaction",
    "D": "Decision",
    "M": "Memory",
    "W": "Wait",
    "R": "Recovery",
}
FIX_CLASS = {
    "I": "batching and defaults - collapse the repeated steps, pre-fill what you can "
         "already know. Every step removed is a whole unit off the score.",
    "D": "reduce or rank the options - cut the list, or put the choice they almost always "
         "make first. log2 means halving a 15-option list only buys you one bit.",
    "M": "co-locate - put the value on the screen that needs it instead of making the human "
         "carry it. Each carried item costs five clicks; a fourth costs twenty.",
    "W": "engineering, not design - no layout change fixes a 3s response. Make it faster, "
         "or background it and notify. A bigger spinner is not a fix.",
    "R": "make it reversible - ship a real undo. A confirmation dialog lowers the slip rate "
         "but not the fear, so it does not discount the cost of an irreversible act.",
}

RECOVERY_ACTIONS = {"backtrack", "irreversible-action", "confirmation-dialog"}
MEMORY_PREFIX = "memory-"
MEMORY_UNIT_ACTION = "memory-item-carried"
MEMORY_CEILING = 4  # Cowan 2001 - past four carried items the flow is over budget

# Thresholds are the Doherty/Miller bands and are fixed by the research; the costs attached
# to them are tunable and are read from the weights file by these names.
WAIT_BANDS = (
    (400, "wait-under-400ms"),
    (2000, "wait-400ms-2s"),
    (10000, "wait-2s-10s"),
    (float("inf"), "wait-over-10s"),
)

LEDGER_COLUMNS = [
    "step", "screen", "action", "action_type",
    "options", "memory_items", "wait_ms", "notes",
]

EXAMPLE_LEDGER = """\
step,screen,action,action_type,options,memory_items,wait_ms,notes
1,/billing,clicked Invoices in the left nav,navigation-new-page,0,0,900,shot-01
2,/billing/invoices,hunted the table for the right period,scroll-to-find,0,0,0,shot-02
3,/billing/invoices,clicked Export,modal-open,0,0,250,shot-03
4,/billing/invoices,chose a format,select-from-short-list,4,0,0,shot-03 CSV/XLSX/PDF/JSON
5,/billing/invoices,typed both dates by hand,field-entry-typed*2,0,0,,shot-04 no date picker
6,/billing/invoices,typed 20 date characters,keystroke-char*20,0,0,,shot-04
7,/billing/invoices,submitted; rejected as 'range too wide',error-encountered,0,1,3200,shot-05 the 90-day limit is stated nowhere before submit
8,/billing/invoices,narrowed the range and resubmitted,error-recovered,0,0,1100,shot-06
"""


class LedgerError(Exception):
    """Anything wrong with the input that must stop the run rather than skew the score."""


def _r(x):
    """Round half up, including for negatives, so deltas read the way people expect."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def load_weights(path=WEIGHTS_PATH):
    """action -> unit_cost. Rows starting with `_` are notes, not actions, and are dropped
    so they never appear in the 'valid values' list a user is shown after a typo."""
    if not os.path.exists(path):
        raise LedgerError("weights file not found: %s" % path)
    weights = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "action" not in reader.fieldnames:
            raise LedgerError("%s has no `action` column" % path)
        for row in reader:
            action = (row.get("action") or "").strip()
            if not action or action.startswith("_"):
                continue
            try:
                weights[action] = float(row.get("unit_cost") or 0)
            except ValueError:
                raise LedgerError(
                    "weights row %r has a non-numeric unit_cost: %r"
                    % (action, row.get("unit_cost"))
                )
    for _, band in WAIT_BANDS:
        if band not in weights:
            raise LedgerError("weights file is missing the wait band %r" % band)
    if MEMORY_UNIT_ACTION not in weights:
        raise LedgerError("weights file is missing %r" % MEMORY_UNIT_ACTION)
    return weights


def component_of(action):
    if action.startswith("wait-"):
        return "W"
    if action.startswith("decision-"):
        return "D"
    if action.startswith(MEMORY_PREFIX):
        return "M"
    if action.startswith(("error-", "undo-")) or action in RECOVERY_ACTIONS:
        return "R"
    return "I"


def wait_band(ms):
    for limit, name in WAIT_BANDS:
        if ms < limit:
            return name
    return WAIT_BANDS[-1][1]


def _int_field(row, key, lineno, default=0, allow_blank=False):
    raw = (row.get(key) or "").strip()
    if raw == "":
        if allow_blank:
            return None
        return default
    try:
        value = int(float(raw))
    except ValueError:
        raise LedgerError("row %d: %s must be a whole number, got %r" % (lineno, key, raw))
    if value < 0:
        raise LedgerError("row %d: %s cannot be negative, got %r" % (lineno, key, raw))
    return value


def split_repeat(raw):
    """`keystroke-char*20` -> ('keystroke-char', 20). No suffix means one occurrence."""
    base, sep, count = raw.partition("*")
    if not sep:
        return raw.strip(), 1
    count = count.strip()
    if not count.isdigit() or int(count) < 1:
        raise LedgerError(
            "bad repeat count in %r - write action_type*N with N a positive whole number" % raw
        )
    return base.strip(), int(count)


def read_ledger(fh, source="<input>"):
    reader = csv.DictReader(fh)
    if not reader.fieldnames:
        raise LedgerError("%s is empty - it needs the header row: %s"
                          % (source, ",".join(LEDGER_COLUMNS)))
    missing = [c for c in LEDGER_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise LedgerError(
            "%s is missing column(s): %s\nrequired header: %s"
            % (source, ", ".join(missing), ",".join(LEDGER_COLUMNS))
        )
    rows = []
    for row in reader:
        if not any((v or "").strip() for v in row.values()):
            continue  # blank line, not a step
        lineno = reader.line_num
        raw_type = (row.get("action_type") or "").strip()
        if not raw_type:
            raise LedgerError("row %d: action_type is empty" % lineno)
        action, repeat = split_repeat(raw_type)
        rows.append({
            "line": lineno,
            "step": (row.get("step") or "").strip() or str(len(rows) + 1),
            "screen": (row.get("screen") or "").strip(),
            "action": (row.get("action") or "").strip(),
            "action_type": action,
            "repeat": repeat,
            "options": _int_field(row, "options", lineno),
            "memory_items": _int_field(row, "memory_items", lineno),
            "wait_ms": _int_field(row, "wait_ms", lineno, allow_blank=True),
            "notes": (row.get("notes") or "").strip(),
        })
    if not rows:
        raise LedgerError("%s has a header but no steps" % source)
    return rows


def score(rows, weights, source="<input>"):
    totals = {c: 0.0 for c in COMPONENTS}
    steps = []
    unmeasured = []
    memory_items = 0

    for row in rows:
        action = row["action_type"]
        if action not in weights:
            raise LedgerError(
                "row %d: unknown action_type %r.\nValid values (from %s):\n  %s"
                % (row["line"], action, WEIGHTS_PATH,
                   "\n  ".join(sorted(weights)))
            )
        cost = weights[action] * row["repeat"]
        comp = component_of(action)
        cell = {c: 0.0 for c in COMPONENTS}

        # Decision: exact arithmetic beats the bucket whenever the option count is known.
        bucket_dropped = False
        if row["options"] > 0:
            cell["D"] += math.log2(row["options"] + 1) * row["repeat"]
            if comp == "D":
                bucket_dropped = True

        # Memory: the column is the count, so a memory-* row is charged per item, not twice.
        if comp == "M":
            cell["M"] += cost * max(row["memory_items"], 1)
            memory_items += max(row["memory_items"], 1)
        else:
            memory_items += row["memory_items"]
            cell["M"] += row["memory_items"] * weights[MEMORY_UNIT_ACTION]

        # Wait: a measurement beats a declared band; a blank is unmeasured, never zero.
        band = None
        if row["wait_ms"] is None:
            if comp == "W":
                cell["W"] += cost
                band = action
            else:
                unmeasured.append(row["step"])
        else:
            band = wait_band(row["wait_ms"])
            cell["W"] += weights[band]

        if comp == "I" or comp == "R":
            cell[comp] += cost
        elif comp == "D" and not bucket_dropped:
            cell["D"] += cost
        # comp == "M" and comp == "W" are already settled above.

        for c in COMPONENTS:
            totals[c] += cell[c]

        steps.append({
            "step": row["step"],
            "screen": row["screen"],
            "action": row["action"],
            "action_type": action + ("*%d" % row["repeat"] if row["repeat"] > 1 else ""),
            "wait_ms": row["wait_ms"],
            "wait_band": band,
            "cells": cell,
            "total": sum(cell.values()),
            "notes": row["notes"],
        })

    # Round components once, then define the total as their sum, so the printed parts
    # always add up to the printed whole. A summary a reader cannot verify gets ignored.
    rounded = {c: _r(totals[c]) for c in COMPONENTS}
    return {
        "source": source,
        "steps": steps,
        "raw": totals,
        "components": rounded,
        "hcs": sum(rounded.values()),
        "unmeasured": unmeasured,
        "memory_items": memory_items,
    }


def summary_line(result):
    c = result["components"]
    return "HCS %d (I:%d D:%d M:%d W:%d R:%d)" % (
        result["hcs"], c["I"], c["D"], c["M"], c["W"], c["R"])


def dominant(result):
    """Largest component by raw cost. Ties resolve by the order of COMPONENTS, which runs
    cheapest-to-fix first, so a tie points at the fix you can actually ship."""
    return max(COMPONENTS, key=lambda c: (result["raw"][c], -COMPONENTS.index(c)))


def print_table(result, out):
    steps = result["steps"]
    w_screen = min(max([len(s["screen"]) for s in steps] + [6]), 24)
    w_action = min(max([len(s["action_type"]) for s in steps] + [11]), 26)
    header = "%-4s  %-*s  %-*s  %10s  %6s %6s %6s %6s %6s  %7s" % (
        "step", w_screen, "screen", w_action, "action_type", "wait",
        "I", "D", "M", "W", "R", "total")
    print(header, file=out)
    print("-" * len(header), file=out)
    for s in steps:
        wait = "unmeasured" if s["wait_ms"] is None and s["wait_band"] is None else (
            "%dms" % s["wait_ms"] if s["wait_ms"] is not None else s["wait_band"])
        cells = s["cells"]
        print("%-4s  %-*.*s  %-*.*s  %10s  %6.1f %6.1f %6.1f %6.1f %6.1f  %7.1f" % (
            s["step"], w_screen, w_screen, s["screen"], w_action, w_action, s["action_type"],
            wait, cells["I"], cells["D"], cells["M"], cells["W"], cells["R"], s["total"]),
            file=out)
    print("-" * len(header), file=out)
    raw = result["raw"]
    print("%-4s  %-*s  %-*s  %10s  %6.1f %6.1f %6.1f %6.1f %6.1f  %7.1f" % (
        "", w_screen, "", w_action, "subtotal", "",
        raw["I"], raw["D"], raw["M"], raw["W"], raw["R"], sum(raw.values())), file=out)


def print_report(result, frequency=None, out=sys.stdout):
    print_table(result, out)
    print("", file=out)
    print(summary_line(result), file=out)

    n = len(result["unmeasured"])
    if n:
        print("unmeasured  %d of %d steps had no wait_ms and are excluded from W: steps %s. "
              "The Wait component is a floor, not a measurement."
              % (n, len(result["steps"]), ", ".join(result["unmeasured"])), file=out)
    else:
        print("unmeasured  0 steps - every transition was timed, so W is a real number.", file=out)

    top = dominant(result)
    total = sum(result["raw"].values())
    share = (result["raw"][top] / total * 100) if total else 0.0
    print("", file=out)
    print("read  %s dominates: %.0f of %.0f, %.0f%% of the score."
          % (COMPONENT_NAMES[top], result["raw"][top], total, share), file=out)
    print("      fix class: %s" % FIX_CLASS[top], file=out)
    if result["memory_items"] > MEMORY_CEILING:
        print("      also: %d items carried across screens, over the working-memory ceiling of "
              "%d. Expect people to write things down or get them wrong - and neither shows up "
              "in your logs." % (result["memory_items"], MEMORY_CEILING), file=out)
    if frequency:
        print("      at %d uses/year this flow costs %d HCS-units a year."
              % (frequency, result["hcs"] * frequency), file=out)


def print_compare(before, after, frequency=None, out=sys.stdout):
    print("before  %-38s  %s" % (summary_line(before), before["source"]), file=out)
    print("after   %-38s  %s" % (summary_line(after), after["source"]), file=out)
    delta = {c: after["components"][c] - before["components"][c] for c in COMPONENTS}
    d_total = after["hcs"] - before["hcs"]
    print("delta   HCS %+d (I:%+d D:%+d M:%+d W:%+d R:%+d)" % (
        d_total, delta["I"], delta["D"], delta["M"], delta["W"], delta["R"]), file=out)
    print("", file=out)

    # Do NOT print the fix class for a component that went DOWN - it already got fixed, and
    # advising the fix again reads as a recommendation to redo work that landed.
    saved = [c for c in COMPONENTS if delta[c] < 0]
    regressed = [c for c in COMPONENTS if delta[c] > 0]
    if not saved and not regressed:
        print("read  nothing moved. Whatever changed, it did not change what the flow costs "
              "the human.", file=out)
    if saved:
        best = min(saved, key=lambda c: delta[c])
        print("read  the saving is mostly %s (%+d of %+d). Name that in the finding - a delta "
              "with no named component is a number nobody can check."
              % (COMPONENT_NAMES[best], delta[best], d_total), file=out)
    if regressed:
        worst = max(regressed, key=lambda c: delta[c])
        print("      regressed: %s. That is a trade you made; say it out loud or a reviewer "
              "will find it for you."
              % ", ".join("%s %+d" % (COMPONENT_NAMES[c], delta[c]) for c in regressed),
              file=out)
        print("      if the trade was not deliberate, %s" % FIX_CLASS[worst], file=out)

    stale = len(before["unmeasured"]) + len(after["unmeasured"])
    if stale:
        print("      %d step(s) across both ledgers have no wait_ms, so the W delta is a floor. "
              "Time the waits before claiming a speed win." % stale, file=out)
    if frequency:
        print("      %d uses/year x %d HCS = %d HCS-units a year %s."
              % (frequency, abs(d_total), frequency * abs(d_total),
                 "saved" if d_total < 0 else "added"), file=out)


def selftest():
    weights = load_weights()
    import io

    base = (
        "step,screen,action,action_type,options,memory_items,wait_ms,notes\n"
        "1,/a,click it,click,0,0,0,\n"
        "2,/a,pick one,select-from-short-list,3,0,120,\n"
        "3,/b,go,navigation-new-page,0,1,1500,\n"
        "4,/b,oops,backtrack,0,0,,\n"
    )
    r = score(read_ledger(io.StringIO(base)), weights)
    # click 1.0 + select 2.0 + nav 4.0 = 7.0 I; log2(4) = 2.0 D; 1 item x 5.0 = 5.0 M;
    # 0ms -> 0.0 and 1500ms -> 1.0 W; backtrack 3.0 R.
    assert r["raw"]["I"] == 7.0, r["raw"]
    assert r["raw"]["D"] == 2.0, r["raw"]
    assert r["raw"]["M"] == 5.0, r["raw"]
    assert r["raw"]["W"] == 1.0, r["raw"]
    assert r["raw"]["R"] == 3.0, r["raw"]
    assert r["hcs"] == 18, r["hcs"]
    assert summary_line(r) == "HCS 18 (I:7 D:2 M:5 W:1 R:3)", summary_line(r)
    # the printed parts must add up to the printed whole
    assert sum(r["components"][c] for c in COMPONENTS) == r["hcs"]

    # wait_ms blank is unmeasured, not zero: step 4 is named and W excludes it.
    assert r["unmeasured"] == ["4"], r["unmeasured"]

    # log2 decision maths, exact at a power of two, and multiplied by the repeat count.
    d = score(read_ledger(io.StringIO(
        "step,screen,action,action_type,options,memory_items,wait_ms,notes\n"
        "1,/a,pick,click,7,0,0,\n")), weights)
    assert d["raw"]["D"] == 3.0, d["raw"]          # log2(8)
    d2 = score(read_ledger(io.StringIO(
        "step,screen,action,action_type,options,memory_items,wait_ms,notes\n"
        "1,/a,pick thrice,click*3,7,0,0,\n")), weights)
    assert d2["raw"]["D"] == 9.0 and d2["raw"]["I"] == 3.0, d2["raw"]

    # a decision-* bucket with a known count uses the arithmetic, not the bucket, once.
    b = score(read_ledger(io.StringIO(
        "step,screen,action,action_type,options,memory_items,wait_ms,notes\n"
        "1,/a,choose,decision-3-to-7,5,0,0,\n")), weights)
    assert abs(b["raw"]["D"] - math.log2(6)) < 1e-9, b["raw"]
    fuzzy = score(read_ledger(io.StringIO(
        "step,screen,action,action_type,options,memory_items,wait_ms,notes\n"
        "1,/a,choose,decision-3-to-7,0,0,0,\n")), weights)
    assert fuzzy["raw"]["D"] == weights["decision-3-to-7"], fuzzy["raw"]

    # a memory-* row is charged per item in the column, not once plus once.
    m = score(read_ledger(io.StringIO(
        "step,screen,action,action_type,options,memory_items,wait_ms,notes\n"
        "1,/a,carry three,memory-item-carried,0,3,0,\n")), weights)
    assert m["raw"]["M"] == 15.0 and m["memory_items"] == 3, m["raw"]

    # unknown action_type is an error naming the value, never a silent default.
    try:
        score(read_ledger(io.StringIO(
            "step,screen,action,action_type,options,memory_items,wait_ms,notes\n"
            "1,/a,who knows,clicky,0,0,0,\n")), weights)
    except LedgerError as exc:
        assert "clicky" in str(exc) and "select-from-short-list" in str(exc), str(exc)
    else:
        raise AssertionError("unknown action_type did not raise")

    # a missing column names the column rather than scoring a partial ledger.
    try:
        read_ledger(io.StringIO("step,screen,action,action_type\n1,/a,x,click\n"))
    except LedgerError as exc:
        assert "options" in str(exc), str(exc)
    else:
        raise AssertionError("missing columns did not raise")

    # the shipped example parses and scores.
    ex = score(read_ledger(io.StringIO(EXAMPLE_LEDGER)), weights)
    assert ex["hcs"] > 0 and len(ex["steps"]) == 8, ex["hcs"]

    print("selftest ok - %d assertions across scoring, log2 decisions, unmeasured waits, "
          "double-charge rules and both error paths" % 14)


def load(path):
    if path == "-":
        return read_ledger(sys.stdin, "<stdin>")
    if not os.path.exists(path):
        raise LedgerError("ledger not found: %s" % path)
    with open(path, newline="", encoding="utf-8") as fh:
        return read_ledger(fh, path)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="effort.py",
        description="Score an effort ledger as a Human Cost Score: "
                    "HCS = Interaction + Decision + Memory + Wait + Recovery.",
        epilog="Units are relative, not seconds. Run --example for a ledger to edit.")
    p.add_argument("ledger", nargs="?", help="ledger CSV path, or - for stdin")
    p.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                   help="score two ledgers of the same flow and print the per-component delta")
    p.add_argument("--frequency", type=int, metavar="N",
                   help="uses per year; turns the score (or the delta) into an annual figure")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--example", action="store_true",
                   help="print a valid 8-row sample ledger and exit")
    p.add_argument("--selftest", action="store_true", help="run the built-in assertions")
    args = p.parse_args(argv)

    if args.example:
        sys.stdout.write(EXAMPLE_LEDGER)
        return 0
    if args.selftest:
        selftest()
        return 0

    try:
        weights = load_weights()
        if args.compare:
            before = score(load(args.compare[0]), weights, args.compare[0])
            after = score(load(args.compare[1]), weights, args.compare[1])
            if args.json:
                delta = {c: after["components"][c] - before["components"][c]
                         for c in COMPONENTS}
                json.dump({"before": before, "after": after, "delta": delta,
                           "delta_hcs": after["hcs"] - before["hcs"],
                           "frequency": args.frequency,
                           "annual": (args.frequency * (after["hcs"] - before["hcs"])
                                      if args.frequency else None)},
                          sys.stdout, indent=2)
                print()
            else:
                print_compare(before, after, args.frequency)
            return 0
        if not args.ledger:
            p.error("give a ledger path (or - for stdin), --compare, --example or --selftest")
        result = score(load(args.ledger), weights, args.ledger)
        if args.json:
            result["summary"] = summary_line(result)
            result["dominant"] = dominant(result)
            result["frequency"] = args.frequency
            result["annual"] = args.frequency * result["hcs"] if args.frequency else None
            json.dump(result, sys.stdout, indent=2)
            print()
        else:
            print_report(result, args.frequency)
        return 0
    except LedgerError as exc:
        print("effort.py: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
