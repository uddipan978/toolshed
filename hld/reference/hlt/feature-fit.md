# feature-fit.md — does this feature still fit the flow?

The `fit` command. A feature was added, changed, or proposed. Your job is not to make it work — the
engineer already did that. Your job is to answer whether the surface it lands on is still coherent
with it there, and to say so in a form someone can act on before the code ships.

**Precondition.** `fit` requires an observed surface. If you have not walked the screen this feature
lands on in this session, walk it first — see [walkthrough.md](walkthrough.md). Reading the
component source tells you what renders; it does not tell you what the page feels like with eleven
other things already on it. If the app will not run, stop and say the fit check is blocked. Do not
substitute a code read and report a verdict; a verdict from source is a guess wearing a table.

**Every principle id in this file is a lookup, not a claim.** Run
`python3 ../scripts/why.py --name <id>` to get the claim, its evidence grade, and its conflicts. If
`why.py` returns nothing for an id used here, the id has drifted — fix the citation and say so.
Never restate a principle from memory when the row is one command away.

---

## 1. The first question is whether to build it at all

Placement, frequency, and hierarchy are all downstream of a question most reviews skip: should this
exist? Answer it first, because every answer after it inherits the assumption.

Four questions, in this order. Each has an answer that is evidence and an answer that is a feeling.

| Question | Evidence answer | Feeling answer (reject) |
|---|---|---|
| Who asked? | Named accounts, named roles, support threads, a workaround you watched during the walk | "Users have been asking for this" |
| How often will it be used? | A rate per user per period, with the population it applies to | "Often" · "It's important" |
| What do they do today instead? | The literal current path, in steps you counted | "Nothing" · "There's no way to do it" |
| What happens if it does not exist? | The cost of the workaround × the people who pay it | "We'd be behind" |

The person who requested a feature is frequently not the person who will use it. Record both. A
request from an executive who will never open the screen is a request, not a usage signal, and
treating it as one is how a monthly task lands in daily real estate.

**The arithmetic that decides most of these.** Prime navigation is paid for by every user on every
visit. A feature used monthly by 3% of users, given a top-level nav slot, charges 100% of users a
permanent scanning cost on every page load to serve 3% of them twelve times a year. That is a net
loss even when the feature is flawless — the feature is fine, the placement is a tax. Juran's
correction to the Pareto principle is the honest framing: the tail is the *useful* many, not the
trivial many, so the answer is rarely "delete it" — it is "do not charge everyone for it."
See id `pareto-principle`, and
`/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/05-decision-making-and-simplicity.md`
for why the 80/20 ratio itself is numerology and only the skew is real.

### The four honest outcomes

**Build it.** Evidence required: more than one independent requester; a frequency you can state as a
rate; an observed workaround with a counted cost; and no existing surface that can absorb it without
distorting that surface's purpose.

**Build a smaller version.** Evidence required: the request contains one action that covers most of
the demand and several that cover the rest speculatively. Name the one. Ship it. The remainder is
not cancelled, it is unproven — say that, so nobody reads "smaller" as "rejected."

**Absorb it into an existing surface.** Evidence required: a screen already holds the object this
acts on, and adding it there costs at most one element and no new decision point. This is the most
common correct answer and the least often proposed, because absorbing looks like less work than it
is credited for.

**Decline it, and say why.** Evidence required: any one of — no second requester; an existing path
already achieves it within about two extra steps; or the cost lands on every user while the benefit
lands on a minority who already have a workaround they do not complain about.

Declining is the outcome agents never offer, and it is frequently correct. Offer it explicitly, with
the reason and with what you would do instead. A decline with no alternative is an obstruction; a
decline that names the underlying complaint and fixes it cheaply is the highest-value output this
command produces.

**Failure behaviour.** If you cannot answer "how often" with anything but a guess, write
`frequency: unknown` and place the feature as if it were monthly — the conservative slot. Do not
place an unknown-frequency feature as if it were daily. An over-hidden feature is a discoverability
bug someone reports; an over-promoted one is a permanent cost nobody reports because nobody
attributes their fatigue to it.

---

## 2. Frequency-driven placement

Prime real estate belongs to frequency, not to importance as argued by whoever requested it.
"Important" is not a placement input — every requester believes their feature is important, and the
belief is uncorrelated with how often anyone opens it. Frequency is measurable and arguable against.

| Use rate | Where it goes | Icon | Label | May be a default |
|---|---|---|---|---|
| **Daily** | Primary nav, or a persistent action on the screen that owns the object | Yes | Yes | Yes |
| **Weekly** | Secondary nav, or the primary action on its own page | Optional | Yes | Yes, if reversible |
| **Monthly** | A page action next to the object it acts on | No | Yes | No |
| **Quarterly** | Overflow menu on the owning screen, or Settings | No | Yes | No |
| **Once ever** | Contextual first-run surface, or Settings | No | Yes | Never |
| **Never by most** (<5%) | Command palette and docs. No menu entry. | No | n/a | No |

Rules the table encodes, each with its reason:

- **Icon without label is a recognition test.** It only pays once the item is used often enough to
  be learned, which is the daily row and nowhere else. Below daily, an icon-only control is a
  guessing game the user loses silently — they do not ask, they just do not use it. See
  `jakobs-law`: an icon transfers meaning only when it is the icon every other product uses for
  that thing.
- **A once-ever action is never a default.** A default is a decision made on the user's behalf, and
  a decision that can only be made once is the one you have no right to make for them. See
  `choice-architecture` for the defaults literature and the line between a nudge and a
  substitution.
- **"Never by most" still means someone.** Docs-only is a real placement, not a deletion — but only
  if the command palette entry exists, because the docs will not be read. See
  `paradox-of-the-active-user`.
- **Adding a nav item is not free to the items already there.** Each addition raises the choice cost
  of the whole set (`hicks-law`) and pushes items past the point where the middle of a list is
  reliably scanned (`serial-position-effect`). A nav that grew to nine entries did not get one
  feature worse; it got measurably slower for everything in it.

### The rare-but-critical exception

Some actions are used once ever and must still be findable in under thirty seconds: cancel
subscription, export my data, delete account, revoke a session, change the billing email, contact a
human. Frequency does not govern these. Two rules:

1. **Put them where every other product puts them** — account or billing settings, at the bottom of
   the page they belong to, with the conventional word ("Cancel subscription", not "Manage plan
   options"). Convention is the entire discoverability mechanism here; the user has done this
   somewhere else and is looking for what they saw there (`jakobs-law`).
2. **Hiding them is a dark pattern, not a placement choice.** Burying cancellation behind a support
   chat, an unlabelled overflow, or four confirmation screens is obstruction. If the fit check finds
   this, it is a `blocker` finding regardless of who asked for it, and you say so plainly rather
   than framing it as a hierarchy question.

The distinction that keeps this honest: rare-and-critical is defined by **consequence to the user if
they cannot find it**, not by consequence to the business if they do. Anything on the second list
is a retention tactic and gets no protection from this rule.

---

## 3. Supplementing or hiding a rare feature

You have decided a feature is real and infrequent. These are the options, ranked cheapest to
costliest for the people who do not use it.

**1. Contextual surfacing — appears only when it is relevant.**
Right when relevance is computable from state: bulk actions on row selection, "Restore" on a
trashed item, "Split payment" when the total exceeds a threshold. Costs nothing to the 97% because
they never see it. Discovery: it appears at the moment of need, attached to the thing it acts on.
This is the best option and is under-used because it needs a real relevance condition — if you
cannot state that condition in one sentence, you do not have one, and you are actually reaching for
option 2.

**2. Progressive disclosure — behind one obvious affordance.**
Right for a coherent group of advanced options: an "Advanced" section, a "More filters" toggle, a
disclosure on a form. Costs one element in the collapsed state and one click to the user who wants
it. Discovery: the affordance must name what is inside it. "Advanced" names nothing; "Advanced
(retries, timeouts, headers)" names three things and is found. Failure behaviour: if the collapsed
section holds one control, do not collapse it — you added a click and an element to hide an element.

**3. Command palette or search entry.**
Right for expert-frequency actions in a product that already has a palette. Costs nothing visually
and nothing to non-users. Discovery: only for people who already know the palette exists and can
guess the verb, so register several aliases and never make this the *only* path for something a
novice needs.

**4. Overflow menu on the owning screen.**
Right for quarterly actions that belong to a specific object. Costs one icon on the screen and two
clicks. Discovery: acceptable — users do open overflow menus when stuck — but only if the menu sits
next to the object, not in the page header three sections away from it.

**5. Settings page.**
Right for configuration that persists, and for once-ever account actions. Costs a navigation away
from the task and a search within a page that is usually long. Discovery: poor unless the setting is
in the section a person would guess, and it usually is not. If you place something in Settings, name
the section you placed it in and check that a plausible alternative guess also leads there.

**6. Delete it.**
Right when the fit check finds no requester, no usage, and no workaround being replaced. Costs the
removal sweep (§7). Say this out loud when it is the answer; a feature kept because removing it
requires a decision is how a surface accumulates.

### The discovery rule

**A feature reachable only by a path nobody would guess is deleted, whether or not the code still
exists.** State the path in one sentence. If that sentence contains "then they scroll to the bottom
and", "if they know to", or "it's in the changelog", the feature is not shipped, it is stored.

The test to run during the walk: land on the screen as someone who wants the outcome but has never
seen this build, and try to reach the feature in two attempts without using search. If both attempts
fail, record it as a finding with the two paths you actually tried — the wrong guesses are the
evidence, and they usually name the correct placement for you.

Failure behaviour when you cannot test discovery because you already know where it is: say so, mark
the finding `[UNOBSERVED]`, and ask for one person who has not seen it. Do not simulate innocence
and report the result as observation.

---

## 4. Does the flow still hold?

**Walk the entire flow again, not just the new step.** The insertion point is rarely where the
damage lands. A field added to step 2 breaks step 4, where the summary now lists an item the user
does not remember entering; a button added to the header pushes the submit control below the fold on
a laptop. You cannot find either by looking at the diff.

Re-walk from the flow's real starting point — where the user actually enters, which is often a
deep link or an email, not the index page — through to the state where they would consider
themselves done, including the confirmation and any email or notification the flow emits.

The checklist. Each item names what to look for and what it breaks.

- **Does the new step interrupt an established rhythm?** Three screens of "pick one, continue" then
  a screen that wants four fields is a rhythm break, and users stall at it out of proportion to its
  actual work. See `flow` — the design contribution is negative and preparatory: do not force a mode
  switch mid-task.
- **Does it demand information not yet knowable?** A field the user can only fill after a step that
  comes later is the single most common defect a fit check catches. The symptom in the walkthrough
  is a backtrack; log it in the effort ledger as one, and check whether the step can simply move.
- **Does it push a previously above-fold action below?** Check at the smallest desktop height you
  support, not at your own window. Then check tablet and phone —
  [responsive.md](responsive.md) has the widths and the reflow rules.
- **Does it change the meaning of a neighbouring control?** "Save" next to a new "Publish" no longer
  means what it meant yesterday, and nobody re-reads a label they have already learned. This is
  negative transfer (`jakobs-law`): an almost-familiar control is worse than an unfamiliar one,
  because the resemblance activates the wrong expectation.
- **Does it add a decision at a point where the user had momentum?** Effort rises as the perceived
  finish line nears (`goal-gradient`), and a decision inserted late spends motivation that was about
  to carry the user over the line. If a decision must be added, add it early where the drop-off is
  already priced in, not at step 4 of 5.
- **Does it change a step counter's denominator?** "Step 2 of 4" becoming "Step 2 of 5" mid-flow
  inverts the progress effect into betrayal. Either the denominator is fixed before the flow starts
  or there is no counter.
- **Does it break a mental model the user brought with them?** Ask which five products your users
  live inside and whether this behaves like those. `jakobs-law` is only actionable once you name that
  reference set; without one it is a slogan. The reasoning is in
  `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/02-interaction-and-system-response.md`.

Every item you answer "yes" to becomes a finding in the standard format (severity, scope, axis,
screen, observed, action, cost, principle, problem, proposal, build) — see
[critique.md](critique.md) for the format and the severity vocabulary.

---

## 5. Hierarchy and load delta

The question is not "is the cognitive load acceptable" — that is unanswerable and everyone answers
it yes about their own screen. The question is **how much did it change**. Deltas are checkable;
absolutes are opinion.

Count three things before and after, on the same screen at the same width:

1. **Elements on screen** — every distinct thing a user could look at or act on above the fold.
   Count groups as one only if they are visually a group (a card, a fieldset, a segmented control).
2. **Decision points** — every place the user must choose. Weight each by `log2(options+1)`, which is
   the Decision component of the Human Cost Score; the method is in
   [effort-ledger.md](effort-ledger.md), the weights are in `../data/effort-weights.csv`.
3. **Competing calls to action** — controls styled or placed as primary.

Report the delta alongside the Human Cost Score for the task, both before and after:

```
load    elements 19 → 23 · decisions 4 → 6 (D 6.9 → 9.4) · primary CTAs 1 → 2
hcs     before 22 (I:12 D:4 M:3 W:2 R:1) → after 27 (I:14 D:6 M:4 W:2 R:1)
```

**The rule that matters: adding a primary action does not create a second primary — it demotes the
first.** A page has one primary action because "primary" is a relative claim, and two things claiming
it means the page now has none. Decide explicitly which one loses and restyle it, in the same change.
The failure behaviour if you cannot decide: the new action is not primary. Default to demoting the
newcomer, because the existing primary has evidence behind it and the newcomer has a request.

The same logic applies to any distinctiveness device — a badge, an accent colour, an animation. Each
one works by being the exception (`von-restorff`); the second one halves the first, and the fourth
one means the page has a colourful area rather than an emphasis. The visual mechanics — what
demotion looks like, which token to move to, how much spacing separates a group from its neighbour —
are in [hierarchy.md](hierarchy.md). Do not re-derive them here.

**Memory is the component that silently rises.** If the new feature requires the user to carry a
value from screen A to screen B — a code, a name they chose, an ID — the Memory component goes up
and the ceiling is about four items (`working-memory`). Carry-over is almost always removable by
displaying the value where it is needed instead of asking the user to hold it.

---

## 6. Scope classification

State the scope before proposing the change, using exactly the SKILL.md vocabulary:
`global` · `template-level` · `page-level`.

| Scope | What it touches | Who must review | Regression surface | The question to ask first |
|---|---|---|---|---|
| **global** | Nav, shell, tokens, auth, layout primitives | Design owner and one engineer per consuming app | Every screen, including ones nobody has opened in months | "Which screens render this, and have I opened three of them?" |
| **template-level** | A layout, list, detail or form shell shared by many pages | Whoever owns the template plus one owner of a consuming page | Every page using the template, at every width | "Who are the consumers, by name, and does this hold for all of them?" |
| **page-level** | This screen only | The page owner | This screen, plus deep links into it | "Is this genuinely one screen, or is this screen an instance of a template?" |

**The trap.** A change is requested for one page, implemented in the shared template because that is
where the markup lives, and silently changes eleven other screens. Nobody notices in review because
the diff touches one file and the request named one page. It surfaces weeks later as unrelated bug
reports on screens the author never opened.

**The check that catches it: enumerate the consumers before you propose the change, not after.**

```
rg -l "InvoiceListLayout" --type ts --type tsx      # who imports the template
rg -n "<InvoiceListLayout" -g '!*.test.*'           # where it is actually rendered
```

Then open three of them and look. If the enumeration returns more than one consumer, the change is
`template-level` no matter how the request was phrased, and the proposal must say either "this holds
for all N consumers" or "this needs a per-page variant." Naming the count is what makes the claim
reviewable — "it's shared" is not, "it has 11 consumers and I checked 3" is.

Failure behaviour when the consumers cannot be enumerated because rendering is dynamic (registry,
config-driven, slot-based): say the enumeration is incomplete, name the registry, and downgrade the
proposal to a question for the owner. Do not assume a single consumer because grep found one.

---

## 7. The removal side

Removing a feature is a change, and it gets the same fit check: scope, load delta, re-walk. Two
things are specific to removal.

**The dead-reference sweep is mandatory afterwards.** Not optional, not "if time" — a removal
without a sweep leaves links to a 404, menu entries that do nothing, and tests asserting a route
that no longer exists. Run it as its own pass: [dead-references.md](dead-references.md).

**The human side is not covered by the sweep.** Three questions:

1. **Who relied on it?** Someone's Monday morning was built on this. Name them if you can, and state
   what their new path is. "They can do it another way" is only an answer if you have walked that
   way and counted it.
2. **Where did the capability go?** Removed entirely, folded into something else, or replaced by a
   different mechanism? Each needs a different message, and the one that goes wrong is "folded into
   something else" without telling anyone — the capability exists and every previous user believes
   it was deleted.
3. **What still advertises it?** Enumerate, and check each: empty-state copy, onboarding checklists,
   tooltips, the keyboard shortcut map, saved views or filters referencing it, notification and email
   templates, help articles, the marketing page, and any deep link a user may have bookmarked. A
   bookmarked deep link that now 404s is the removal defect users report most and teams find last.

The deleted thing that is hardest to see is the one that still works: a route left routable but
unlinked. It passes every test, serves stale behaviour to whoever bookmarked it, and nobody
maintains it. Either link it or remove the route.

---

## 8. The verdict format

One block per feature. Same shape as the finding format so both can sit in one report.

```
FIT  <feature name>
  verdict    build | smaller | absorb | decline
  asked-by   <who requested> · <who will use, if different>
  frequency  <rate> · <population> | unknown
  today      <the literal current path, in counted steps>
  placement  <where it goes> — <the frequency row that justifies it>
  scope      global | template-level | page-level · <what else it touches, enumerated>
  load       elements A → B · decisions A → B · primary CTAs A → B
  hcs        before <N (I: D: M: W: R:)> → after <N (…)>
  principle  <id> [<grade>] · <id> [<grade>] · conflicts: <id>
  also       <what else must change: copy, empty state, docs, shortcuts, tests>
  re-walk    <the flows to walk again, by path>
```

### Example A — accepted with modifications

```
FIT  compare invoices
  verdict    smaller
  asked-by   finance leads at 2 accounts · used by the same 2 roles, not by AP clerks
  frequency  weekly · ~15% of users on /invoices
  today      they open two invoices in two browser tabs and alt-tab between them
  placement  selection toolbar that appears when 2 rows are checked — NOT primary nav.
             Weekly row: secondary placement, labelled, no icon. Contextual surfacing
             (§3 option 1) because the relevance condition is exact: 2+ rows selected.
  scope      template-level · InvoiceListLayout has 4 consumers (/invoices, /credit-notes,
             /drafts, /archive). Checked 3. Selection toolbar already exists in all 4, so
             this adds a button to an existing container rather than a new container.
  load       elements 21 → 21 (toolbar already renders on selection) · decisions 3 → 3 ·
             primary CTAs 1 → 1
  hcs        before 19 (I:11 D:3 M:3 W:1 R:1) → after 19 · new compare path 8
             (I:5 D:1 M:0 W:1 R:1), replacing an 11-step two-tab workaround
  principle  pareto-principle [heuristic] · flow [heuristic] — removes the mode switch out
             of the app · conflicts: von-restorff, if the toolbar gains a third accent
  also       empty selection state needs no change; keyboard map gains one entry; the
             "compare" verb must be registered in the command palette for the 2 accounts
             who will look for it there
  re-walk    /invoices → select 2 → compare → back; /credit-notes selection toolbar at
             1280px and 768px, where the toolbar already wraps
```

What was modified: the request was a "Compare" entry in primary nav. Declined at that placement —
weekly use by 15% does not buy a slot every user pays for on every page, and a nav Compare would
need its own picker screen (two more decisions) to select what the selection toolbar already knows.

### Example B — declined

```
FIT  per-user custom column ordering on the invoice table
  verdict    decline
  asked-by   1 named user, once, in a call · no support threads, no second requester
  frequency  unknown — no observed use of the existing column-visibility menu either
  today      they use the filter bar, then read the row. Observed cost: 0 extra steps.
             The stated complaint was "the Amount column is too far right", not "I want
             to order columns"
  placement  n/a
  scope      would be template-level · TableShell has 11 consumers, plus per-user
             persistence, which is a new storage surface and a new migration
  load       elements 24 → 26 (drag handles + a reset control) on every table in the
             product, for every user, permanently
  hcs        unchanged for the task; +2 elements of scanning cost on 11 screens
  principle  pareto-principle [heuristic] — cost on all, benefit to one ·
             paradox-of-the-active-user [heuristic] — a feature needing a drag gesture
             nobody will discover is a feature nobody will use
  also       instead: move Amount to column 3 in the default order. One line, one
             template, ships today, and addresses the complaint that was actually made.
  re-walk    /invoices after the default reorder, plus 2 other TableShell consumers to
             confirm the default did not displace something they rely on
```

The decline is doing real work here: the feature was a solution the requester proposed, and the
complaint underneath it was one default away from fixed. Say both parts. A decline that reports only
the first half reads as obstruction and gets overridden in the next meeting.

**Failure behaviour for the whole command.** If you cannot fill `today` — the literal current path —
you have not observed enough to issue a verdict. Go back and walk it, or issue the block with
`[UNOBSERVED]` on the lines you guessed and no verdict at all. A fit verdict built on an imagined
current state is the most expensive kind of wrong, because it is confident, specific, and gets built.
