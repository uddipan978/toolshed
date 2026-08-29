# Brainstorm — turning findings into proposals the user decides on

This is the last step of a walk. You have observed screens, counted effort, and written findings.
Now you turn those findings into a set of options and hand them over.

**The discipline: these are options, not a plan.** You are not announcing what you will build. You
are laying out what could be done, what each costs, what argues against each, and which one you
would pick — so the user can pick a different one in ten seconds. They know the roadmap, the
customer who complained last week, and the migration that lands next sprint. You do not.

**Precondition.** Every proposal traces to a finding from [critique.md](critique.md) or
[walkthrough.md](walkthrough.md), and every effort claim traces to the ledger from
[effort-ledger.md](effort-ledger.md). If you have no ledger, you cannot compute Δ HCS, so you
cannot rank. Say "no ledger — proposals are unranked" and present them unranked rather than
inventing numbers. A ranked list built on guessed numbers is worse than an unranked one, because
the ranking looks like evidence.

---

## 1. Diverge, then converge — two separate passes

**The failure this prevents:** you find a problem, the first adequate fix arrives within seconds,
and everything after that is you defending it. The first fix is almost always an addition — a
tooltip, a helper line, a confirmation step — because additions are what a mind reaches for when it
is already looking at the screen. You end up proposing more interface to fix the cost of interface.

Run two passes and do not let them touch.

**Pass one — generate. No judging.** Every response you can think of, including the ones you would
be embarrassed to send. "Delete this whole screen" belongs in pass one even when you are sure the
answer is no. Cost, feasibility, and politics are pass-two concerns; letting them in early kills
the option that would have won.

**Pass two — kill.** Apply the criteria: Δ HCS, build cost, blast radius (global / template-level /
page-level), conflicts, risk. Most options die here. That is the point — you are choosing from a
field, not defending a first draft.

### The rule of three classes

**For every finding worth fixing, generate at least three structurally different responses before
choosing one.** Different wording of the same fix is one response, not three. Force the variety by
naming the class:

| Class | What it means | Typical move |
|---|---|---|
| **remove** | Delete the step, the field, the screen, the choice | Drop the confirmation dialog; delete the optional field; infer the value instead of asking |
| **defer** | Move it later, hide it, make it optional | Collapse into a summary row; move to a second step only 12% reach; put it behind "Advanced" |
| **absorb** | Fold it into something the user already does | Set it during the action that implies it; derive it from the previous answer; make the default correct |

**Remove is listed first because it is the cheapest fix and the least considered.** A deleted field
has no copy to write, no validation to test, no responsive behaviour, no translation, and no
support ticket. It also cannot be A/B tested into existence later by someone who never read this
report — which is an argument for proposing it now, in writing.

**Failure behaviour — when a class has no viable option:** write the entry anyway and state why it
fails. "remove — cannot: the VAT number is a legal requirement in the EU checkout" is information.
A blank is not, and a blank is how a class quietly stops being considered. If you cannot say why
remove fails, you have not checked; go and check.

**The absorb trap.** Absorbing work into an existing action moves cost, it does not delete it —
that is Tesler's Law, `teslers-law`. Say where the cost went. If the answer is "onto the system",
good, that is the trade you want. If the answer is "onto support, or onto the customer's ops team",
you have not simplified anything, you have relocated the finding somewhere nobody measures it. See
`/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/00-overview-and-index.md` §5.2.

---

## 2. The two options nobody offers

Two entries are mandatory in every brainstorm, whatever the findings say.

**"Do nothing" — with its cost stated.** Not "we could leave it", but the number: what this
currently costs, per user, per month. `Do nothing — HCS 34 stays. 6 clicks × ~40 uses/user/month.`
The cost is what makes doing nothing a real choice rather than a polite gesture. Sometimes it wins:
a 12-point saving on a flow used twice a year is not worth a sprint, and saying so buys credibility
on the proposals that are.

**"Delete this feature" — with what breaks named.** Every brainstorm about a screen must contain
the option of not having the screen. Name who uses it, how often, and what they would do instead.

**A brainstorm that contains only additions is a brainstorm that has already decided.** If your
list is five proposals and all five add UI, you skipped pass one. Go back.

---

## 3. The proposal format

One block per proposal. Fixed fields, every field required.

```
P-03  Collapse the filter panel into a single summary row
  addresses    F-02 (high), F-05 (medium)
  class        defer
  principle    cognitive-load [replicated] · law-of-common-region [replicated]
  conflicts    pareto-principle — power users filter on every visit; keep one-click reopen
  effort saved Δ HCS -9 (I:-6 D:-3) × ~40 uses/user/month
  build        M · template-level · affects 6 list pages
  risk         filters become undiscoverable if the summary row is too quiet
  evidence     screenshots 03, 07
```

Field rules:

- **id** — `P-nn`, stable for the rest of the conversation. The user will say "do P-03 and P-07";
  renumbering between messages loses their decision.
- **addresses** — the finding ids with their severities. A proposal addressing no finding is you
  redesigning something nobody complained about. Delete it or write it as a finding first.
- **class** — exactly one of `remove | defer | absorb`. If it is two, it is two proposals.
- **principle** — the id from `principles.csv` with its `evidence_grade` in brackets. **Get the id
  from `python3 scripts/why.py --symptom "<what you observed>"`, never from memory** — a
  mistyped id silently cites nothing, and nobody checks. Print every grade, including the
  inconvenient ones (§7).
- **conflicts** — from `conflicts.csv`, via `python3 scripts/why.py --conflicts <id>`. Name the
  principle that argues **against** this proposal and how you are handling it.
- **effort saved** — Δ HCS with components, times frequency. `Δ HCS -9` alone hides whether you
  removed clicks or removed thinking, and those are different wins.
- **build** — `S | M | L`, plus scope from SKILL.md's vocabulary, plus what it touches. "M ·
  template-level · affects 6 list pages" is actionable; "medium effort" is not.
- **risk** — the way this proposal makes things worse if it lands badly. Every proposal has one.
- **evidence** — screenshot numbers from the walk. A proposal with no evidence line is marked
  `[UNOBSERVED]` and carries no Δ HCS, because you did not measure what it saves.

### `conflicts` is the field that keeps this honest

**A proposal with no counter-argument has not been thought about.** Nearly every UX principle has
another pointing the other way, and it is not hard to find: collapsing fights discoverability,
adding progress fights step-count, standardising fights differentiation. The tension table in
`/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/00-overview-and-index.md` §5 works
through eight of these in full.

**Failure behaviour — when `why.py --conflicts` returns nothing:** the CSV has no registered pair
for that principle. That is not permission to write `none`. Write the trade-off in your own words —
`conflicts  none registered; trade-off: two fewer fields means support cannot verify the account by
postcode` — and mark it as your inference rather than a sourced conflict. Writing `none` when you
have not looked is the single most common way a proposal ships a regression.

---

## 4. Ranking and presenting

```
priority = (Δ HCS × frequency) / build cost
```

- **Δ HCS** — the saving, as a positive number.
- **frequency** — uses per user per month, from the walk or from the user. A flow used once at
  signup and a flow used forty times a month are not comparable at the same Δ HCS.
- **build cost** — `S = 1`, `M = 3`, `L = 8`.

Then three tiers:

- **do now** — high priority, S or M build, page- or template-level scope.
- **do next** — worth doing, but blocked on a decision, a design, or an L build.
- **consider later** — real but small, or high-risk, or dependent on something not yet true.

**Failure behaviour — frequency unknown.** Do not invent it. Write `frequency unknown` and rank the
proposal provisionally at the bottom of its tier with the reason: `provisional — ranks above P-05
if this is used more than ~5×/month`. That sentence turns a guess into a question the user can
answer in four words. An invented frequency turns it into a number they will quote back at you in
a planning meeting.

**Failure behaviour — two proposals conflict with each other.** Say so on both, and say which order
resolves it. `P-03 and P-06 both touch the filter row; do P-03 first, then re-measure — P-06 may be
unnecessary after it.` Shipping both without checking is how a 9-point saving turns into a 2-point
saving and a confused screen.

### Then one recommendation

Present the ranked list, then pick **one** first move and say why. Not three. One.

```
Recommended first move: P-03.
  Why: largest saving per unit of build in the list, and it is template-level, so the six
  list pages all improve from one change. It also makes F-05 disappear without a separate fix.
  What would change my mind: if the filter panel is how power users start their day — I only
  observed it cold, on an empty account. If that is wrong, P-07 (remember last filter) goes first
  and P-03 becomes optional.
```

**The rule: you recommend, the user decides.** So make the recommendation clear enough to act on
without asking a follow-up, and make disagreeing cheap by stating what would change your mind. A
recommendation with no "what would change my mind" line puts the user in the position of arguing
with you instead of correcting you, and most people will just say yes.

---

## 5. Defects, gaps, and improvements — three separate lists

Report these as three lists, not one, because they need different responses from the user.

| List | Definition | What it needs from you | What it needs from them |
|---|---|---|---|
| **Defects** | It is broken. It does not do what it says, or it loses the user's work | Evidence: screenshot, the exact action, what happened instead | A fix, on a defect timeline |
| **Gaps** | Something a user will need that does not exist. Nothing is broken | The scenario and who hits it. Say if you did not observe anyone hitting it | A product decision |
| **Improvements** | It works. It costs more than it needs to | Δ HCS and the proposal | A prioritisation decision |

**Why the split matters:** mixed into one list, a genuine defect gets read as a nice-to-have and
triaged accordingly. "The date range resets when you paginate, so exporting month 2 silently
exports month 1" is not an improvement — it produces a wrong file with no error, and it belongs at
the top of its own list where it cannot be ranked below a spacing change.

**Defects require evidence — no exceptions.** A defect you inferred from reading the component
source is `[UNOBSERVED]` and goes in the gaps list as a question, not in the defects list as a
fact. See rule 1 in SKILL.md.

**Gaps are where you are most likely to be wrong**, because a gap is a claim about a user you did
not watch. Write the scenario concretely — "an admin adding their fourth teammate has no way to
copy permissions from an existing one" — and say whether you saw it or reasoned it. A gap stated
as an observation when it was a guess is the finding that costs the most credibility when the user
knows their customers.

---

## 6. The ethics gate

Before proposing any technique whose `ethics_axis` is `persuasive` — `scarcity`, `social-proof`,
`loss-aversion`, `goal-gradient` used as streaks, urgency, `anchoring` — do three things in the
proposal itself:

1. **Name the protective alternative.** There almost always is one, and it is usually cheaper.
2. **Say who benefits from each option.** Business, user, or both.
3. **If the honest answer is "the business, at the user's expense", write that sentence.** Then
   present both and let the user choose with the trade-off visible. Your job is not to refuse; it
   is to make sure nobody picks the extractive option by accident because it was the only one on
   the page.

The six-criterion test and the mechanism→dark-pattern decay table are in
`/Users/shankhajeettaran/workspace/learning/research/behavioral-design/04-unified-behavioral-design-synthesis.md`
§5. Two criteria decide most cases: **truth at render time** (is the number live-sourced, and does
the component render honestly when the true value is unimpressive?) and **disclosure survival**
(would it still work if a caption on the same screen explained the mechanism?). A technique that
stops working once explained was running on deception.

### What each of these decays into — learn the names

| Technique | Its dark pattern | The tell |
|---|---|---|
| `scarcity` / urgency | **false urgency** | The timer survives a page reload |
| `social-proof` | fabricated counts, fake activity toasts | No data source; it renders when there is nothing to render |
| `loss-aversion` / streaks | streak-loss anxiety, then **forced continuity** — the loss is manufactured, and relief from it is sold or bundled | The user did not choose the constraint; cancelling means losing something the product invented |
| framing of a decline option | **confirmshaming** | The "no thanks" is written to make the user feel stupid |
| ability, inverted | **roach motel** | The exit path has more steps than the entry path |

The last one has a one-afternoon audit attached and it is the highest-value ethics work available:
**count the clicks, fields, and screens on the entry path and the exit path of every consequential
flow, and put the two numbers side by side.** Equal effort is choice architecture. Wildly
asymmetric effort is sludge, and the ratio is the evidence. You already have the entry number from
your ledger.

### Three worked examples

**Example A — social proof on an empty dashboard.**
Proposal considered: "3,412 teams connected a data source this week" on the empty state.
Protective alternative: show the three source types this account's plan supports, with the
one-click setup for each.
Who benefits: the persuasive version benefits the business (activation rate). The protective
version benefits the user (they learn what is available) and the business slightly less.
**Verdict: conditional pass.** Passes if the count is queried live and the component renders
nothing when the true count is small — that is the truth criterion enforced in code, not in review.
Fails the moment it becomes a constant in a template. Recommend the protective version anyway: it
answers the question the empty state actually raises, which social proof does not.

**Example B — a streak on a weekly reporting habit.**
Proposal considered: a streak counter for consecutive weeks the manager filed their report, plus a
"don't break your streak" reminder on day 6.
Protective alternative: show whether this week's report is filed, and let them set the reminder
themselves.
Who benefits: the streak benefits the business (a compliance metric it can report). The user gets
anxiety attached to an obligation they already had.
**Verdict: fail on reflective endorsement.** A streak turns a work task into a personal loss, and
the users most affected are the ones already under time pressure — the deficit-exploitation
criterion, which is the one that changes decisions. The manufactured loss is `loss-aversion`
[replicated] pointed at the user, and it decays into forced continuity the first time someone
proposes selling a "streak freeze". Propose the protective version and say plainly that the streak
would probably raise the compliance number.

**Example C — "2 seats left at this price" on the upgrade page.**
Protective alternative: state the real price-change date and what the new price will be.
Who benefits: the business, at the user's expense. Say exactly that.
**Verdict: fail unless the constraint is real.** Queried from live inventory, it passes truth and
disclosure and is a legitimate nudge. Decorative, it is false urgency and actionable under EU/UK/US
consumer-protection regimes — not a design question at all. Note the asymmetry: nothing in the
interface distinguishes the two cases. The ethics live entirely in whether the claim is true.

---

## 7. Evidence honesty

**Every proposal that cites a principle prints that principle's `evidence_grade`.** No exceptions,
including when the grade weakens your case — especially then.

A `contested` or `null-result` principle **may** motivate a proposal. It **may not** be presented
as established fact, and the proposal must stand on the observed effort cost rather than on the
citation. If removing the citation collapses the proposal, the proposal was the citation wearing a
UI change as a costume.

**Wrong:**

```
P-11  Show a partially-filled progress bar on the setup wizard
  principle    zeigarnik-effect — people remember and return to unfinished tasks
```

That states a `null-result` claim as fact. The recall effect it leans on did not replicate.

**Right:**

```
P-11  Pre-fill step 1 from the signup data and show 1-of-4 complete
  addresses    F-09 (medium)
  class        absorb
  principle    endowed-progress [replicated] · zeigarnik-effect [null-result — the recall
               claim did not replicate; this proposal does not rest on it]
  conflicts    parkinsons-law — do not add steps to make progress look better; the step count
               stays at 4
  effort saved Δ HCS -4 (I:-3 D:-1) × 1 use/user (signup only) — small, but signup is the
               observed drop-off point
  build        S · page-level · signup wizard only
  risk         a pre-filled field the user does not notice is a field they do not check
  evidence     screenshot 11
```

The proposal survives on the three keystrokes it removes and on where the drop-off was observed.
The weak citation is present, graded, and explicitly load-free.

**Failure behaviour — the grade is `my-inference`.** Say so in the same words the CSV uses, and add
the observation it rests on. `my-inference` is legitimate; passing it off as literature is not.

---

## 8. How this lands in the response

Four parts, in this order. Nothing else.

```
<one line: what you walked, what it costs today>

DEFECTS (n)
  D-01  <one line>   evidence: screenshot 04
  ...
  — or: none observed

GAPS (n)
  G-01  <one line>   observed | inferred
  ...

DO NOW
  P-03  Collapse the filter panel into a single summary row   Δ HCS -9 · M · template-level
  P-07  Remember the last filter set                          Δ HCS -5 · S · page-level

DO NEXT
  P-01  Merge steps 2 and 3 of the export flow                Δ HCS -12 · L · template-level

CONSIDER LATER
  P-09  Inline the invoice preview                            Δ HCS -3 · M · page-level

  Do nothing — HCS 34 stays, ~40 uses/user/month
  Delete the export builder — 3 of 21 pages link to it; the CSV endpoint covers the observed use

Recommended first move: P-03.
  Why: <two lines>
  What would change my mind: <one line>

Full proposal blocks below / attached. Tell me which to expand, or point me somewhere else —
you know the constraints I cannot see.
```

Rules for this block:

- **The one-line summary is the only thing some readers will read.** Put the cost in it.
- **Full proposal blocks come after the summary, not instead of it.** Ten `P-nn` blocks up front is
  a wall; ten one-liners with blocks below is a decision.
- **Keep both mandatory options visible in the tier list**, at the bottom, where they read as
  choices rather than as a disclaimer.
- **End with the invitation to redirect, and mean it.** The user has constraints you did not see —
  a rewrite already scheduled, a customer contract that requires the field you want to delete, an
  engineer who owns that template and is on leave. If they redirect you, that is the process
  working, not a rejection.

**Then stop.** One brainstorm per walk. Re-deriving proposals because the first set was not
accepted spends the user's money to re-litigate a decision they already made. If they pick three
and ask for detail, give detail on those three — that is the one follow-up round SKILL.md allows.
