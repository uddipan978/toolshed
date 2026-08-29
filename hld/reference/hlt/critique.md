# critique.md — the `review` command

Turn an observed walkthrough into a short, ranked, defensible list of things to change.

A finding is defensible when someone who disagrees with your taste still has to accept it. That
takes three things: you saw it, you counted it, and you can name the principle and its evidence
grade. Anything short of that is a preference, and preferences lose arguments with engineering
managers who have a sprint to fill.

---

## 1. Precondition — you must have walked it

`review` runs on an observed surface. Observed means: you clicked it, in this session, and you
have screenshots.

**If the surface was not walked this session, stop and run `walk` first.** See
[walkthrough.md](walkthrough.md).

**Failure behaviour — say this out loud rather than substituting:**

- *Not walked yet* → "I have not walked this surface. Running `walk` first." Then walk it.
- *App will not start* → report exactly what failed (command, error, what you tried). A surface you
  cannot reach is a blocked review, not a source-code review.
- *Partially walked* — you saw the list but never opened the detail drawer → review only what you
  saw. Everything else goes in "what was not checked and why" (§7), not into a finding.
- *User pastes a screenshot and asks for a review* → you may review what is in the frame, at
  page-level scope only. You cannot judge effort, flow, or responsiveness from one frame; say so.

Reviewing from source is the exact failure this skill exists to prevent. Source tells you what the
component *can* render. It does not tell you that the button is below the fold, that the toast
disappears in 2s, that the save takes 1.8s, or that the third field is pre-filled with a value that
is wrong. Every one of those is a finding you can only get by driving.

Read [effort-ledger.md](effort-ledger.md) and finish the ledger **before** you form a visual
opinion. The reason is in §6; the ordering is not optional.

---

## 2. The five axes, operationalised

Answer all five, in order. The order is damage-descending: a flow that costs 14 clicks is worse
than a flow with a weak heading hierarchy, and fixing the heading first is how reviews become
decoration.

Each axis below gives checks phrased as questions with a decidable answer. "Decidable" means the
ledger or a screenshot settles it — not your judgement. If a check needs judgement to answer, it is
not a check, it is a topic.

### Axis 1 — Effort

*How many steps to the goal, and which are removable?*

| # | Check | Fails when | Principle |
|---|---|---|---|
| E1 | What is the theoretical minimum step count for this goal? What is the observed count? | observed > 2× minimum | `teslers-law` |
| E2 | Was any value typed that the system already knows, or that was typed earlier in this same flow? | ≥1 re-entry | `working-memory`, `choice-architecture` |
| E3 | Did you navigate away and back purely to *read* one value? | ≥1 round trip for a read | `cognitive-load` |
| E4 | Does any action require leaving the row/card it belongs to, when it could be inline? | edit opens a full page for one field | `fitts-law` |
| E5 | The list holds >10 items — is there a bulk action for the operation you just did one at a time? | no multi-select and the op is repeatable | `pareto-principle` |
| E6 | Does any required choice have one obviously dominant answer, and no default set? | field is empty where a default exists | `choice-architecture` |
| E7 | Count clicks/fields/screens on the *entry* path and on the *exit* path (subscribe vs cancel, add vs remove). | exit path costs more than entry | `choice-architecture` (asymmetry test) |
| E8 | How many steps to undo the most likely mistake? | recovery > the action that caused it | `cognitive-load` |
| E9 | Did anything take >400ms with no acknowledgement under 100ms? | bare spinner-free wait | `doherty-threshold` |

Evidence that proves a check failed: the ledger row plus the two screenshots that bracket it —
`screenshot 04 → 05` — and the raw count. `"6 clicks · 2 waits >400ms · 1 backtrack"`. Never
"felt slow"; you have the number, use it.

Typical proposal shapes, in order of preference — **delete the step · default the step · defer the
step · merge two steps · make the step inline**. Reach for "add a shortcut" last: a shortcut is a
second path, and two paths cost more to maintain and to learn than one shorter path.

The asymmetry audit (E7) is the highest-yield single check in this file and needs no theory — see
`/Users/shankhajeettaran/workspace/learning/research/synthesis/02-practitioner-playbook.md`
("Practitioner's note"). Most products carry more accidental friction on the user-beneficial path
than they have missing persuasion on the business-beneficial one.

### Axis 2 — Presentation

*Show, collapse, hide, or omit?*

Decide by **frequency × detail need**, not by how much room is free. A screen with space left is not
an argument for putting something in it.

| Needed… | Do this | Failure if you get it wrong |
|---|---|---|
| always, by everyone | **show** — visible, no interaction | user hunts for the thing they need every time |
| sometimes, by most | **collapse, expanded by default** | a daily value costs a click forever |
| rarely, by some | **collapse, collapsed by default** | permanent visual tax on everyone else |
| almost never, by almost nobody | **move it elsewhere, or delete it** | the 2% feature crowds the 98% one |

"Rarely" is decidable: during your walkthrough, did you open it? Would the persona in
[audience.md](audience.md) open it in a normal week? If neither, it is not front-page content.

| # | Check | Fails when | Principle |
|---|---|---|---|
| P1 | How many of the visible fields did you actually read to make the decision on this screen? | ≤2 of 8+ visible | `cognitive-load` |
| P2 | Can this block be reduced to **one line with detail one click away**? | yes, and it currently takes 9 rows | `optimal-information-flow` |
| P3 | Does the user **compare a value across items**? | comparing, but rendered as cards | `law-of-similarity` |
| P4 | Is each item an individual thing you act on, with an image or status? | acting individually, but rendered as a dense table | `law-of-common-region` |
| P5 | Is anything shown collapsed that every user opens every time? | you opened it on every visit | `pareto-principle` |
| P6 | Is anything shown expanded that you never opened? | expanded, unread, occupying above-the-fold | `selective-attention` |
| P7 | Are IDs, timestamps, and internal codes shown to a non-technical audience? | raw UUID in the primary column | `mental-model` |
| P8 | Does the empty state teach the next action, or just say "No data"? | dead-end empty state | `paradox-of-the-active-user` |
| P9 | Is there exactly one visual emphasis per view, or several competing? | 3 primary buttons in one frame | `von-restorff-effect` |

Table vs cards is one question, and it has one answer: **compare across items → table; act on one
item → cards.** A card grid where users scan for the cheapest plan is a table someone made pretty.
A table of eleven columns where users only ever open one row is a list someone made exhaustive.

Evidence: a screenshot with a count — "9 fields visible, 2 used" — or the click record showing the
collapse was opened every time / never.

Proposal shape: *collapse X to a one-line summary showing `<the 2 fields you used>`; move the rest
behind "Details".* Name the fields. "Reduce clutter" is not a proposal.

Visual detail — spacing, type scale, colour, icon use — is [hierarchy.md](hierarchy.md). Do not
re-derive it here.

### Axis 3 — Flow and frequency

*Does the sequence match how a person thinks about the task?*

| # | Check | Fails when | Principle |
|---|---|---|---|
| F1 | Say the task out loud as a human would ("pay this invoice"). Does the screen order match that sentence? | UI order is table-shaped, not task-shaped | `mental-model` |
| F2 | Is any step ordered by system convenience — parent record before child, ID before name? | you had to create a thing to name a thing | `optimal-information-flow` |
| F3 | Is anything demanded before it is **knowable**? | field asks for a value produced by a later step | `optimal-information-flow` |
| F4 | Does any step require a value the user must fetch from outside the product? | tab-switch mid-flow | `working-memory` |
| F5 | Is a rarely-used feature holding prime space (first tab, primary button, top nav slot)? | quarterly action in the daily slot | `pareto-principle` |
| F6 | Is a daily action buried ≥3 levels deep, or behind a kebab menu? | daily action needs 3 clicks to reach | `fitts-law` |
| F7 | Does the flow show progress and a knowable end? | multi-step wizard with no step count | `goal-gradient` |
| F8 | On error, is the entered data preserved? | form clears on validation failure | `working-memory` |
| F9 | Does completing the task return you to where you started, or strand you? | lands on an unrelated screen | `flow` |

Evidence: the screenshot sequence in the order you actually hit it, plus any backtrack. A backtrack
*is* the evidence for F2 and F3 — you went back because the flow asked for something you did not
have yet.

Proposal shape: **reorder before you remove.** The same fields in a different order carry a
different load, because load is a function of what must be held simultaneously, not of the total.
Reordering costs nothing in data and is usually the bigger win — see
`/Users/shankhajeettaran/workspace/learning/research/behavioral-design/03-behavioural-design-toolbox-20-techniques.md`
(§18, Optimal Information Flow). Teams reach for deletion first because it is more visible.

### Axis 4 — Cognition

*Load, hierarchy, grouping, scan path, and what the user has to carry.*

| # | Check | Fails when | Principle |
|---|---|---|---|
| C1 | How many values must the user carry across a screen boundary unaided? | >4 | `working-memory` |
| C2 | Is any of the load **extraneous** — decoration, inconsistent labels, state the system could have held? | same concept has two names on two screens | `cognitive-load` |
| C3 | Do groups on screen match the real structure of the data? | related fields split across two panels | `law-of-proximity` |
| C4 | Where a boundary is drawn (card, panel, rule), does it enclose exactly one real group? | box spans two unrelated groups | `law-of-common-region` |
| C5 | Is grouping done with the **weakest cue that succeeds**, or does every group get a box? | nested cards 3 deep | `law-of-common-region` |
| C6 | In a genuinely sequential flow, is the most important thing first and the action last? | key concept in the middle of a 5-step wizard | `serial-position-effect` |
| C7 | Is there exactly one isolate — one element that differs on a pre-attentive dimension? | zero (nothing leads) or three (nothing leads) | `von-restorff-effect` |
| C8 | Where does the eye land first, and is that the thing the task needs? | eye lands on the banner, task lives bottom-right | `selective-attention` |
| C9 | Does the label vocabulary match the user's words or the database's? | "Entity" in the UI, "customer" in the user's mouth | `mental-model` |

Two scope traps, both common enough to name:

- **`serial-position-effect` applies to sequences that are presented one at a time and are no longer
  visible** — wizards, onboarding, spoken flows. It applies weakly at best to a persistent
  horizontal nav bar, which is simultaneously visible and spatially arrayed. Arguing nav order from
  memory research is the most common scope violation in this library; argue it from `fitts-law`
  (screen edges are infinitely deep targets) and from click data instead. Source:
  `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/01-cognitive-load-and-memory.md`.
- **Frequency data beats every cognitive argument.** If analytics say users click the middle item
  most, the middle item stays. Serial position and Von Restorff are weak effects relative to
  learned habit.

Evidence: a numbered list of the values carried between screens (that is C1, exactly), or a blurred
/ squinted screenshot showing the perceived groups. Blur the frame and count the units — if the
count does not match the real structure, C3 or C4 has failed and it will fail silently otherwise.

Proposal shape: *carry `<value>` forward in the URL / show it in the header of step 3* for C1;
*close the gap between `<a>` and `<b>` and open it before `<c>`* for C3. Never "reduce cognitive
load" — that is the diagnosis, not the change.

Visual specifics of hierarchy, contrast, type scale and breathing room live in
[hierarchy.md](hierarchy.md).

### Axis 5 — Responsiveness

The method is [responsive.md](responsive.md). Read it there.

The only thing that belongs in a critique is the **pass condition**:

> Every finding is checked at three widths — desktop, tablet, phone — before it is reported. A
> layout verified only at desktop is reported as **unverified**, not as passing.

Failure behaviour: if you did not resize, do not write "responsive: fine". Write it into §7 as
`not checked: tablet/phone widths — walkthrough ran at 1440px only`. An unchecked width silently
reported as passing is worse than an admitted gap, because the reader will act on it.

A finding that only exists below 768px is still a finding; label its scope `template-level` if the
layout is shared, and say which other pages use that template.

---

## 3. Severity — a decision rule, not a vibe

| Severity | Condition |
|---|---|
| `blocker` | The user **cannot complete the goal** by any path they would find, **or** data loss is possible. |
| `high` | The goal is completable, but the cost is disproportionate to its value — **or** a mistake is likely and recovery is hard. |
| `medium` | Measurable friction with a clear, bounded fix. |
| `low` | Real, observed, small. |
| `nit` | Cosmetic, optional, and you would not fight for it. |

**Tie-break, when a finding sits between two levels:** ask *what happens to the user who hits this
and does not know the workaround.* If they stop, it is the higher level. If they grumble and carry
on, it is the lower one. Do not split the difference — a severity that means "somewhere between
high and medium" tells the reader nothing about whether to fix it this week.

**Irreversibility promotes severity by one level.** A delete with no undo, a submit that fires an
email, an overwrite of the user's draft — each moves up one rung. The reason is that severity is a
proxy for expected harm, and expected harm includes the cost when the user is wrong, not only the
cost when the flow is followed correctly.

Severity does **not** account for how often the thing is used. That is `priority`. Keep them
separate — see §4.

An unobserved finding carries no severity at all. Write it `F-nn [UNOBSERVED]` and say what you
would need to click to grade it.

---

## 4. Ranking

```
priority = (Δ HCS × frequency) / build cost
```

- **Δ HCS** — how many Human Cost Score points the fix removes, from the ledger. Not a guess.
- **frequency** — times per user per month the task runs. From the user, from analytics, or stated
  as an assumption you can be corrected on.
- **build cost** — `S = 1`, `M = 3`, `L = 8`. State which and what it touches.

A worked set. Same surface, one review pass:

| ID | Sev | Finding | Δ HCS | Freq/mo | Build | Priority |
|---|---|---|---|---|---|---|
| F-03 | medium | Invoice list has no bulk "mark paid"; done one at a time | 9 | 40 | S (1) | **360** |
| F-01 | high | Currency re-typed on every line item; system already knows it | 4 | 60 | S (1) | **240** |
| F-05 | medium | Status filter resets on back-navigation | 3 | 50 | S (1) | **150** |
| F-02 | high | Export needs a date range that is already in the page filter | 6 | 8 | S (1) | **48** |
| F-07 | blocker | Bulk import fails silently over 500 rows; no error, no partial report | 20 | 1 | M (3) | **6.7** |
| F-04 | medium | Customer detail opens a full page to edit one field | 5 | 4 | M (3) | **6.7** |
| F-06 | low | Column order does not match the printed statement | 2 | 6 | M (3) | **4** |
| F-08 | high | Tax-settings page unusable below 768px | 7 | 0.3 | L (8) | **0.26** |

Ranked: **F-03 · F-01 · F-05 · F-02 · F-07 = F-04 · F-06 · F-08**.

Read that ordering carefully, because it is the point of the formula: **F-07 is a blocker and it
ranks fifth.** A blocker on a task run once a month, costing three days to fix, does less total harm
than a missing bulk action on a task run forty times a month and fixable in an afternoon. Severity
answers "how bad is it when you hit it"; priority answers "what should be built first". They are
different axes and a report that collapses them into one list will either ship the wrong fix first
or bury the dangerous one.

So report both, and say the sentence out loud when they disagree: *"F-07 is the most severe finding
and the fifth most valuable to fix. Fix F-03 first; schedule F-07 because silent data loss is not
something to leave open regardless of rank."*

When frequency is unknown, say so and use the persona's plausible number — then mark it. A ranking
built on an invented frequency is fine as long as the invention is visible and correctable.

---

## 5. What NOT to report

This is the hardest discipline in the file, and the one that decides whether anything gets fixed.

**Cap the report at 8–12 findings.** A 40-item list is not thoroughness, it is a refusal to
prioritise, handed to someone who now has to prioritise it themselves — so nothing gets done and
the review gets ignored. If you have 30 candidates, the ranking in §4 already told you which 10 to
keep. Keep those. Say "22 further findings below `medium` were dropped" and stop.

Never report:

1. **A preference with no principle behind it.** "I'd use a drawer here" is not a finding.
   `why.py --symptom` returned nothing → either find the real principle or drop it.
2. **A finding you did not observe.** If it came from reading the component, it is `[UNOBSERVED]`
   and it carries no severity. If it came from an assumption, it is not a finding at all.
3. **The same root cause under three names.** "Too many fields", "form feels long", "high cognitive
   load on step 2" are one finding. **Merge them** and report the root cause with all three
   symptoms as evidence. Three-way duplication is how a review inflates its own importance and
   loses the reader's trust in one reading.
4. **A style disagreement with a deliberate brief.** If the team chose a dense table because their
   users are traders who want density, "it feels cluttered" is you reviewing the brief, not the
   build. Ask whether the brief exists before you argue with it.
5. **Findings about surfaces you did not walk.** They go in §7.

**The rule that settles every borderline case:**

> If you cannot name (a) what the human experiences and (b) what to change — it is not a finding.

Test it on the candidate. "The information architecture is unclear" fails (a) and (b). "On
/settings/team, the invite button is inside the Roles panel, so you look for it under Members
first — I did, twice — move it to the Members panel header" passes both, and takes one sentence
each.

---

## 6. The Aesthetic-Usability trap

Principle id `aesthetic-usability-effect`. Run `python3 scripts/why.py --name
aesthetic-usability-effect` and quote the grade the row prints — do not assert a grade from memory.

What it does to *you*: a beautiful surface gets graded generously. The one part of this literature
that nobody disputes is the part that matters here — **visual polish suppresses usability problem
reports in testing.** NN/g state it directly; that claim survives even in the study that contradicts
the rest (Tuch et al. 2012 found aesthetics did *not* affect perceived usability). So treat this as
a bias to control in measurement, not an effect to chase in design. Full argument and the three
conflicting studies:
`/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/03-gestalt-and-perception.md` (§6).

Two more properties worth knowing because they change where you should be suspicious:

- The effect covers **minor** problems only. A beautiful checkout that drops a payment method loses
  the halo instantly. So polish inflates your medium/low findings, not your blockers.
- It operates on **first** impressions and decays with use. You are a first-time user of every
  surface you review. You are maximally exposed.

**Counter-procedure — mechanical, do it in this order:**

1. **Score the effort ledger before you form a visual impression.** Count clicks, fields, waits,
   backtracks first. Counting is halo-proof; rating is not.
2. **Ask the two questions separately and log them separately.** "How did that task go?" and "How
   does this look?" Positive comments about visuals are not usability evidence.
3. **Re-read your finished findings once, asking one question: which of these did I soften because
   the screen looks good?** Look for hedges — "slightly", "could perhaps", "minor". Each hedge is a
   place to re-check the count. Promote or delete; do not leave a softened finding standing.
4. **Watch for the inverse.** An ugly surface gets graded harshly, and you will over-report styling
   on it while under-reporting the 12-click flow. The ledger protects you in both directions.
5. **If the surface tests well and the ledger is bad, trust the ledger.** The canonical failure is a
   redesign that scores higher on satisfaction and lower on task completion, and ships because
   satisfaction is the number on the slide.

---

## 7. The report skeleton

Emit exactly these sections, in this order.

```
1  Audience            who this is for, and how long they sit here     → audience.md
2  What was walked     surfaces, screenshot count, what you did NOT reach
3  Effort ledger       HCS total + components + the per-step table     → effort-ledger.md
4  Findings            ranked; 8–12 max; contract finding format
5  Not checked         each gap with the reason
6  The one change      a single recommendation
```

Compact filled example:

```
AUDIENCE   Accounts-payable clerk, non-technical, 20–40 min/day in this screen,
           runs the invoice list many times a day and the tax settings ~4×/year.

WALKED     /billing/invoices · /billing/invoices/:id · /billing/export
           14 screenshots. Not reached: bulk-import flow (needs a >500-row file),
           tablet + phone widths on /billing/export.

LEDGER     Goal: mark 12 delivered invoices as paid.
           HCS 34 (I:18 D:6 M:4 W:3 R:3)   theoretical minimum: I:13
           Worst step — step 4, "open invoice → mark paid → back": ×12.

FINDINGS   ranked by priority; severity shown separately

F-03  [medium]  scope: page-level   axis: effort
  screen    /billing/invoices
  observed  screenshot 06 → 09
  action    opened invoice, clicked "Mark paid", navigated back — repeated 12×
  cost      36 clicks · 12 waits >400ms · 12 context switches
  principle pareto-principle [replicated] · conflicts: choice-overload
  problem   The clerk's most frequent task is only available one row at a time.
  proposal  Add row checkboxes and a "Mark paid" bulk action in the list header.
  build     S · invoice list table only; no API change (endpoint takes an id array)

F-01  [high]  scope: template-level   axis: effort
  screen    /billing/invoices/:id
  observed  screenshot 10 → 11
  action    re-typed currency on each line item after selecting it on the header
  cost      3 keystrokes × n line items · 1 backtrack when it mismatched
  principle working-memory [replicated] · conflicts: —
  problem   The user re-enters a value the invoice already holds, and can contradict it.
  proposal  Default line-item currency to the invoice currency; keep it editable.
  build     S · shared line-item form; touches invoices, credit notes, quotes

  … 6 more findings …

NOT CHECKED
  tablet/phone on /billing/export — walkthrough ran at 1440px only. Reported as
    unverified, not as passing.
  bulk import >500 rows — needs a fixture file I do not have. F-07 is [UNOBSERVED].
  print stylesheet — out of scope for this pass.

THE ONE CHANGE
  Add bulk select + "Mark paid" to the invoice list (F-03). It removes 24 of the
  34 HCS points on the task this clerk runs most, it is an afternoon of work on one
  table component, and it does not change the API. Do this before anything else in
  this report.
```

End on **one** recommendation. Not three, not "quick wins". The user has to walk into a planning
meeting and say a sentence; give them the sentence. Everything else is ranked below it and will
still be there next sprint.

Turning the accepted findings into a designed proposal — options, trade-offs, what to build — is
[brainstorm.md](brainstorm.md).

---

## Stopping

One review pass. One batched report. At most one follow-up round to confirm fixes landed. Then
hand it over. Re-walking a surface to find finding number 13 spends the user's money to reproduce
what the first pass already ranked below the cut line.
