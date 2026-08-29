# Responsive — desktop → tablet → mobile

A layout that only works at 1440px is unfinished, not responsive. This file says how to check the
other widths for real, what each class of component is supposed to become, and how to tell a genuine
width defect from the three things that look broken at 375px and are not.

Responsiveness is axis 5 of every `review`. It is the last axis because getting it wrong costs less
than getting effort wrong — not because it is optional.

---

## 1. The verification rule

**Every finding is checked at three widths, or it is reported as unverified.** Not "the CSS has a
`@media (max-width: 768px)` block, so it reflows". A media query proves a rule exists; it does not
prove the rule produces a usable screen. Reading the stylesheet is the same category of mistake as
reading the API response instead of clicking the button — see [walkthrough.md](walkthrough.md).

The three widths, in this order:

| Pass | Preset | Size | Input emulated |
|---|---|---|---|
| 1 | `desktop` | 1280 × 800 | mouse, hover works |
| 2 | `tablet` | 768 × 1024 | **mouse** — not touch |
| 3 | `mobile` | 375 × 812 | touch: Android UA, 5 touch points, mouse→touch translation, **no hover** |

The method, per width:

```
resize_window { preset: "mobile" }     # or explicit width/height
navigate      { url: <same url> }      # RELOAD — see below
computer      { action: "screenshot" }
```

**Reload after every resize.** Device gates that run at load time — a `matchMedia` check in a
mount effect, a server-rendered layout branch, a touch-capability sniff, a chart that reads its
container width once — do not re-run on resize. Skip the reload and you screenshot a desktop layout
squeezed into 375px and file three findings against a mobile view that never rendered.

**The tablet preset is not a touch device.** Emulation switches on below 768px, and 768 is not below
768. If you need a touch-emulated tablet-width viewport, pass `width: 767, height: 1024` explicitly
and reload. If you skip this, you will pass a tablet that mis-handles every hover affordance in §3.

**768 also lands on the wrong side of the common breakpoint.** Tailwind's `md:` is
`min-width: 768px`, so at exactly 768 you are looking at the *desktop* branch of every `md:` rule
and the *mobile* branch of every `lg:` rule. That is a real state a real user sees, so keep the
preset — but when you need the sub-768 branch, use 767 and say which you used.

**Resize back to desktop is a reload too.** The touch emulation from pass 3 persists on that tab.
Go back to 1280 without reloading and hover produces nothing, and you will report "the row actions
never appear on desktop" — a defect you manufactured with the tool. This has happened. Reload.

**Screenshot at every width and name the width in the filename or the caption.** Findings reference
screenshots (`observed screenshot 11 (mobile) vs 04 (desktop)`), and an unlabelled screenshot cannot
carry a width-specific claim.

`resize_window` also takes `colorScheme`. Sweep themes at desktop only, unless the theme changes
layout — it usually changes colour, and colour is [hierarchy.md](hierarchy.md), not this file.

**When a width cannot be reached** — the tool is absent, the app refuses to render, an auth wall
only serves desktop — stop and say which width is missing. Findings for that width are written
`F-nn [UNOBSERVED]` and carry no severity. Do not infer the mobile layout from the desktop DOM.

---

## 2. What actually changes

Not "it gets narrower". Each component class has a target transformation and a characteristic way of
failing.

| Class | Desktop | Tablet | Mobile | Failure mode |
|---|---|---|---|---|
| Navigation | persistent sidebar | collapsible / icon rail | bottom bar or drawer | destinations become invisible; users stop knowing what the app contains |
| Data table | full columns | fewer columns | see §2.1 | eight columns crushed into 375px, unreadable at any zoom |
| Form | 2–3 columns | 1–2 columns | 1 column | fields reflow into a different reading order than the tab order |
| Modal | centred dialog | centred, wider | full-screen sheet | close control lands under the notch or off-canvas |
| Filter panel | inline sidebar | drawer | dedicated screen | filters become unreachable while results are visible, so nobody filters |
| Chart | full axes + legend | legend below | see §2.5 | axis labels overlap into grey mush; units disappear |
| Toolbar | all actions visible | primary + overflow | 1–2 + overflow | the destructive action survives and the primary one goes into the menu |
| Wizard | horizontal stepper | horizontal stepper | compact "3 of 5" | progress indicator vanishes entirely, taking the sense of an end with it |

Two things are true of the whole table. First, hiding navigation has a cost: an item behind a
hamburger is discovered by people who already knew it was there. Hide nav on mobile because the
space genuinely is not there — not because it tidies the header. Second, complexity does not
evaporate at a breakpoint; it moves (`teslers-law`). When you hide something, name where the work
went. If the answer is "the user now remembers it", you moved the work onto the human.

### 2.1 Data tables — the hardest case

Ranked. Take the highest option the data allows.

1. **Horizontal scroll with a frozen key column.** The identifying column (name, invoice number,
   date) stays pinned; the rest scrolls. Right when the table is genuinely tabular and users compare
   rows on values. Requires a visible scroll affordance — a shadow on the frozen edge, or a clipped
   partial column. Without it, users do not know the columns exist.
2. **Card per row.** Each row becomes a stacked block: title, 2–4 labelled values, actions. Right
   when rows are read individually rather than compared, and when there are fewer than ~8 fields.
   Costs vertical space fast; 200 rows of cards is an infinite scroll.
3. **Priority columns + detail view.** Show 2–3 columns; tapping a row opens the full record. Right
   when the table is a directory into detail. Costs one navigation per row, so it is wrong for
   scan-and-compare work.
4. **A genuinely different mobile view** — a grouped list, a summary, a search-first screen. Right
   when the mobile task is not the desktop task. The most work and occasionally the only honest
   answer.

**Squeezing eight columns into 375px is never one of the four.** It produces 40px-wide cells, wrapped
single characters, and a table nobody reads. If you see it, that is a finding, and the proposal names
which of the four to move to.

### 2.2 Forms

Multi-column → single column, always. A two-column form at 375px either overflows or produces 140px
inputs that clip their own content.

- **Labels above inputs, not beside.** Side labels eat width the input needs, and at narrow widths
  they wrap to two lines and break vertical rhythm. Placeholder-as-label is not a substitute: it
  disappears on focus, so the user loses the label exactly when they need it.
- **Inputs full width of the container**, height ≥44px (§3). A 32px-tall input is a desktop habit.
- **Match the keyboard to the field.** `type="email"`, `type="tel"`, `inputmode="numeric"`,
  `inputmode="decimal"`, `autocomplete="postal-code"`. Wrong keyboard costs a keyboard switch per
  field — count it in the ledger ([effort-ledger.md](effort-ledger.md)).
- **Check reading order against tab order after reflow.** A CSS grid that reorders visually does not
  reorder the DOM. Two columns collapsing to one can produce a form that reads top-to-bottom and
  tabs left-to-right-then-back.
- **The submit button must be reachable without hunting.** A submit pinned top-right after 900px of
  fields is a Fitts violation on desktop and worse on mobile (`fitts-law`).

### 2.3 Modals

Centred dialog → full-screen sheet below ~600px. A centred modal at 375px is a modal with 8px of
margin, which is a full-screen sheet wearing a border.

Close affordance: **top-left or top-right, always visible, never scrolled away.** If the sheet
scrolls, the header is sticky or the close button is gone. A sheet with no visible close and no
back-gesture is a trap, and the user's escape is to reload the page and lose their input.

Primary action pinned to the bottom, above the safe area. Do not rely on the browser's own back
gesture to dismiss — on the web it navigates away from the page, discarding the form.

### 2.4 Sidebars and filter panels

Inline → drawer → dedicated screen. The rule that matters: **applied filters must remain visible
when the panel is closed.** Chips above the results, with a count. A drawer that closes and shows no
trace of what it did produces the classic "why are there only 3 results" support ticket, and the
recovery is to reopen the drawer and read every control — count that as Recovery.

### 2.5 Charts

Drop in this order: gridlines, minor tick labels, the legend (replace with direct labels or a
below-chart key), data-point labels, then the series count itself.

**Never drop the axis units.** A chart reading `0 – 40 – 80` with no unit is not a simplified chart,
it is a chart that now says nothing — the reader cannot tell dollars from percent from count. Same
for the time range. If units and range will not fit, the chart is the wrong component at that width;
show a stat tile with the number and a sparkline.

Charts are the most common victim of the missing reload: many chart libraries measure their
container once at mount, so a resized-not-reloaded chart renders at the old width and overflows.
Confirm the overflow survives a reload before filing it.

### 2.6 Toolbars

Primary action stays visible at every width. Everything else collapses into an overflow menu, in
frequency order — and because the first and last items in a menu are the ones remembered
(`serial-position-effect`), do not bury the second-most-used action in the middle.

**Destructive actions do not get promoted by collapse.** The common bug: the overflow rule keeps the
first N buttons and "Delete" happens to be third in the DOM, so at 375px the toolbar reads
`Save · Delete · ⋯`. Delete belongs in the overflow, behind confirmation, at every width.

### 2.7 Multi-step flows

The progress indicator is the flow's contract with the user: it says how much is left
(`goal-gradient`). Horizontal steppers do not fit at 375px, so they get deleted — and the wizard
becomes an unbounded sequence of screens, which is where people abandon.

Replace, do not remove: `Step 3 of 5` plus a thin progress bar costs one line of vertical space.
Keep the current step's name; drop the other four names, not the count.

---

## 3. Touch

**Targets ≥44px, with spacing between them.** Apple HIG 44×44pt, Android Material 48×48dp, WCAG 2.2
SC 2.5.8 sets 24×24 CSS px as the accessibility floor — treat 44/48 as the design target and 24 as
the legal minimum, not the goal (`fitts-law`, evidence `replicated`).
Source: [/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/02-interaction-and-system-response.md](/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/02-interaction-and-system-response.md)

Hit area and visual area are different rectangles. A 24px icon with 10px of transparent padding is a
44px target that looks like a 24px icon. Measure the target, not the glyph.

**Spacing is not part of Fitts's formula and matters for a different reason:** the cost of a miss is
whatever the neighbour does. Two adjacent 44px targets 2px apart still mis-tap, and each mis-tap
costs a recovery step — back out, re-orient, re-aim. If the neighbour is destructive, the mis-tap
costs a record. Count mis-taps as Recovery in the ledger; never report a target-size finding without
the adjacency check.

**Thumb zones on a large phone.** The bottom centre and the same-side lower edge are cheapest; the
**top two corners are the hardest reach** and require a grip change. That makes the top corners the
right home for destructive and rarely-used actions and the wrong home for the primary action. A
"Delete account" pinned bottom-right on mobile is a design defect even at 44px.

Note the browser caveat: a native app's screen edge stops the pointer, giving edge targets effectively
infinite depth. Your web app has no screen edges — every viewport edge abuts browser chrome. A
`position: fixed` bottom bar on mobile comes closest, because there the phone edge is the app edge.

**Hover does not exist.** At the mobile preset, hover produces nothing at all. What breaks and what
replaces it:

| Hover-only affordance | What the touch user gets | Replacement |
|---|---|---|
| Tooltip explaining an icon | nothing — an unlabelled glyph | visible text label, or tap-to-open popover |
| Hover-opened menu | nothing, or a menu that opens and instantly closes | explicit tap to open, tap-outside to close |
| Row actions revealed on hover | an invisible feature | always-visible overflow `⋯` per row, or swipe with a visible hint |
| Hover-only delete on a card | either invisible, or fires on first tap | overflow menu + confirmation |
| Hover preview / expand-on-hover | nothing | tap to expand inline, or a detail sheet |
| `title` attribute anywhere | nothing | it was never accessible; replace at all widths |

The dangerous one is the middle case: mouse→touch translation can turn a hover-reveal into a
tap-to-fire, so the first tap that was meant to reveal the control instead activates it. Test the
first tap on any hover-revealed control and report what actually happened.

---

## 4. Drop, stack, defer, or keep

A decision rule, run per element, in order. Stop at the first line that matches.

1. **Keep, unconditionally**, if the element is: the primary action for this screen's task, an error
   message, a validation state, a destructive-action confirmation, a price or total, or anything
   legally required (consent, disclosure, terms). These never move behind a tap and never disappear
   at a breakpoint. If it will not fit, the layout is wrong — not the requirement.
2. **Drop** only if the element is genuinely redundant at this width — a decorative image, a second
   copy of information already on screen, a column that repeats the row title, a legend replaced by
   direct labels. Redundant means "the same information is still visible", not "less important".
3. **Defer** (behind a tap, disclosure, or second screen) if a minority of users need it for this
   task. Deferring costs one interaction plus one decision for the people who need it; that is the
   right trade when they are few and wrong when they are most.
4. **Stack** everything else. Stacking is the default and it is boring and it is usually correct.

**"They won't need that on mobile" is an assumption, not a design principle.** Mobile is not a
reduced audience — it is often the whole audience for a task (approving something between meetings,
checking a number on the way to one). Before dropping a capability on mobile, say what evidence
supports it: analytics, a user statement, or the task genuinely being impossible on a phone. Absent
that, stack it. The failure this prevents is the common one — a feature dropped on mobile because it
was awkward to lay out, discovered a quarter later when someone asks why the mobile numbers are flat.

---

## 5. Beyond width

Four conditions that break the same layouts and are almost never checked.

- **Zoom to 200%.** A desktop accessibility requirement (WCAG 1.4.4 covers text to 200%; 1.4.10
  reflow requires 320px-equivalent). At 1280px zoomed to 200% the layout gets ~640 CSS px — a
  breakpoint most apps never test because it is neither desktop nor a phone. Symptoms: fixed-width
  sidebars overlapping content, horizontal page scroll, sticky headers eating half the viewport.
  Check it the same way: set the browser zoom, reload, screenshot.
- **Landscape phone** (~812 × 375). Vertical space collapses to ~375px and every sticky element
  competes for it. A 64px sticky header plus a 56px bottom bar plus the browser's own chrome can
  leave under 180px of content. Modals with a pinned footer are the first casualty — the primary
  button ends up below the fold of a sheet that does not scroll.
- **Small laptop at 1280.** The most common real screen and the most commonly untested, because
  designs are drawn at 1440 or 1920. This is why the desktop preset is 1280 and not 1440: if
  something breaks between 1280 and 1440, it breaks for the largest single group of users. A
  three-column dashboard that needs 1400px is a defect, not a preference.
- **Slow connections.** The skeleton, spinner, and empty state are the real first impression on a
  phone, not the loaded screen. Anything over the 400ms Doherty Threshold is a felt wait
  (`doherty-threshold`); a mobile network turns a 300ms desktop fetch into 1.5s routinely. Look at
  what renders during the wait: a skeleton with the right shape reads as fast, a full-page spinner
  reads as broken, and a blank screen reads as a crash. Waits go in the ledger's `W` component.

---

## 6. The responsive audit

Run this checklist at each of the three widths after the reload. Findings are batched, not filed one
at a time — one round, per [walkthrough.md](walkthrough.md).

**Desktop 1280 × 800**
- Does the layout need more than 1280? Horizontal scroll on the body is a defect.
- Do line lengths exceed ~90 characters? Long measure at wide widths is a real reading cost.
- Zoom to 200%, reload, look again.

**Tablet 768 × 1024 (mouse) and 767 (touch)**
- What did the navigation become, and can you still name every top-level destination?
- Did a three-column layout become two, or did it become one prematurely and waste 200px?
- At 767, does anything that was hover-driven at 768 still work?

**Mobile 375 × 812 (touch)**
- Body horizontal scroll? (A wide table scrolling *inside its own container* is fine — §7.)
- Every interactive target ≥44px, with spacing from its neighbours?
- Is the primary action visible without scrolling, and out of the top corners?
- Every hover affordance from the §3 table — check each one by tapping.
- Tables: which of the four §2.1 options is in use, and is it the right one?
- Charts: are the axis units still present?
- Modals: is the close control visible and does the sheet scroll?
- Forms: one column, right keyboard per field, tab order matches reading order?
- Wizard: is progress still stated?

**The finding must name the width.** A responsive defect without a width is unactionable — nobody
knows what to open.

```
F-12  [high]  scope: template-level   axis: responsiveness
  screen    /billing/invoices @ 375×812 (mobile preset, touch, reloaded)
  observed  screenshot 11 (mobile) vs screenshot 04 (desktop)
  action    reloaded at 375, tried to read the Amount column, tapped row 3
  cost      3 horizontal scrolls · 1 mis-tap on the adjacent Delete · 1 backtrack
  principle fitts-law [replicated] · conflicts: pareto-principle
  problem   Eight columns compress to ~44px each; Amount wraps to three lines and
            Delete sits 2px from the row link, so opening an invoice deletes one.
  proposal  Freeze the Invoice # column, scroll the rest horizontally, and move
            Delete into a per-row overflow menu behind confirmation.
  build     M · the invoice table component, shared by 4 routes
```

If the same defect appears at two widths, file one finding and name both. If it appears only at one,
say so — "mobile only" changes the fix and the priority.

---

## 7. Common false findings

Three things look broken at a narrow width and are not. Reporting them wastes the user's review time
and costs you credibility on the findings that are real.

**1. Intentional horizontal scroll inside a wide data table.** A table in its own
`overflow-x: auto` container, scrolling while the page body does not, is the correct pattern (§2.1,
option 1). How to tell it from a defect: scroll the *page* left and right. If the body moves, it is a
defect — something is overflowing the viewport. If only the table moves and the surrounding layout
holds, it is by design. The remaining question is not "why does it scroll" but "is there a frozen key
column and a visible scroll affordance" — if not, file that, which is a smaller and more accurate
finding.

**2. A fixed-min-width canvas, editor, or diagram.** A drag-and-drop page builder, a node graph, a
video timeline, a spreadsheet grid. These have an irreducible working area, and shrinking it does not
make them usable — it makes them useless in a different way (`teslers-law`). Correct behaviour is a
clear message at narrow widths ("Open on a larger screen to edit"), not a squeezed canvas. The
finding here is only ever about the *message*: is it present, does it say what width is needed, and
does it still let the user read or preview what they cannot edit. Filing "the editor is broken on
mobile" against a tool that never claimed to work there is noise.

**3. Content that genuinely requires a desktop.** Bulk multi-select across 500 rows, side-by-side
diffing, dense financial comparison. Before calling this a false finding, apply §4 rule 1: the
*primary action for the mobile task* must still exist. "You cannot bulk-edit 500 rows on a phone" is
acceptable. "You cannot see your invoice total on a phone" is not, whatever the desktop screen does.

The test that separates all three from real defects: **is the constraint stated to the user, or does
the screen just fail?** A stated constraint is a design decision you can disagree with. Silence is a
defect, and it is the defect worth filing.
