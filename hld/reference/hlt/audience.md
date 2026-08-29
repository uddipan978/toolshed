# Audience — who is on this screen, and how long do they sit on it

Read this before you score anything. Every other judgement in this skill — what to hide, what to
collapse, how dense is too dense, whether six clicks is fine or fatal — is a function of two
variables you have to fix first: **who** is here, and **how long** they stay.

## 1. Why this comes first

The same screen is correct for one audience and wrong for another. Not "better or worse" —
correct or wrong.

A trading terminal with 40 numbers per viewport, no icons, no whitespace, and keyboard-only
ordering is excellent design for someone who sits in it seven hours a day and terrible design for
someone opening it once. A guided three-step wizard with illustrations and a confirmation dialog is
excellent for the first-timer and an insult to the professional, who now pays 3 extra screens ×
200 times a week.

**The failure.** Score a screen without fixing the audience and you produce advice that is
confident, specific, well-cited, and wrong. You will tell a team to add breathing room to a
live-in surface — costing their analysts a scroll on every row — and cite `law-of-proximity` while
doing it. The citation makes it worse, not better: it launders an unstated assumption as a finding.
This is the most expensive mistake available in this skill, because unlike a missed defect it
actively destroys working software.

**If you cannot determine the audience.** Do not guess silently and do not stall. Write the
audience statement (§8) with the unknown field marked `ASSUMED`, name the signal you inferred it
from, and cap every finding that depends on that assumption at severity `medium`. Say in the
finding which way the recommendation flips if the assumption is wrong. A capped, labelled finding
is useful. An uncapped guess is a liability.

## 2. Reading technical vs non-technical from the surface

You usually cannot ask. Infer from what is on screen — and write down what you inferred from, so
the user can correct it in one line instead of re-litigating the whole report.

| Signal on screen | Reads as | Why it is evidence |
|---|---|---|
| Raw IDs exposed (`usr_8f3a…`, UUIDs in a column) | Technical | Nobody surfaces an opaque key unless someone pastes it somewhere |
| JSON / YAML / regex / cron / SQL input | Technical | These have no forgiving version; shipping one asserts the user can debug it |
| API keys, webhooks, tokens visible | Technical | Implies the user owns an integration |
| Log / event / trace views, stack traces in errors | Technical | Only useful to someone who can act on them |
| Jargon in labels ("idempotency key", "upstream", "TTL") | Technical | Labels are written for whoever must read them |
| Keyboard-first affordances: `⌘K`, shortcut hints, `j/k` | Technical + frequent | Shortcuts only pay back with repetition |
| Destructive action with no confirm, undo instead | Technical | Team decided speed beats safety — a bet only expert users win |
| Dense tables, no row illustration, small type | Technical + live-in | Density is throughput optimisation |
| Guided steps / wizard / numbered progress | Non-technical | Serialising choice is a novice accommodation |
| Plain-language labels ("Who's paying?" not "Payer entity") | Non-technical | Written to be understood cold |
| Heavy empty-state coaching, sample data, "Start here" | Non-technical | Assumes no installed model to fall back on |
| Confirmation dialogs on ordinary actions | Non-technical | Team expects mistakes and cannot afford them |
| Illustrations, mascots, generous whitespace | Non-technical | Attention is being bought, not assumed |
| IDs hidden, human names everywhere | Non-technical | Someone paid to map keys to labels |
| Tooltips explaining fields rather than edge cases | Non-technical | Field names are not self-evident to this reader |

Three or more signals on one side is a read. One or two is a hint — record it as `ASSUMED`.

**When signals conflict** — and on real products they usually do, because the same screen serves an
admin and a first-week hire:

> **Design for the less expert user on anything destructive or rare. Design for the expert on
> anything done daily.**

The reason is asymmetric cost. A confirmation step on a daily action costs the expert a click ×
1,000 a year — real, but recoverable. No confirmation on a rare destructive action costs the
novice their data once — unrecoverable. Frequency decides who you optimise for; consequence decides
who you protect.

**Failure behaviour:** if an action is both daily *and* destructive (bulk-archiving a queue, say),
you do not get to average them. Give the expert the fast path and make the mistake cheap — undo
with a visible window, not a dialog. That is the only resolution that serves both, and it is more
work than either.

## 3. The expertise gradient

Four states, not two. Treating this as novice-vs-expert is what produces interfaces that are
correct for 20% of sessions.

| State | Who | Needs | Finds insulting |
|---|---|---|---|
| **First-run** | Never seen it. No model of this product, a strong model from adjacent ones | Defaults that produce a working result; the first action visible in the empty state; recoverable errors | Being made to configure before doing anything |
| **Occasional** | Weeks between uses. Has done this before, remembers nothing about how | Recognition over recall — visible labels, the last-used values, a path they can re-derive from the screen | Being onboarded again from zero; a "welcome back" tour |
| **Daily** | Runs the same 3–5 tasks, at speed | Shortest path, stable positions, no layout drift, no confirmations on routine actions | Coaching, tooltips they've dismissed 40 times, animation on every transition |
| **Power** | Bends the tool. Bulk operations, keyboard, custom views | Keyboard access to everything, multi-select, saved filters, an escape hatch (API, export, raw edit) | Capability removed "for simplicity"; being capped at what the daily user needs |

**The occasional user is the hardest and the most commonly forgotten.** They are not a novice —
they know the feature exists and will be annoyed at being taught it again. They are not an expert —
they cannot recall where it lives or what the fields meant. They need the interface to be
*re-derivable from what is on screen*, which is a stricter constraint than either neighbour.

The tell that a product forgot them: it has a great first-run and a great power path, and the
quarterly task takes eleven minutes because the user is searching for a control they used before.
When you walk a surface, ask explicitly — *what does the person who did this last in March see?*

**Paradox of the Active User** (id `paradox-of-the-active-user`). People start acting immediately
and do not read the documentation, even when reading would save them time — the behaviour is
locally rational and globally irrational, and pointing it out does not change it. Consequence for
your findings: guidance must live *inside* the interface, attached to the control it explains, on
whatever path the user chose — not in a wall of text or a five-slide tour before it. A front-loaded
onboarding carousel is skipped, and its completion metric is read by the team as comprehension.
The mechanism, the misuses, and the one domain where this principle does *not* hold (high-
consequence expert systems — clinical, aviation, tax, compliance — where users genuinely do train
and read):
`/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/05-decision-making-and-simplicity.md`

**Failure behaviour:** if you find yourself proposing "add a tooltip explaining this", check
whether the control could instead be self-explanatory. A tooltip is guidance that survives the
paradox only when it is attached to the point of use *and* the user can act without reading it.

## 4. Dwell time

How long one person stays on this surface in one sitting. It sets density, contrast, motion, and
how much chrome you can charge them.

| Band | Duration | Examples |
|---|---|---|
| **Glance** | under 10s | Notification, status badge, widget, toast, header alert |
| **Task** | 10s – 2min | Form, search, checkout, single record edit |
| **Session** | 2 – 30min | Dashboard, editor, review queue, report builder |
| **Live-in** | hours, daily | The tool someone's job runs on — CRM, IDE, ticket queue, terminal |

| | Glance | Task | Session | Live-in |
|---|---|---|---|---|
| **Density** | Lowest — one message | Low — one decision per view | Medium | **Highest** |
| **Contrast** | High, deliberately loud | Medium-high on the primary action | Medium | **Low-medium, sustained** |
| **Motion** | Allowed, one beat, to catch the eye | Only as state feedback | Only as state feedback | **Effectively none** |
| **Saturation** | Full — colour is the message | Accent on the primary path only | Reserved for status | **Reserved for status only, minimum area** |
| **Font size** | Large, readable at arm's length | Comfortable body | Body | **Small but never below legibility floor** |
| **Chrome tolerated** | High (it *is* the chrome) | Medium — a header and a progress cue | Low | **Near zero** |

**The rule that surprises people:**

> A live-in surface should be **quieter and denser** than a glance surface, not louder.

Two independent reasons, and both are physical, not aesthetic. Sustained high contrast and
saturation fatigue: the eye adapts, the signal stops signalling, and the person ends the day tired
in a way they will describe as "the app is exhausting" without being able to point at a control.
And every pixel of chrome is paid for a thousand times a day — a 56px header that costs a glance
surface nothing costs a live-in surface one scroll per screen, on every screen, forever.

**The negative case.** The most common defect in enterprise UI is a live-in screen styled like a
marketing page: 80px of hero padding, an animated skeleton loader on every filter change, a
saturated brand-colour banner pinned to the top, and four rows visible. The person using it eight
hours a day has already stopped seeing the banner and is scrolling around it. Report that as an
effort finding with the scroll count, not as a taste finding.

**The opposite error** is real too: a glance surface made quiet and dense. A status widget nobody
notices has failed at its only job. Loud is correct there.

**Failure behaviour:** if you cannot tell the band from the walkthrough, look at what the screen is
*for* — a surface with no persistence (no saved filters, no draft state, no returning position)
was not built for a session or live-in user, whatever its density suggests. Record the band as
`ASSUMED` and cap dependent findings per §1.

## 5. Voluntary vs involuntary users

Consumer software users can leave. Enterprise software users cannot. The person in your admin
console did not choose it, cannot switch, and will still be there next quarter regardless of what
you do to them.

**What this forbids.** Motivation levers aimed at making someone *want* to act are inappropriate
here, and often insulting:

- `social-proof` — "12 other admins completed this step" on a mandatory task reads as surveillance,
  not encouragement. It is also non-diagnostic: it carries no information the user could act on.
- `scarcity` — manufactured urgency on work someone is required to do is a lie about the state of
  the world told to compress a colleague's decision time.
- `gamification` — badges and leaderboards on required work. Leaderboards reliably motivate the top
  decile and demotivate the bottom half; on a task nobody chose, that is the whole population you
  are demotivating to move a number.

**What works instead: ability levers, only.** BJ Fogg's decomposition is the useful frame — a
behaviour is easy when it demands little of the resource the person has *least of at that moment*,
and it is a **min**, not an average. Run the check per screen: time, money, physical effort, brain
cycles, social deviance, routine. Fix the scarcest one, then re-check, because the min moves.
Note that "the flow is pretty easy overall" is exactly the averaging error this rule exists to
prevent. Full model, the six-vs-five factor discrepancy, and the diagnosis order:
`/Users/shankhajeettaran/workspace/learning/research/behavioral-design/01-fogg-behavior-model.md`

Social deviance deserves specific attention on involuntary surfaces: a feature can be fast, free,
and familiar and still fail because using it visibly marks someone as the person who does things
differently from their team.

**Why the usual metrics lie.** Frustration in a captive population does not show up as churn. It
shows up as:

- **Workarounds** — the flow is done in a different tool and the result pasted in
- **Shadow spreadsheets** — the real system of record is an XLSX on someone's desktop
- **Support tickets and internal docs** — a colleague wrote a wiki page for your feature
- **Batching** — work that should be continuous clusters at a deadline, because the tool is only
  worth opening once
- **Data quality decay** — required fields filled with `n/a`, `-`, `test`

Engagement, retention, and DAU are all flat while every one of these gets worse. A tool with 100%
adoption and 100% mandate has no adoption signal at all.

**Measure instead:** time-on-task for the top 3 recurring tasks; count of steps that leave the
product; ticket volume per feature; how much of the required-field data is junk; where in the month
the work clusters; and how many people have written their own instructions for it. Put these in the
effort ledger as observations — see [effort-ledger.md](effort-ledger.md) for how they enter the
count.

## 6. Mental models and Jakob's Law

Users do not arrive empty. They arrive with an internal simulation of what your buttons do,
assembled from every product they have used, and they interact with that simulation
(id `mental-model`). When your system disagrees with it, they experience **your system** as broken.
The corollary that makes it operational: the designer and the user never communicate directly —
everything travels through what is visible on screen. You cannot transmit intent by explaining it,
only by building it into the surface.

`jakobs-law` is the practical instruction: people spend most of their time on other products and
prefer yours to work the same way.

**How to find the incumbent convention for a surface.** In order, stopping at the first that
answers:

1. **Platform convention** — what does the OS or the browser do? Back goes back. `⌘Z` undoes.
   Toggles apply immediately; checkboxes wait for save.
2. **Category convention** — open the two or three products in this category that most of these
   users have already used, and look at the same screen. Not the best one; the *most used* one.
3. **Your own product** — what does the equivalent control do on the other eleven screens? An
   internal inconsistency is a broken convention with a smaller blast radius, not a free choice.

If none of these answers, you are in genuinely new territory and there is no model to match — in
which case you are teaching a model, and §3 says it must be taught through the consequences of the
user's own actions, not documentation.

**When to break it.** Narrow:

> Break convention only where the novelty **is** the value. Never in navigation, authentication, or
> destructive confirmation.

The reason is where the value lands. Conform on interaction mechanics — select, scroll, undo, go
back, submit, sign in — because conformity there is nearly free and imports the user's entire
practice history. Differentiate on capability, content, and visual identity, where the difference
is the reason they came. Vim, Blender and Figma are commercially successful violations of Jakob's
Law, and all of them violate it on capability, not on how the Back button behaves.

**The trap neither law names — the near-miss.** A control that is 90% conventional is *worse* than
one that is overtly novel, because the visual resemblance fires the wrong expectation before the
difference is discovered. "Almost standard" is the worst point on the spectrum. If you break a
convention, break it visibly, one at a time. The full Familiar-vs-Novel argument, the Von Restorff
tension, and the scope limit on Jakob's Law (it is a claim about *first-run* cost — the wrong
target for a live-in tool):
`/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/00-overview-and-index.md`

**Failure behaviour:** when you cannot establish an incumbent convention and the team asserts one,
write the finding as `[UNOBSERVED]` for the convention claim and keep the observed cost separate.
"This took 6 clicks" survives being wrong about conventions; "this violates the standard pattern"
does not.

## 7. Accessibility as an audience, not a checklist

These are not a compliance appendix. Each one changes the effort ledger for a real person, and the
change is measurable in the same units as everything else in [effort-ledger.md](effort-ledger.md).

| Audience | What changes in the ledger |
|---|---|
| **Low vision** | Zoom to 200% reflows or clips the layout; every horizontal scroll is an added interaction. Small type turns a glance into a task. |
| **Motor impairment** | Small targets multiply misses; each miss is a click *plus* a recovery. Drag-only interactions have infinite cost — there is no path. |
| **Screen reader** | Order is the DOM order, not the visual order. An unlabelled icon button is an unreachable control. A live region that never announces is a silent failure. |
| **Cognitive load sensitivity** | Simultaneous decisions cost more than sequential ones. Timeouts convert a task into a failure. Dense error prose is unread. |
| **Situational** | One hand on a phone: only the bottom third is comfortable. Bright sun: low-contrast text is gone. Poor connection: every wait above 400ms is a real wait, and skeleton loaders lie about progress. |

Situational impairment is the one teams skip and the one that hits the most people. The one-handed
commuter and the low-vision user need the same thing from you, which is why this is an audience
question and not a legal one.

**The minimum, stated as numbers so a finding can cite them:**

- **Touch targets ≥ 44×44pt** (iOS) / 48×48dp (Android). WCAG 2.2 SC 2.5.8 sets 24×24 CSS px as
  the accessibility *floor* — treat 44/48 as the design target and 24 as the legal minimum, not the
  goal. The hit area does not have to be the visual area: a 24px icon with 10px of transparent
  padding is a 44px target. Treating the two rectangles as the same rectangle is the most common
  `fitts-law` violation in shipped code.
- **Visible focus** on every interactive element, in the tab order that matches the visual order.
- **Contrast** sufficient at the size actually rendered, checked in both light and dark.
- **No colour-only signalling.** A red row and a green row are the same row to a large minority.
  Pair colour with an icon, a label, or position.
- **Text survives 200% zoom** without clipping or horizontal scroll — see
  [responsive.md](responsive.md) for how this interacts with breakpoints.

**Failure behaviour:** you can observe target size, focus visibility, colour-only signalling, and
200% zoom directly in a walkthrough. You cannot observe screen-reader behaviour by looking. If you
did not drive it with a screen reader, write those findings `[UNOBSERVED]` — do not infer
accessibility from markup you read instead of used.

## 8. The audience statement

The artefact this file produces. It goes at the **top of every HLT report**, before the effort
ledger, and every later judgement is checked against it. If a finding does not follow from the
statement, either the finding is wrong or the statement is — resolve it before shipping the report.

**Exact format:**

```
AUDIENCE
  who        <technical | mixed | non-technical>   inferred from: <2–4 signals from §2>
  expertise  <first-run | occasional | daily | power>   at risk: <the band this screen fails>
  dwell      <glance | task | session | live-in>   <the observed or estimated duration>
  choice     <voluntary | involuntary>
  access     <the constraints from §7 that apply here>
  therefore  <one sentence: what this licenses, and what it forbids>
```

Any field you could not determine is written `ASSUMED:<value>` and triggers the severity cap in §1.

**Example — technical, live-in:**

```
AUDIENCE
  who        technical   inferred from: raw run IDs in column 1, cron expression input,
                         ⌘K palette, delete with undo toast and no confirm dialog
  expertise  daily       at risk: occasional — the re-run path has no visible label,
                         only a right-click menu
  dwell      live-in     observed ~4h continuous in the session; tab kept open
  choice     involuntary — internal ops tool, no alternative
  access     desktop only; dense 12px type is below comfortable at 200% zoom;
             status conveyed by row colour alone
  therefore  Optimise for throughput and stability of position: no confirmations on
             routine actions, no motion, no brand banner. Do NOT propose whitespace,
             illustration, or a guided flow. Do add a text/icon status token alongside
             the row colour, and surface re-run as a visible control.
```

**Example — non-technical, task:**

```
AUDIENCE
  who        non-technical   inferred from: plain-language field labels, no IDs anywhere,
                             illustrated empty state, confirm dialog on "Remove"
  expertise  first-run       at risk: occasional — returning users get the same
                             4-slide intro they already dismissed
  dwell      task            observed 1m50s to submit; single sitting, never revisited
  choice     voluntary — public sign-up flow, one click from leaving
  access     52% mobile per the team; primary CTA sits above the thumb zone;
             error text is red-only with no icon
  therefore  Optimise for a clean first pass: one decision per view, defaults that
             produce a working result, recoverable errors. Do NOT add density,
             shortcuts, or bulk actions. Do move the CTA into thumb reach and give
             errors a non-colour cue. Suppress the intro on second visit.
```

Both statements are three lines of work and they decide the whole report. Write it before the
walkthrough findings, not after — written after, it becomes a justification for opinions you
already had. See [walkthrough.md](walkthrough.md) for where it sits in the run, and
[critique.md](critique.md) for how the five axes consume it.
