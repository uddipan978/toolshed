# The effort ledger

Turns "this feels clunky" into a number someone can argue with.

The Human Cost Score is fixed:

```
HCS = Interaction + Decision + Memory + Wait + Recovery
```

Report it as `HCS 69 (I:37 D:15 M:10 W:7 R:0)` plus the per-step table. Never report a bare total —
it hides where the cost is, and where the cost is *is* the recommendation.

You build this from an observed walkthrough. If you have not driven the flow, you have no ledger.
See [walkthrough.md](walkthrough.md). Findings built on a ledger get written up per
[critique.md](critique.md).

## 1. Why count

An opinion about a UI cannot be checked, so it cannot be beaten. "The invite flow is clunky" has no
reply except "I disagree." "The invite flow costs 12 steps, 2 items held in the head, and 8 seconds
of waiting" has three replies, all of them useful: recount it, dispute a weight, or fix it and
re-score.

The ledger exists for two jobs:

1. **Before/after comparison.** A redesign without both scores is a claim, not a result.
2. **Stopping you from proposing changes you never priced.** Counting forces you to walk every step,
   including the four boring ones you would otherwise summarise away. Most flows are not bad at the
   dramatic step; they are bad because of six cheap steps nobody counted.

The score is a **comparison instrument**. It is not a truth about the interface. Read §7 before you
quote it to anyone.

## 2. The five components

### Interaction — clicks, keystrokes, scrolls, navigations

**Counting rule.** Count physical acts, weighted by `data/effort-weights.csv`:

| What | Counted as | Why |
|---|---|---|
| A click or tap | 1 `click` (1.0) | The atomic unit. |
| Entering a field | 1 `field-entry` (1.5), or `field-entry-typed` (2.5) when they must type rather than pick, **plus** `keystroke-char*N` (0.1 each) | Focusing and committing a field is the act; the characters are cheap and near-automatic. |
| Scrolling | 1 `scroll-screen` (0.8) per **screenful**, not per wheel notch — or `scroll-to-find` (2.5) when they are hunting | The cost is re-finding your place, and that happens once per screen. Hunting costs more than scrolling, because it includes not knowing when to stop. |
| Moving to another screen | `navigation-new-page` (4.0), or `navigation-same-page` (1.5) for an in-page jump | Includes re-orientation, not just the click that caused it. |

**What does not count.** Reading. Hovering. Looking. Deciding — that is Decision, and counting it
here double-charges the user. A click that both navigates and decides is counted once in each
column; those are different costs paid by different faculties.

**Governing principle.** `fitts-law` for the pointing cost, `doherty-threshold` for why a navigation
costs more than a click. Run `python3 scripts/why.py --symptom "too many clicks"` for the full row.

**Micro-example.** Typing `dana@acme.io` into an email field with no autocomplete:
`field-entry-typed 2.5 + keystroke-char*12 (12 × 0.1) = 3.7`. Not 12. Not 13.

**Most common miscount: counting each keystroke as a click.** Typing an email becomes 22 actions,
the form looks like the problem, and you propose cutting a field when the real cost was the four
navigations wrapped around it. If you find yourself recommending "fewer form fields" on a flow whose
I is dominated by typing, recount before you write the finding.

### Decision — Σ log2(options + 1) at each choice point

Principle id `hicks-law`. **Counting rule.** At each point where the user must classify, count the
visible alternatives `n` and add `log2(n + 1)` bits. The `+1` is the option of not responding yet —
the user must also decide *whether* to act. `effort.py` charges **1.0 per bit** and derives this
from the row's `options` column, so you record the option count and the script does the arithmetic.

If you would rather name the band than count exact options — useful when the choice is a menu you
did not fully enumerate — `effort-weights.csv` also carries explicit slugs: `decision-binary` (1.6),
`decision-3-to-7` (2.6), `decision-over-7` (3.7). Use one or the other on a row, never both, or the
choice is charged twice.

**Why logarithmic and not linear.** Hick and Hyman measured reaction time against transmitted
information, not item count, and it lands on a line: `RT = a + b·H`. Doubling the options does not
double the time — 20 → 22 options costs almost nothing, 2 → 4 costs a lot. A linear model would tell
you to delete a 200-item country list; the log model tells you a country list is nearly free and the
five near-identical plan names are not. The log is what makes the score point at the right screen.

**What counts.** A choice the user must actually make, in this session, without an installed habit.
**What does not:** a choice already resolved this session, and a habitual destination like the global
nav an admin clicks daily. Hick's law is a law about **unpractised** choice; with practice the slope
`b` flattens dramatically, and pricing a daily nav click at 3 bits makes every score dominated by
navigation the user does not think about. That cost still lands — in Interaction, where it belongs.
**When you do not know whether the user is practised, count it and say so in the row.** An
overcounted D you flagged is recoverable; a silent one is not.

**The caveat you must state, every time.** Hick's Law assumes options that are equiprobable and
scannable at a glance. Real interfaces routinely violate both, in both directions:

- **It OVERSTATES** an alphabetised country list of 200. `log2(201) ≈ 7.7` bits is nonsense — the
  user does not classify 200 items, they jump to the letter. Scannable, ordered, mutually exclusive
  options cost far less than the formula says.
- **It UNDERSTATES** eight similarly-worded buttons — "Save", "Save and close", "Apply", "Update",
  "Commit", "Publish", "Submit", "Confirm". `log2(9) ≈ 3.2` bits is nowhere near the truth, because
  the user must *comprehend* each label before classifying. When items must be read to be
  distinguished, cost is closer to linear in `n`.

Write the caveat into the row: `D 3.70 (overstates — alphabetised, scannable)`. A formula applied
past its assumptions is how measurement launders a bad recommendation: the number gives a wrong
instinct the authority of arithmetic, and nobody audits arithmetic.

Source: `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/02-interaction-and-system-response.md`, §2 Hick's Law.

**Most common miscount: counting the option the user was always going to pick.** A highlighted
default, a "Most popular" badge, or a remembered last choice collapses the probability distribution,
and Hyman's entropy form says `H` collapses with it. A ten-item menu where one item is chosen 90% of
the time is ~0.7 bits, not 3.5. If the interface has a real default, score the real default.

### Memory — items carried between screens

**Counting rule.** Two numbers per step:

- `carry_new` — items the user must commit to memory **at this step**, because they will need them
  later and they will not be on screen. Each item is priced **once**, at pickup.
- `carry_held` — total items being held while on this step, including the new ones.

`M = Σ carry_new × memory-item`. Separately report `peak carry = max(carry_held)`.

**The ceiling is ~4, not 7±2.** Cowan (2001) puts working memory at 4 ± 1 chunks when rehearsal and
covert grouping are controlled; the familiar 7±2 was inflated by participants silently chunking.
Principle id `working-memory`. The row `millers-law` exists and is graded **`contested`** for exactly
this use — if you cite 7±2 as a capacity limit, you must attach that grade or not cite it. Plan
against 4.

**What counts.** Anything the user must copy, remember, hold, or scroll back to retrieve: a
reference number shown two screens ago, an email address they must retype, the role name they picked
that a later screen calls something else. **What does not:** a value visible on the current screen —
that is visual search, priced in Interaction. Breadcrumbs, step indicators and a sticky order summary
are the system holding the item instead of the user; when they are present, `carry_new` is 0.

**Micro-example.** A flow shows an invoice number on screen 3, hides it on screen 4, and asks for it
on screen 6. `carry_new = 1` at step 3. Steps 4, 5 and 6 record `carry_held = 1` and `carry_new = 0`.
`M = 1 × 2 = 2`. Peak carry = 1.

**Most common miscount: charging the item once per step it is held.** The example above scores 4× if
you add `carry_held` instead of `carry_new`, and now a long flow looks like a memory failure when it
is a length problem. The item was memorised once. The `carry_held` column exists only to compute the
peak against the ceiling of 4 — when peak carry exceeds 4, that is a finding regardless of what M
totals.

Source: `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/01-cognitive-load-and-memory.md`, §2 Miller's Law and §3 Working Memory.

### Wait — transitions over 400ms

**Counting rule.** Band the observed delay, then weight the band:

| Observed | Action slug | Note |
|---|---|---|
| < 400ms | — | Free. Not counted. |
| 400ms – 2s | `wait-400ms-2s` | Noticed; thought flow survives. |
| 2s – 10s | `wait-2s-10s` | Attention leaks; task state starts decaying. |
| > 10s | `wait-over-10s` | The user leaves the task. |

The slugs are the `action` values in `data/effort-weights.csv`; `effort.py` exits 1 on any other
string, so copy them exactly. The 400ms boundary is `doherty-threshold`. The bands above it follow
Miller's 1s and 10s thresholds, which are older and better specified than Doherty's single number.

**How to measure with the tools you actually have**, in order of preference:

1. **`read_network_requests`** — the gating request carries real timings. The only measurement that
   is not a guess. Use it whenever a network call is what the user is waiting on.
2. **Spinner presence between screenshots.** Screenshot N shows a spinner, N+1 does not: you have
   evidence of a wait but not its length. Record the band you can defend and name the evidence — a
   spinner that survived a deliberate 1s pause is ≥1s, and that is a real bound.
3. **Neither available** → `unmeasured`.

**Never record 0 for a wait you did not time.** Zero is a claim that the transition was fast, and it
is the single easiest way to make a slow flow score well. `effort.py` excludes `unmeasured` rows from
the W total and reports them separately: `W:8 (+1 unmeasured)`. An unmeasured wait is visible; a
fabricated zero is not.

**Most common miscount: timing the spinner instead of the transition.** The clock starts when the
user acts and stops when they can act again. A 200ms request followed by 900ms of client-side render
is a 1.1s wait, and the network panel will happily tell you it was 200ms.

Source: `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/02-interaction-and-system-response.md`, §3 Doherty Threshold.

### Recovery — steps to undo the most likely mistake

**Counting rule.** At each **commit point** — any step that writes, sends, charges, publishes, or
deletes — ask what the most likely mistake is, then count the interaction steps needed to get back to
the pre-mistake state.

**Two different quantities live under the word "recovery", and confusing them is the most common
mistake in this whole file.**

**Observed recovery — this is what the ledger scores.** Recovery actions the human actually
performed on the run you watched: a wrong turn, an error, an undo. They get their own rows, with
the real slugs from `data/effort-weights.csv`:

| What happened | `action_type` | Weight |
|---|---|---|
| Hit an error and had to read it | `error-encountered` | 6.0 |
| Worked back out of it | `error-recovered` | 3.0 |
| Navigated backwards to redo something | `backtrack` | 3.0 |
| Reversed it with one visible control | `undo-single-action` | 1.0 |
| Reversed it across several steps | `undo-multi-step` | 6.0 |
| Had to confirm a destructive action | `confirmation-dialog` | 2.5 |
| Did something with no path back | `irreversible-action` | 12.0 |

These are **summed**, like every other component — if the human hit two errors, they paid for both.
`effort.py` routes any `error-*`, `undo-*`, `backtrack`, `confirmation-dialog` or
`irreversible-action` row into R automatically, by name.

**`R:0` therefore means "nothing went wrong on this run", not "this flow is safe."** A clean run
scores zero recovery. That is the correct score and it is not praise.

**Latent recovery risk — this is a finding, not a number.** At each **commit point** — any step that
writes, sends, charges, publishes, or deletes — ask what the most likely mistake is and what it
would cost to undo. Do not add this to the score: you did not observe it, and this skill's first
hard rule is that unobserved things are not stated as fact. Take the **worst** commit point in the
flow (a user makes one mistake at a time, so summing prices a user who makes every mistake, which is
not a user) and emit it as a finding. Irreversibility is an automatic `blocker`.

**Irreversible is an automatic blocker.** Emit the finding immediately, in the standard format:

```
F-03  [blocker]  scope: page-level   axis: effort
  screen    /settings/members
  observed  screenshot 09 → 10
  action    clicked "Remove", confirmed in dialog
  cost      R: irreversible — no undo, no restore, no audit trail entry
  principle working-memory [replicated] · conflicts: —
  problem   A misclick on the wrong row permanently deletes a teammate's access
            and history, and the confirm dialog does not name who is being removed.
  proposal  Name the member in the confirm dialog, and replace hard delete with a
            30-day soft delete plus an "Undo" toast.
  build     M · members table + membership delete endpoint + a restore path
```

**Most common miscount: scoring 0 because the browser Back button exists.** Back is not undo. It
reverses navigation, not a committed server-side action, and on a flow that already submitted it
often re-submits. If your recovery path is Back, the recovery path does not exist — count the real
steps, or `irreversible`.

**Why recovery is weighted above a forward step.** A recovery step is unplanned, performed under
mild alarm, and taken by a user who has just learned the interface can hurt them. Run
`python3 scripts/why.py --symptom "afraid to click"` for the governing row and its evidence grade.

## 3. The per-step table

One row per **action**, not per narrative step. Every cell filled — an empty cell is an uncounted
cost, not a zero.

**Worked example: "Invite a teammate and give them Editor access to the Atlas project."**
Observed 2026-08-09, desktop 1440px, admin user, first time performing this task.

The table below is `effort.py`'s own output for the ledger in §8, not hand arithmetic. If you change
a weight, rerun it — do not edit these numbers.

| # | Screen | `action_type` | Wait | I | D | M | W | R | Total |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `/dashboard` | navigation-new-page | 320ms | 4.0 | 0 | 0 | 0 | 0 | 4.0 |
| 2 | `/settings` | tab-switch (9 tabs) | 610ms | 2.0 | 3.3 | 0 | 1.0 | 0 | 6.3 |
| 3 | `/settings/members` | scroll-to-find | 0ms | 2.5 | 0 | 0 | 0 | 0 | 2.5 |
| 4 | `/settings/members` | modal-open | 0ms | 2.0 | 0 | 0 | 0 | 0 | 2.0 |
| 5 | modal | field-entry-typed | 0ms | 2.5 | 0 | 0 | 0 | 0 | 2.5 |
| 6 | modal | keystroke-char\*12 | 0ms | 1.2 | 0 | 0 | 0 | 0 | 1.2 |
| 7 | modal | select-from-short-list (5) | 0ms | 2.0 | 2.6 | 5.0 | 0 | 0 | 9.6 |
| 8 | modal | click — "Send invite" | 2400ms | 1.0 | 0 | 0 | 4.0 | 0 | 5.0 |
| 9 | `/settings/members` | read-instruction | 0ms | 3.0 | 0 | 5.0 | 0 | 0 | 8.0 |
| 10 | `/settings/members` | navigation-new-page | 890ms | 4.0 | 0 | 0 | 1.0 | 0 | 5.0 |
| 11 | `/projects` | scroll-to-find (12) | 1200ms | 2.5 | 3.7 | 0 | 1.0 | 0 | 7.2 |
| 12 | `/projects/atlas` | tab-switch (6 tabs) | 340ms | 2.0 | 2.8 | 0 | 0 | 0 | 4.8 |
| 13 | `…/access` | modal-open | 0ms | 2.0 | 0 | 0 | 0 | 0 | 2.0 |
| 14 | modal | field-entry-typed | 0ms | 2.5 | 0 | 0 | 0 | 0 | 2.5 |
| 15 | modal | keystroke-char\*12 | 0ms | 1.2 | 0 | 0 | 0 | 0 | 1.2 |
| 16 | modal | select-from-short-list (4) | 0ms | 2.0 | 2.3 | 0 | 0 | 0 | 4.3 |
| 17 | modal | click — "Save" | unmeasured | 1.0 | 0 | 0 | 0 | 0 | 1.0 |
| | | **subtotal** | | **37.4** | **14.7** | **10.0** | **7.0** | **0.0** | **69.1** |

```
HCS 69 (I:37 D:15 M:10 W:7 R:0)   1 of 17 steps unmeasured — W is a floor, not a measurement
```

Round once, at the end. Rounding each row first drifts the total by several points on a long flow.

Read the table before the total. Three facts are visible in it and invisible in `69`:

- **Steps 9–17 exist only because step 7 did not ask about projects.** More than half the flow is a
  second errand caused by an omission in the first.
- **The two carried items cost 10 — a seventh of the whole score — and both are vocabulary
  mismatches.** The email must be retyped because there is no autocomplete; the role must be
  remembered because "Editor" at step 7 is called "Can edit" at step 16. Neither is a memory problem.
  Both are naming problems that present as memory problems, and renaming is far cheaper than
  building a memory aid for the wrong diagnosis.
- **`R:0` is not praise.** No recovery action was performed because no mistake was made on this run.
  It says nothing about what a mistake would have cost — see the Recovery section above for why that
  is a separate finding rather than a score component.

## 4. Reading the score

The components matter more than the total. Each has one dominant fix class.

| Signal | What it means | Fix class |
|---|---|---|
| **High I, low D** | Tedium. The user knows exactly what to do and has to do it many times. | Batch it, bulk-select it, or supply a default. Never "simplify" — nothing is confusing. |
| **High D** | Confusion. The user is being made to classify. | Reduce the set, rank it, or mark a recommended option. Ranking is free; deletion is not. |
| **High M** | A layout failure, not a memory failure. Things needed together are not together. | Put them on one screen, or carry them forward in the UI. The system has unlimited memory; use it. |
| **High W** | Engineering, not design. | Optimistic UI, prefetch on intent, acknowledge locally within 100ms. Do not redesign a screen to hide a slow endpoint. |
| **High R** | Fear. | Undo over confirm; soft delete over hard delete; name the object in the dialog. |

**High R deserves its own warning.** Fear does not stay at the risky step. A user who has been burned
once slows down *everywhere* — re-reading labels, re-checking selections, abandoning flows they would
otherwise complete. When R is high, say in the finding that the measured HCS understates the flow.

**Do not average the components.** An HCS of 62 that is all Interaction is a boring flow; an HCS of
62 carrying an `irreversible-action` is a dangerous one, and it is a blocker at the same score.

## 5. Comparing before and after

**Never report a redesign without both scores.** A proposal with only an "after" number is a
prediction wearing the costume of a measurement.

Report three things, in this order. The "after" below is fix A from §6 — the invite modal also takes
a project and a role, so steps 7–12 of the worked example stop existing.

Score both ledgers with the script rather than estimating the "after" —
`python3 scripts/effort.py --compare before.csv after.csv --frequency 156`:

```
before  HCS 69 (I:37 D:15 M:10 W:7 R:0)    17 actions
after   HCS 30 (I:17 D:8  M:0  W:5 R:0)     8 actions
delta   HCS -39 (I:-20 D:-7 M:-10 W:-2 R:+0)

read  the saving is mostly Interaction (-20 of -39). Name that in the finding — a delta with
      no named component is a number nobody can check.
      1 step across both ledgers has no wait_ms, so the W delta is a floor.
      156 uses/year x 39 HCS = 6084 HCS-units a year saved.
```

The per-component delta is the part that gets read. `−39` tells a reviewer nothing about whether you
fixed the right thing; `M:−10` tells them you removed both carried items by renaming one field and
adding autocomplete, and `R:+0` tells them you did not touch recovery at all — which is honest, and
invites the reviewer to ask whether you should have.

**Frequency is not optional, and it usually decides the argument.** A 6-point saving on a daily task
(`6 × 250 = 1,500`/yr) beats a 30-point saving on a quarterly one (`30 × 4 = 120`/yr). The quarterly
fix is five times the improvement and one twelfth the value.

**When you cannot get a usage number, say so and state the assumption you used** — "assuming ~3/week;
at 3/month this drops below fix B and should not be built first." A stated assumption gets corrected
by the one person in the room who knows the real number. An unstated one does not.

## 6. Pricing the fix

The other half, and the half agents skip. Every proposal carries a build cost and a scope.

**Build cost.** `S` = a day or less, one file. `M` = a few days, several files or an endpoint.
`L` = a week or more, or it needs a migration or a design decision that is not yours. For ranking:
`S=1, M=3, L=8`.

**Scope.** `global` (nav, shell, tokens — every screen), `template-level` (a layout many pages
share), `page-level` (this screen only). State what else it touches. Scope is a **risk** measure, not
a cost measure — a global string rename is `S` build and `global` scope, and both facts matter.

**Ranking rule:** `priority = (Δ HCS × frequency) / build cost`. Applied to five candidates on the
invite flow above:

| Fix | Scope | Δ HCS | Uses/yr | Build | Priority | Verdict |
|---|---|---|---|---|---|---|
| A. Invite modal also takes project + role | template-level | 27 | 156 | M (3) | **1404** | Build first. It deletes five steps. |
| B. Autocomplete email from the directory | page-level | 4 | 156 | S (1) | 624 | Build. Cheap; kills a retype and a carried item. |
| C. Rename "Can edit" → "Editor" | global | 2 | 156 | S (1) | 312 | Build. Global scope, trivial cost — check the other 4 surfaces using the string. |
| D. Move "Invite" above the members table | page-level | 1 | 156 | S (1) | 156 | Build if you are in the file anyway. |
| E. Promote "Members" to the top-level nav | global | 7 | 156 | L (8) | **137** | Do not build for this. |

**Score every candidate against the *current* flow, then re-score after building the top one.**
Deltas are not additive: A already removes the retype that B fixes and the vocabulary mismatch that
C fixes, so a post-A re-walk drops B and C to roughly zero. Adding this column up gives 41 points of
saving on a 62-point flow, which is arithmetic nobody should believe.

**Why E loses, and how to argue with the ranking.** E has the second-largest Δ in the table and
still ranks last: the cost is `L`, it regresses eleven screens you did not walk, and it invalidates
the location habit of every existing user. **Say that out loud in the proposal.** If you genuinely
believe the nav change pays, the honest move is to re-score it against the three other tasks that
share that nav and show the combined frequency — not to inflate its Δ against one task. A global
change scored on a single flow will always lose, and it should.

**A proposal with no build cost is a wish.** If you cannot estimate it, say `build: unknown — needs
<the specific thing you do not know>` and rank it last. Do not guess `S` to make the arithmetic work.

## 7. Honest limits

The score is a comparison instrument, not a truth. It does not capture:

- **Emotion.** A flow can be efficient and humiliating. The score cannot see a tone problem.
- **Trust.** Two flows scoring identically differ enormously if one asks for a card number before it
  shows a price.
- **Aesthetic pleasure.** The aesthetic-usability effect is real and the ledger is blind to it.
- **Learnability over repeated use.** This is the big one. **A flow that scores worse on day one may
  score far better on day thirty**, because habitual choice points drop out of D and practised
  motions get cheaper. A wizard beats a dense expert screen on first use and loses badly by the
  hundredth. If you score a flow once, you have scored one point on a curve.

**Do not use the score for:**

- **Novel or expressive surfaces.** A marketing page, a launch moment, an onboarding celebration.
  Optimising these for HCS makes them efficient and forgettable, which is a regression against their
  actual job.
- **One-off, high-stakes decisions.** Deleting a workspace, accepting terms, confirming a transfer.
  Here friction is the feature and a *low* HCS is the defect.
- **Browsing.** When the user's goal is to look rather than to complete, steps are the product. A
  catalogue optimised down to three clicks has removed the thing people came for.

**When the flow is one of these, say so and do not produce a ledger.** A score attached to a surface
the score does not fit is worse than no score, because it will get quoted.

Segment matters too: any HCS claim without a named user segment is unfalsifiable. "HCS 62 for a
first-time admin" is a measurement. "HCS 62" is not. See [audience.md](audience.md) for picking the
segment before you count.

## 8. Feeding `effort.py`

The ledger is a CSV. Header row required, RFC4180 quoting (the `action` column contains commas).
**Eight columns, one row per action the human took** — not one row per narrative step. A step in
which someone opens a select and picks from it is two rows, because the two actions have different
weights and land in different components.

```
step,screen,action,action_type,options,memory_items,wait_ms,notes
```

| Column | Value | Rule |
|---|---|---|
| `step` | integer | 1-based. Yours to keep in order; the script does not sort. |
| `screen` | free text | A route, a URL, or `modal`. |
| `action` | free text, quoted | What they did, in plain words. Shown in the table only. |
| `action_type` | slug | **MUST** match an `action` in `data/effort-weights.csv`. May carry a repeat count: `keystroke-char*12` charges the row twelve times. An unrecognised slug is a hard error, not a default. |
| `options` | integer | Choices at this step; `0` when it is not a choice point. Decision cost is `log2(options+1)`. |
| `memory_items` | integer | Items the human newly has to carry **out** of this step. Per row, not a running total. |
| `wait_ms` | integer or empty | Observed transition time. `0` means you timed it and it was instant. **Empty means you did not time it** — the row prints `unmeasured`, adds nothing to W, and is footnoted so the total stays honest. Never write `0` for "I did not look". |
| `notes` | free text | Put the screenshot id here so a finding can cite the row. |

`data/effort-weights.csv` is the authority for `action_type`. Run
`python3 scripts/why.py --help` for principles; run
`python3 -c "import csv;print([r['action'] for r in csv.DictReader(open('data/effort-weights.csv'))])"`
for the valid slugs. Do not invent one — `effort.py` exits 1 and lists the vocabulary, deliberately,
because a silent default produces a confident wrong score and that is worse than a failure.

**Which component a slug lands in** is decided by name, so the mapping survives edits to the weights
file: `wait-*` → W · `decision-*` → D · `memory-*` → M · `error-*`, `undo-*`, `backtrack`,
`irreversible-action`, `confirmation-dialog` → R · everything else → I.

Start from a real one rather than the table above:

```bash
python3 scripts/effort.py --example > ledger.csv
```

Sample — the worked example from §3, verbatim and scoreable:

```csv
step,screen,action,action_type,options,memory_items,wait_ms,notes
1,/dashboard,"Click ""Settings"" in the global nav",navigation-new-page,0,0,320,shot-01
2,/settings,"Click ""Members"" in a 9-tab sub-nav",tab-switch,9,0,610,shot-02
3,/settings/members,"Scroll past a 40-row table to find the button",scroll-to-find,0,0,0,shot-03
4,/settings/members,"Click ""Invite""",modal-open,0,0,0,shot-03
5,modal,"Focus the email field",field-entry-typed,0,0,0,shot-04
6,modal,"Type dana@acme.io (12 chars)",keystroke-char*12,0,0,0,shot-04
7,modal,"Open the role select and pick ""Editor""",select-from-short-list,5,1,0,shot-04 carries the role
8,modal,"Click ""Send invite""",click,0,0,2400,shot-05
9,/settings/members,"Read ""Pending""; no project access was granted",read-instruction,0,1,0,shot-06 carries the email
10,/settings/members,"Click ""Projects"" in the global nav",navigation-new-page,0,0,890,shot-07
11,/projects,"Scroll and click ""Atlas"" among 12 projects",scroll-to-find,12,0,1200,shot-08
12,/projects/atlas,"Click the ""Access"" tab (6 tabs)",tab-switch,6,0,340,shot-09
13,/projects/atlas/access,"Click ""Add member""",modal-open,0,0,0,shot-10
14,modal,"Retype dana@acme.io (12 chars)",field-entry-typed,0,0,0,shot-10 no autocomplete
15,modal,"Retype the 12 characters",keystroke-char*12,0,0,0,shot-10
16,modal,"Pick ""Can edit"" from 4 options",select-from-short-list,4,0,0,shot-10 same thing step 7 called Editor
17,modal,"Click ""Save""",click,0,0,,shot-11 not timed
```

Run it — `python3 scripts/effort.py ledger.csv`, or `cat ledger.csv | python3 scripts/effort.py -`.
The real output, trimmed to the tail:

```
                              subtotal        37.4   14.7   10.0    7.0    0.0     69.1

HCS 69 (I:37 D:15 M:10 W:7 R:0)
unmeasured  1 of 17 steps had no wait_ms and are excluded from W: steps 17.
            The Wait component is a floor, not a measurement.

read  Interaction dominates: 37 of 69, 54% of the score.
      fix class: batching and defaults — collapse the repeated steps, pre-fill what you can
      already know. Every step removed is a whole unit off the score.
```

**Weights live in `data/effort-weights.csv`, not here**, and the totals above were produced by
running the script against that file — they are not hand arithmetic. If you change a weight, rerun
the example rather than editing the number in this page. `python3 scripts/build.py --check` reports
the drift rather than letting this page quietly become wrong.

**If `effort.py` reports an action slug it cannot find**, the ledger is fine and the weights file is
missing a row — do not silently drop the action. Fix `effort-weights.csv`, or the component it
belongs to is being scored as free.

Once the ledger is built, turn it into findings via [critique.md](critique.md), and into a ranked
proposal via [brainstorm.md](brainstorm.md).
