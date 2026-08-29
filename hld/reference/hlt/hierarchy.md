# Hierarchy, colour, icons, type, breathing room

The mechanics of making a screen readable at a glance. Load this when a finding is about *what the
eye does before the brain reads* — "this feels cluttered", "I can't tell what to click", "why does
this look so busy", "everything shouts".

Two things this file does not do. It does not rank the *content* — that is
[critique.md](critique.md) axis 2. And it does not let you skip observation: you cannot blur, grey
out, or five-second-test a component tree. Every check here runs against a rendered screenshot of
the running app. If you have not walked the surface, walk it first ([walkthrough.md](walkthrough.md)).

Principle ids in this file are join keys into `data/principles.csv`. Evidence grades shown inline
are illustrative. Take the live grade from `python3 scripts/why.py --name <id>`; if this file and
the CSV disagree, the CSV wins.

Source material, one hop:
`/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/03-gestalt-and-perception.md`
and `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/01-cognitive-load-and-memory.md`.

---

## 1. The scan path

Before any word is read, the eye has already sorted the screen. It sorts in this order, and each
stage narrows what the next one looks at:

1. **Size** — the biggest thing wins first, regardless of what it says.
2. **Contrast** — luminance distance from the background. Survives blur, greyscale and low vision.
3. **Colour** — pulls the eye pre-attentively, but says *different*, not *more important*.
4. **Position** — reading order. Top-left in LTR; first and last of any sequence
   (`serial-position-effect`).
5. **Whitespace isolation** — an item alone in space reads as its own unit, even when it is small.

You do not get to opt out of this. The screen is already ranked by these five whether you specified
a rank or not (`law-of-pragnanz`). Your job is to make the perceived rank match the real one.

**The failure condition.** If two things compete for first, the page has no first, and the user
picks by accident. That accident then reads to you as a preference in the analytics. When you catch
this, the finding is not "these two are both prominent" — it is "the user cannot tell which one you
meant", severity `high` or above if the two lead to different outcomes.

### The three tests, in this order

Run all three. They catch different things and none subsumes another.

**Blur test (squint / 8 px Gaussian).** Strips detail, keeps mass, colour and position.
- *Catches:* how many units the page really has, where the group boundaries fall, and whether a
  single element wins first. Compare the blurred unit count against your intended information
  architecture — if they differ, the layout is wrong no matter how sensible the structure is.
- *Misses:* colour-only meaning (blur preserves hue), and anything that depends on reading.

**Greyscale test.** Strips hue, keeps detail and luminance.
- *Catches:* every place colour is the sole carrier of meaning — status pills, chart series,
  required-field markers, error states, "the green one is selected". Also catches rank that was
  faked with hue when it needed contrast: if the primary button and the secondary button are the
  same grey, they had no contrast difference, only a colour difference.
- *Misses:* grouping at a glance — greyscale keeps every detail, so a badly grouped screen still
  looks organised.

**Five-second test.** Show the screen for five seconds, hide it, then ask two questions: *what is
this page for* and *what would you do next*.
- *Catches:* whether the winner of the scan is the **right** winner. Blur tells you a first exists;
  it cannot tell you that the first should have been "Publish" rather than the illustration.
- *Misses:* everything structural that a viewer can compensate for in five seconds of effort.

When you cannot recruit a person, run it on yourself with a timer and write down the answer before
looking again. A remembered answer after re-reading is not a five-second result — say `[UNOBSERVED]`
rather than pretending.

---

## 2. Rank signals and their costs

| Signal | Rank it buys | What it costs | How it fails when overused |
|---|---|---|---|
| **Size** | Most per unit, and coarsest. Wins the first scan outright. | Vertical space. A hero that ranks well pushes the action below the fold. | Three large things means no large thing. Size inflation is one-way — you cannot escalate past the biggest element you already shipped. |
| **Weight** | Moderate, and free of layout cost. 400→600 at the same size buys a clean level. | Extra font files; bold at ≤12 px loses letterform detail on low-DPI screens. | Bold everywhere reads as shouting, and the eye stops treating bold as signal at all. |
| **Colour** | Strong pull, but **unordered** — it marks a category, it does not rank. | It is the meaning channel. Rank spent on hue collides with status semantics. | Six accents means no accent. Fails outright in greyscale and for colour-blind users. |
| **Contrast** | Strongest *ordered* signal after size, and the only one that survives blur, greyscale and low vision together. | A finite budget: there is only so much luminance distance to the background before you hit pure black or white. | Everything at maximum contrast leaves nothing able to recede, so secondary text competes with primary. |
| **Position** | Strong and free. Primacy and recency are real slots (`serial-position-effect`). | Only a handful of privileged positions exist per layout. | Not really overusable — but it is the signal that reflows away first. A rank that lives only in position is gone at 375 px. See [responsive.md](responsive.md). |
| **Whitespace** | Buys rank with zero ink. Isolation reads as importance. | Vertical space, same bill as size. | Uniform generous spacing isolates nothing. Space only ranks *relative* to other space. |
| **Border** | Buys **grouping**, not rank (`law-of-common-region`). | Adds visual weight to every group it draws. | A page of boxes has no hierarchy at all. |
| **Elevation** | Buys "above the page / temporary / interactive". | Renders unreliably in dark themes — a shadow on a dark surface is close to invisible, so dark mode carries the same job on surface lightness. | Everything floating is flat again, and the modal loses the one cue that said it was a modal. |
| **Motion** | Breaks the attention filter better than any static signal — it is a threshold effect, not an intensity one (`selective-attention`). | Highest cost in the table: `prefers-reduced-motion`, vestibular impact, and a delay before the information is legible. | Attention inflation. Motion on every panel trains the filter to discard the whole class, and you have then spent the only signal that reliably breaks through. |

**The rule: use the fewest signals that produce a clear order.** One primary signal per rank level,
plus at most one reinforcing signal. Never stack four on one element.

Why four is the ceiling and not a taste call: signals do not add, they exhaust. An element that is
larger *and* bolder *and* accent-coloured *and* boxed *and* shadowed has consumed the entire
vocabulary, so the next-most-important element has no way to be second without also stacking. Do
that twice and every candidate stacks. That is exactly how a page ends up with six "most important"
things, and the user resolves it by clicking whatever is nearest the pointer.

**Failure behaviour.** When you cannot decide which signal to drop, drop back to contrast plus
position and re-run the blur test. If a single element still wins, the other signals were decoration.
If none wins, the problem is that you have two genuine primaries — that is a content decision, not a
styling one, and the finding belongs on the effort or flow axis instead.

---

## 3. Grouping

Grouping is not something you add. It is something you can only fail to control — the eye groups
from four cues whether or not you specified them. The cues are not equal, and they conflict on real
screens. Full treatment, including the priority evidence:
`/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/03-gestalt-and-perception.md`.

```
weakest ──────────────────────────────────────────────────► strongest
 law-of-proximity  <  law-of-similarity  <  law-of-uniform-connectedness ≈ law-of-common-region
 (relative gap)       (shared attribute)    (visible link)                 (enclosed area)

 spends no ink ────────────────────────────────────────────► spends a box
```

**Reach for proximity first, common region second, borders last.**

**`law-of-proximity` — whitespace groups more cheaply than borders.** Proximity is *relative*: what
makes two items a group is that the gap between them is smaller than the gap to everything else.
"Put related things close together" is not actionable, because everything is close to something.

> **Gap ratio heuristic — mark it as a heuristic, not a finding.** Between-group gap ÷ within-group
> gap ≥ **2** is unambiguous; **1.5** is marginal; below **1.25** grouping is broken. On an 8 px
> scale that means 8 inside / 24 between, not 8 / 12. This number is the research file's own working
> figure, not a published constant — `principles.csv` carries the principle's claim and its grade.
> Do not report a ratio miss as a research-backed defect; report it as a measurement plus its
> observable consequence.

The negative case, and it is the highest-value one: a form label sitting 12 px above its own field
and 12 px below the previous field belongs to neither. Users answer the wrong question and you see
it as a data-quality problem three systems downstream.

**`law-of-common-region` — a border or fill makes everything inside one object,** and it beats
proximity and similarity when they disagree. Two consequences you must plan for:
- A region **resets the local spacing frame**. Once you draw the box you have spent your strongest
  cue and can no longer subdivide inside it with gaps of similar weight.
- A region is a **semantic claim**. If you cannot name the entity the card represents — one invoice,
  one setting group, one recipe — it should have been spacing.

Escalate in order: **gap → background tint → border → elevation.** Move up a rung only when the
previous one demonstrably fails the blur test. Cap region nesting at two levels; a card inside a
card inside a panel produces boxes with no hierarchy, which is the common-region failure mode with
its own name in the source: card soup.

**`law-of-similarity` — same appearance ⇒ same behaviour, and different behaviour ⇒ different
appearance.** This is the only grouping cue that can *lie*, because it makes a claim about
behaviour, which is a claim about code, and code drifts away from styling. Most design systems
enforce the first half through components and almost none enforce the second — which is how a
destructive action ends up wearing the secondary-button style. Check the second half explicitly.

**`law-of-uniform-connectedness` — reserve connectors for relations that carry information beyond
membership:** sequence, hierarchy, dependency, state-sharing. Membership alone is spacing's job.
That single rule removes most line clutter. A stepper's connecting line is the thing that conveys
order — delete it and five circles become five unordered tabs. A rule under every list item is the
same instrument spent on nothing.

**Failure behaviour when cues disagree.** Strength is cue *type* × cue *magnitude*, so a 200 px gap
still beats a 1 px hairline at 5 % contrast. When you observe a contradiction — a divider drawn
through a group that spacing established — do not average them. Delete the weaker instrument and
re-blur.

---

## 4. Colour

### The token rule comes first, and it is absolute

**Never write a hex literal in a component. Every colour comes from a semantic token** —
`--primary`, `--foreground`, `--muted-foreground`, `--border`, `--destructive`, and so on.

The reason, not the convention: organisation branding overrides these tokens **at runtime**. A
hard-coded colour does not fail loudly — it silently survives the override, so a custom-branded
workspace ends up with one element still wearing the default palette and nobody sees it until a
customer does. In this user's monorepo this is a stated review finding, not a preference; the token
table lives at
`/Users/shankhajeettaran/workspace/office/assistents/assistents-monorepo/docs/UI-DESIGN.md`
(§ Token reference).

**Failure behaviour — the case the rule does not enumerate.** If no existing token fits the colour
you need, the correct output is a `global`-scope finding that the token set is missing a role. It is
never "hard-code it for now". A hex literal added under time pressure is indistinguishable from an
intentional one six months later, and nobody greps for it.

### Semantic colour

Four roles carry meaning and must be used for nothing else: `destructive`, `warning`, `success`,
`info`. One meaning per hue across the entire product. If red means "will delete data" on one screen
and "recording" on another, similarity has told the user something false, and the cost lands on the
screen where they guessed wrong.

**Colour must never be the sole carrier of meaning.** Pair it with an icon, with text, or with
position. Two reasons, and the second is the one people forget:
- Colour-blind users — roughly 1 in 12 men — receive no signal at all from a red/green distinction.
- Greyscale reproduction: printed invoices, faxed forms, screenshots in a monochrome ticket, and
  e-ink readers all flatten hue to luminance.

The check is mechanical: run the greyscale test from §1. Anything you can no longer distinguish was
colour-only. The fix is an added glyph or word, not a "more distinguishable" pair of colours.

### Saturation discipline

Saturation budget is set by **dwell time**, not by taste. A screen a user glances at for eight
seconds tolerates saturation that becomes fatiguing on a screen they sit in for six hours. Get the
dwell-time judgement from [audience.md](audience.md) before proposing a palette change — a
saturation finding without a dwell-time claim is an aesthetic preference wearing a lab coat.

---

## 5. Icons

### When an icon alone is acceptable

All three conditions, not any one of them:

1. **Universally conventional** — the glyph means the same thing across products the user already
   uses (`jakobs-law`).
2. **Frequently used by this audience** — repetition builds the association. A control touched once
   a quarter never gets learned.
3. **Reinforced by a fixed position** — top-right close, leading-edge back, the same toolbar slot
   every time. Position does half the work of recognition.

Otherwise: **icon + label.** Not icon with tooltip.

**A tooltip is not a fix.** It requires hover, and hover does not exist on touch — which is where
half your traffic is. Even on a pointer device it costs a dwell delay before the label appears, so
the user pays a wait to learn what they could have read. If your defence of an icon-only control is
"there's a tooltip", the control is unlabelled.

### The honest finding

Most icons are not self-evident. Icon-only toolbars are a recognised usability cost, and the cost is
paid by exactly the users least able to absorb it — new, occasional, and non-native-language users.
State it that way in a finding. Do not soften it to "consider adding labels", and do not overstate
it either: for a daily-use professional tool the cost may be correctly accepted, and the finding
then reads "accepted cost, unlabelled by design" with the audience named.

### Genuinely conventional (icon-only is defensible)

magnifier = search · X = close/dismiss · ← or chevron-left = back · ⌂ = home · + = add/new ·
chevron ▸/▾ = expand/collapse · ⋮ or ⋯ = more actions on this item · ↻ = refresh · ⬇ = download ·
🖨 = print · hamburger ≡ = **navigation** menu

### Commonly misused (label them)

- **Hamburger for anything that is not navigation** — filters, a settings drawer, a density menu.
  The glyph is learned as "the nav lives here"; every other use spends that learning.
- **Three dots vs three lines.** ⋮/⋯ means "more actions on this row". ≡ means navigation, or a drag
  handle. They get swapped constantly, and a three-line drag handle next to a three-line nav toggle
  is unreadable at any size.
- **Floppy disk for save.** The referent has not existed for two decades; it survives on convention
  alone and collides with export and download in the same toolbar.
- **Gear for anything.** It means "settings", and it gets used for filters, display density, admin,
  account, and per-widget configuration. Four gears on one screen mean four different things.
- **Magnifier for zoom vs search.** Same glyph, two jobs. If both exist on one screen, label both.
- **Heart vs star vs bookmark.** Favourite, rate, and save-for-later are three meanings across three
  glyphs with no stable mapping.
- **Circular arrow** — refresh, undo, history, and sync all claim it.
- **Eye** — preview, visible/hidden toggle, and mark-as-read.
- **Pencil** — edit, annotate, rename.
- **Cloud with arrow** — upload, sync, backup.
- **Any glyph for a concept that only exists in your product.** There is no convention to inherit,
  so it is never self-evident. Always label, including in the toolbar.

---

## 6. Type

**Use a ratio-based scale.** Pick one ratio and generate the steps from a base: 1.200 (minor third)
for dense product UI, 1.250 (major third) where the page has room. From a 16 px base at 1.200:
12 · 14 · 16 · 19 · 23 · 28 · 33, rounded to the nearest even value your system uses.

Arbitrary sizes destroy hierarchy because the eye reads *relative* difference, not absolute size. A
1 px step reads as an accident rather than a level, so somebody adds another size to make the point,
and you end up with 15, 16, 17, 18 and 19 all in use and no perceptible order between them. If two
sizes on a screen are within ~10 % of each other, they are one level and one of them is noise.

**Weight over size for secondary emphasis.** Going 400 → 600 at the same size buys a level without
changing line height, column height, or where the fold lands. Size changes reflow; weight does not.
Reach for weight first, and only step the size when weight has already been spent.

**Line length 45–75 characters** for anything read in sentences. Above ~75 the return sweep to the
start of the next line becomes unreliable and readers re-read or skip lines outright — the failure
is silent, it shows up as "this page is exhausting", never as "the measure is too wide". Below ~45
there are too many sweeps and the rhythm breaks. Set it with `max-width` in `ch`, not `px`, so it
tracks the font size instead of fighting it.

**Line height by size.** Body 1.5–1.6 · headings 1.1–1.25 · single-line UI labels and controls
1.0–1.2. The reason is the same return sweep: leading exists to make the next line findable, and a
heading that wraps once at 1.6 reads as two unrelated lines rather than one heading.

**More than three type sizes on one screen usually means the hierarchy is doing work the layout
should do.** Failure behaviour when you need a fourth: do not add it yet. Try grouping (§3) or
position first, and add the size only once the group structure is already correct. A fourth size
laid over bad grouping produces four levels of an order the user still cannot see.

---

## 7. Breathing room

The user's phrase for this was "so users do not feel caged". Concretely:

- **One spacing scale, used everywhere.** 4 px or 8 px base, geometric steps. Two competing scales
  in one product is the same defect as two type scales — the eye cannot read a level out of an
  inconsistent step.
- **Space belongs BETWEEN groups more than inside them.** This is the whole mechanism of §3: a group
  is only a group because its internal gaps are smaller than its external ones. Adding space evenly
  adds no structure — it just makes the page longer.
- **Padding proportional to container size.** A 320 px card with 32 px padding is cramped and empty
  at once. Roughly: small container 12–16, medium 20–24, page section 32–48. Scale padding with the
  container, not with the designer's mood.

### Symptoms of a caged UI

These are observable, so each one is a reportable finding:

1. **Content touching container edges.** A bordered box with zero padding — text sitting on the
   line. The most common single symptom, and it reads as "unfinished" before it reads as "tight".
2. **Uniform spacing everywhere.** Every gap the same token, so nothing groups. Usually a design
   system with exactly one spacing value in real use.
3. **A border on every element.** Ink spent on structure that spacing already carried; the page
   reads busier while conveying the same information.
4. **No resting area.** Every pixel assigned to a component, no full-bleed band, no empty column.
   The eye has nowhere to land between tasks.
5. **Modals that fill the viewport.** A modal that fills the screen is a page. It loses the
   common-region boundary that made it read as temporary, so users lose track of what they will
   return to.
6. **Row height equal to text height** in tables and lists — no vertical padding, so horizontal
   tracking across a wide row fails.
7. **Sticky header plus sticky footer plus sticky sidebar** leaving a live area smaller than the
   chrome around it. Measure it; if chrome exceeds content area at 1280×800, report it.

### The counter-argument, stated honestly

**Density is correct for live-in professional tools.** A trading terminal, an ops console, a
40-row admin table, a log viewer — those users have high dwell time and high frequency, and paying
them in scrolling is worse than paying them in density. "Add whitespace" applied to those surfaces
is a bad recommendation, and reviewers make it constantly because sparse screenshots photograph
well (`aesthetic-usability-effect` [contested]).

The rule is **consistent rhythm, not maximum space.** In a dense tool the *ratio* still has to hold
— 4 px inside a group, 12 px between is a perfectly readable dense rhythm — what changes is the base
unit, not the relationship. Before proposing more space anywhere, get the dwell time and frequency
from [audience.md](audience.md). A spacing finding on a daily-driver tool with no dwell-time claim
attached should not be filed.

---

## 8. The hierarchy audit

Ten checks. Each has a decidable answer — you can be wrong, but you cannot be vague. Run them
against screenshots from the walkthrough, in both light and dark, at a desktop viewport.

| # | Check | Decidable answer | Catches |
|---|---|---|---|
| H1 | Blur to 8 px. Name the element that wins first. | One name, or fail. | Competing primaries; a page with no first. |
| H2 | Greyscale. Is any status, state, category or requirement conveyed by hue alone? | Yes / no, plus the list. | Colour-only meaning; rank faked with hue. |
| H3 | Five seconds. Can the viewer name the page's purpose *and* the next action? | Both / one / neither. | A clear hierarchy pointing at the wrong element. |
| H4 | Grep the changed components for hex literals and named CSS colours. | Zero, or the list of files and lines. | Branding overrides silently defeated. |
| H5 | For the three most prominent elements, count rank signals (size, weight, colour, contrast, position, whitespace, border, elevation, motion). | A number each. ≤2 passes. | Signal stacking that leaves nothing to escalate to. |
| H6 | For each visual group, measure between-group gap ÷ within-group gap. | A ratio each. ≥2 passes. | Ambiguous membership — labels bound to the wrong field. |
| H7 | For each border, ask whether a gap or a background tint carries the same grouping. | Yes = finding. Also: max region nesting depth. | Card soup; ink spent where whitespace would do. |
| H8 | List every icon-only control. Does each satisfy conventional **and** frequent **and** position-reinforced? | All three, or name the failing one. | Unlabelled controls defended by a tooltip. |
| H9 | Count distinct type sizes on the screen; measure body line length in characters. | A count (≤3) and a number (45–75). | Hierarchy doing the layout's job; unreadable measure. |
| H10 | Re-run H1 and H7 in the opposite theme. | Same result / different. | Tinted regions that collapse to invisible in dark mode; shadows that vanish. |

Report each failure in the standard format. One worked example:

```
F-12  [medium]  scope: template-level   axis: cognition
  screen    /settings/notifications
  observed  screenshot 07, 8px blur
  action    loaded the page, no interaction
  cost      2 competing primaries · 5 rank signals on "Save" · gap ratio 1.1
  principle law-of-proximity [replicated] · law-of-common-region [replicated]
  problem   Every setting sits in its own bordered card with equal gaps, so the eye
            finds sixteen units and no groups; the user reads all sixteen labels
            to find the one they came for.
  proposal  Drop the per-row borders. Group the rows into three labelled sections
            with 8px inside / 24px between, and keep one border per section.
  build     M · the shared SettingsRow and SettingsSection components; affects
                  every settings page that uses them.
```

Rules for the audit output, and each one exists because its absence has produced a bad report:

- **Scope every hierarchy finding before you write the proposal.** Spacing tokens, type scale and
  colour tokens are `global` almost by definition — a padding change that looks like a one-screen
  win is how eleven other screens regress. If the fix touches a token or a shared component, say so
  in the `build` line and name the blast radius.
- **A failed check is not automatically a defect.** H9 failing on a data-dense console may be
  correct for that audience. Where you accept a failure, write it as a finding with severity `nit`
  and the accepted-cost reasoning, rather than dropping it — a silently skipped check reads as a
  passed one.
- **Never report H1 or H3 from source code.** Both require a rendered pixel. If the app would not
  run, the check is `[UNOBSERVED]` and carries no severity.
- **Batch the ten checks into one round.** Re-blurring after every tweak spends the user's money to
  reproduce what the first pass already found.
