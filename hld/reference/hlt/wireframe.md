# ASCII wireframes

A copy-and-adapt component library. Take a block, change the words, keep the alignment.

## 1. Why ASCII

It diffs — a frame in a code block shows up in `git diff`, in a PR, in a ticket, and reviewers argue
with what is in front of them. It reviews in place with no account, plugin or export step, and it
survives a terminal, a chat window and a `grep` two years out. It costs seconds to draw and seconds
to redraw, so you show three options instead of defending one. And it is deliberately low fidelity:
nobody argues about the shade of a `─`, so the conversation stays on where things sit and how many
steps the task takes.

**The limit, stated honestly.** ASCII cannot express spacing rhythm, colour, type scale, weight,
motion, or true proportion. Column counts are not pixels. It is a structure tool only.

Failure behaviour: never use a wireframe to argue a visual point — "this feels cramped", "this needs
more contrast", "the heading is too small". Those need the real screen; take them to
[hierarchy.md](hierarchy.md). Say the limit out loud when you hand a frame over:

```
Structure only — no spacing, colour, type or motion implied. 78 cols = desktop
```

## 2. The character set and rules

```
core set     ─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼

█ ▓ ▒ ░      filled → muted → empty.  ▓ = primary, ░ = disabled / scrim
═ ║ ╔ ╗ ╚ ╝ ╒ ╕ ╘ ╛ ╟ ╢   the double-line family: focus rings, and anything
                          floating above the page (modal, drawer, popover)
▾ ▴ ◂ ▸      direction    ▹ current item    ▪ ▫ icon slot, on / off
● ○ ◉        selected · unselected · in progress
✓ ✗ ⚠ ℹ      success · error · warning · info
⌕ ··· ›      search · overflow menu · breadcrumb separator
→ · »        frame transition · inline separator · content runs off the edge
╱ ╲ ‾ _      line-chart segments: rising, falling, high plateau, low plateau
```

Failure behaviour for the extension set: these are single-width in every monospace font this skill
has been used with, but a terminal that renders `⌕`, `ℹ` or `▓` double-width shears every frame
containing one. Substitute across the **whole document** — `⌕`→`>`, `ℹ`→`i`, `▓`→`#`, `░`→`.` —
never in one frame, because a half-substituted document looks like two different products.

**Rule 1 — fixed-width font, always inside a fenced code block.** Markdown collapses runs of spaces
and proportional fonts destroy the grid; outside a fence the frame renders as a shredded paragraph
and the reviewer stops at line two. Use a bare fence — a language tag invites syntax highlighting
that recolours box characters into noise.

**Rule 2 — one canvas width per viewport, held for the whole document:** desktop **78** cols
(interior 76), tablet **56** (54), mobile **34** (32). 78 fits an 80-col terminal and a GitHub diff
without wrapping; 56 and 34 are the 1024/1440 and 390/1440 ratios. Reviewers compare screens by eye,
and two frames at different widths make identical layouts look different. Failure behaviour: if
content will not fit at 78, do **not** widen — cut the row at the edge, mark it `»`, and say in the
legend that the region scrolls sideways. Widening hides the exact problem worth reporting.

**Rule 3 — alignment is the product.** Every line of a frame is the same character count, every `│`
in the same column, corners at the ends. A sheared frame reads as carelessness and the reviewer
discounts the proposal with it. Failure behaviour: count the top rule against the bottom rule before
pasting; if you cannot hold 78, use a narrower frame rather than ship a sheared one. The rule is per
frame, not per line of the page — two frames may sit side by side at different heights, and captions
may hang off the right edge at any length.

**Rule 4 — label every whole-screen frame**, one header line above it:
`SCREEN /billing/invoices · 78 cols · [PROPOSED]`. A frame with no path is unreviewable; nobody can
tell what it replaces. `[PROPOSED]` and `[EXISTING]` are the only markers. A frame you did not
observe is `[UNOBSERVED]` and may not be stated as fact — see [walkthrough.md](walkthrough.md).

**Rule 5 — real content, never lorem.** `Acme Corp · $4,820.00 · Overdue 12d` tells the reviewer the
column is two characters short. `Lorem ipsum dolor sit` tells them nothing. Failure behaviour: if you
have no real data, copy three rows out of the screen you walked.

## 3. The component library

Components are drawn at their natural width, not the canvas width — they are parts. Only whole-screen
frames hold the canvas width.

### Buttons, toggles and choices

```
  primary            secondary          disabled
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│▓▓▓  Save  ▓▓▓│   │    Cancel    │   │░░░  Save  ░░░│
└──────────────┘   └──────────────┘   └──────────────┘
inline, for dense frames:  [▓ Save ▓]   [ Cancel ]   [░ Save ░]   [▓ Save ▓ ▾]

Notify me when          Billing period            Weekly digest  (──●)  on
[✓] a run fails         (●) Monthly  $12/user     Slack alerts   (○──)  off
[ ] a run finishes      ( ) Annual   $10/user     SSO required   (○──)░ locked
[–] a run is queued     ( ) Custom
[–] = mixed: some children ticked, some not
```

A disabled primary with no reason beside it is a dead end — the user's only move is to click and
watch nothing happen. A toggle applies immediately; if yours needs a Save button it is a checkbox.
Under about five options show radios rather than hiding them in a select.

### Fields

```
empty                                filled
┌────────────────────────────┐       ┌────────────────────────────┐
│ Work email                 │       │ ada@example.com            │
└────────────────────────────┘       └────────────────────────────┘
placeholder, not a value             a value

focused                              error
╒════════════════════════════╕       ┌────────────────────────────┐
│ ada@example.com█           │       │ ada@example                │
╘════════════════════════════╛       └────────────────────────────┘
█ is the caret                       ✗ Add the part after @, like
                                       ada@example.com
```

The error sits under its own field and names the fix, not the rule. "Invalid email" makes the user
guess; "Add the part after @" does not.

```
Notes                                    0 / 500  closed
┌────────────────────────────────────────────┐    ┌──────────────────────────┐
│ Renewal call moved to Thursday; ops needs  │    │ Ada Lovelace           ▾ │
│ the export before then.                    │    └──────────────────────────┘
│                                            │
└────────────────────────────────────────────┘    open
                                                  ┌──────────────────────────┐
┌────────────────────────────────────────────┐    │ Ada Lovelace           ▴ │
│ ⌕ Search by invoice number, customer or PO │    ├──────────────────────────┤
└────────────────────────────────────────────┘    │ ● Ada Lovelace           │
                                                  │ ○ Grace Hopper           │
┌────────────────────────────────────────────┐    │ ○ Katherine Johnson      │
│ ⌕ acme                                  ✗  │    │ ○ Unassigned             │
└────────────────────────────────────────────┘    └──────────────────────────┘
  12 of 412 invoices · Enter to see all
```

The search placeholder names what is searchable: without it the user guesses a field you do not
index, gets nothing, and concludes search is broken.

```
date range picker, open                          file dropzone, idle
┌────────────────────────────────────────────┐   ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
│ 1 Jul 2026  →  31 Jul 2026             ▴   │   │  Drop a CSV here, or      │
├───────────────┬────────────────────────────┤   │  [ choose a file ]        │
│ Today         │  ◂     July 2026        ▸  │   │  Up to 10 MB · header row │
│ Last 7 days   │  Mo Tu We Th Fr Sa Su      │   └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
│ Last 30 days  │         1  2  3  4  5      │
│ This month  ▹ │   6  7  8  9 10 11 12      │   uploading
│ Custom        │  13 14 15 16 17 18 19      │   ┌───────────────────────────┐
│               │  20 21 22 23 24 25 26      │   │ customers.csv  1.4 MB  ✗  │
│               │  27 28 29 30 31            │   │ ▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░  52%  │
├───────────────┴────────────────────────────┤   └───────────────────────────┘
│                 [ Cancel ]   [▓ Apply ▓]   │
└────────────────────────────────────────────┘
```

Presets left, calendar right: most range picks are a preset, and a preset is one click where a
calendar is two plus a decision. State upload limits before the upload, not in the error after it.

### Data table

```
┌────────────────────────────────────────────────────────────────────────────┐
│[✓] Invoice ▾   Customer         Status     Amount        Due        ···    │
├────────────────────────────────────────────────────────────────────────────┤
│[✓] INV-2041    Acme Corp        Overdue    $4,820.00     12d ago    ···    │
│[ ] INV-2040    Northwind Ltd    Sent       $1,150.00     in 4 days  ···    │
│[ ] INV-2039    Globex           Paid         $980.00     —          ···    │
└────────────────────────────────────────────────────────────────────────────┘
▾ = current sort key and direction.  ··· = per-row overflow menu.
Amounts are right-aligned so magnitudes compare without being read.

empty — keep the header, so the user can see what to change
┌────────────────────────────────────────────────────────────────────────────┐
│[ ] Invoice ▾   Customer         Status     Amount        Due        ···    │
├────────────────────────────────────────────────────────────────────────────┤
│                   No invoices match "acme" + Overdue                       │
│              Clear the status filter, or  [ Reset all filters ]            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Containers

```
card                                   accordion, collapsed
┌──────────────────────────────────┐   ┌─────────────────────────────────┐
│ (AC)  Acme Corp         [Overdue]│   │ ▸ Billing address     Complete  │
│       12 invoices · $48,200      │   ├─────────────────────────────────┤
│ Last payment   3 Aug 2026        │   │ ▸ Payment method      Complete  │
│ Owner          Ada Lovelace      │   ├─────────────────────────────────┤
├──────────────────────────────────┤   │ ▸ Tax details        3 missing  │
│ [ Open ]  [ Send reminder ]      │   └─────────────────────────────────┘
└──────────────────────────────────┘
                                       accordion, one section open
list rows                              ┌─────────────────────────────────┐
├──────────────────────────────────┤   │ ▸ Billing address     Complete  │
│ (AC) Acme — INV-2041   $4,820  ▸ │   ├─────────────────────────────────┤
├──────────────────────────────────┤   │ ▾ Payment method      Complete  │
│ (NW) Northwind — 2040  $1,150  ▸ │   │   ┌───────────────────────────┐ │
├──────────────────────────────────┤   │   │ •••• •••• •••• 4242       │ │
                                       │   └───────────────────────────┘ │
tabs                                   │   [▓ Update ▓]   [ Remove ]     │
┌──────────────────────────────────┐   ├─────────────────────────────────┤
│ Details │ Activity │ Docs (3)    │   │ ▸ Tax details        3 missing  │
│ ═══════                          │   └─────────────────────────────────┘
├──────────────────────────────────┤
│ the active tab's content         │
└──────────────────────────────────┘
```

A card's border is the grouping: everything inside reads as one object, which is why a card drawn
around unrelated fields is worse than no card (`law-of-common-region`). Keep the status on a
collapsed accordion header — hiding "3 missing" hides the reason to open it.

### Overlays

```
modal                                                     drawer
┌──────────────────────────────────────────────────────┐  ┌──────────────────┐
│░░░╔══════════════════════════════════════════╗░░░░░░░│  │░░░░░░░░░░╔══════╗│
│░░░║ Delete 3 invoices?                    ✗  ║░░░░░░░│  │░░░░░░░░░░║ INV- ║│
│░░░║ INV-2041, INV-2040, INV-2039 will be     ║░░░░░░░│  │░░░░░░░░░░╟──────╢│
│░░░║ removed. This cannot be undone.          ║░░░░░░░│  │░░░░░░░░░░║ Acme ║│
│░░░║                  [ Cancel ]  [▓ Delete ▓]║░░░░░░░│  │░░░░░░░░░░║ …    ║│
│░░░╚══════════════════════════════════════════╝░░░░░░░│  │░░░░░░░░░░╚══════╝│
└──────────────────────────────────────────────────────┘  └──────────────────┘
```

`░` is the scrim over the page behind, and it is drawn so the reviewer can see how much of the page
the overlay eats. The modal title asks the question its primary button answers. Prefer a drawer, as
sketched at the right, when the user needs the list behind it to stay exactly where it was — draw it
full size when it is the thing under discussion.

### Alerts and toasts — four severities

```
┌────────────────────────────────────────────────────────────────┐
│ ✓  3 invoices sent.                                  [ Undo ]  │
├────────────────────────────────────────────────────────────────┤
│ ℹ  Exports run nightly. Yours is queued for 02:00 UTC.         │
├────────────────────────────────────────────────────────────────┤
│ ⚠  2 of 3 invoices have no billing email.       [ Fix these ]  │
├────────────────────────────────────────────────────────────────┤
│ ✗  Send failed — the provider rejected the token.              │
│    Nothing was charged.                             [ Retry ]  │
└────────────────────────────────────────────────────────────────┘
```

Severity rides on the glyph and the words, never colour alone — the wireframe has no colour, and
neither does a colour-blind user. Every failure alert also states the resulting system state
("Nothing was charged"): that is the question the user actually has.

### Chrome — bars, nav, breadcrumb, pagination, badges

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ▓ Acme    Billing › Invoices      ⌕ Search…      ⚠3    (AL) Ada L. ▾       │
└────────────────────────────────────────────────────────────────────────────┘

sidebar, expanded        collapsed rail       mobile bottom bar, 34 cols
┌────────────────┐       ┌───┐ logo         ├────────────────────────────────┤
│ ▓ Acme         │       │ ▓ │              │   ▫       ▪       ▫       ▫    │
├────────────────┤       ├───┤ Home         │  Home  Invoices  Cust.   More  │
│   Home         │       │ ▫ │              └────────────────────────────────┘
│ ▹ Invoices     │       │ ▪ │ active
│   Customers    │       │ ▫ │               Billing › Invoices › INV-2041
│   Reports      │       │ ▫ │
├────────────────┤       ├───┤               ◂ Prev  1 2 [3] 4 5 … 17  Next ▸
│   Settings     │       │ ▫ │ Settings      Rows [ 25 ▾ ] · 412 total
│ (AL) Ada L.    │       │ AL│
└────────────────┘       └───┘               (AL)              avatar
                                             (AL)(GH)(KJ)+4   stack + overflow
                                             [Overdue]         status badge
                                             Invoices ( 12 )   count badge
```

The collapsed rail keeps every destination. Collapsing is not hiding: dropping items into a `···`
menu changes what people can find, and the wireframe must show that difference.

### Progress, skeleton, empty state

```
Uploading 3 of 8 files                  ●────────●────────◉────────○────────○
▓▓▓▓▓▓▓▓▓▓▓▒░░░░░░░░░░░░░░░░░░░░  37%   Account  Company  Billing  Team Invite
                                        done     done     current  ahead ahead
indeterminate — no percentage, because
a fake one is worse than none
░░░░▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░

skeleton                                 empty state
┌──────────────────────────────────┐     ┌──────────────────────────────────┐
│ ░░░░░░░░░░░░░░                   │     │          No invoices yet         │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░       │     │   Invoices appear here once you  │
│                                  │     │   send one, or import your old   │
│ ░░░░░░  ░░░░░░░░░░  ░░░░  ░░░░░░ │     │   system's.                      │
│ ░░░░░░  ░░░░░░░░░░  ░░░░  ░░░░░░ │     │ [▓ Create invoice ▓] [ Import ]  │
└──────────────────────────────────┘     └──────────────────────────────────┘
```

Draw the skeleton in the shape of the content that lands; one whose shape does not match is a second
layout the user has to re-read. An empty state has three parts, always — what is missing, why, and
the one action that fixes it. Without the action it is a dead end with padding.

### Chart placeholders

```
bar                                  line
┌──────────────────────────────┐     ┌──────────────────────────────┐
│ Revenue by month       ▾ 6m  │     │ Open invoices         ▾ 90d  │
│ 40┤       ▓                  │     │ 40┤         ╱‾╲    ╱‾‾       │
│ 20┤ ▓  ▓  ▓     ▓            │     │ 20┤  __╱‾‾‾╱   ╲__╱          │
│  0┼──┬──┬──┬──┬──┬──         │     │  0┼──┬──┬──┬──┬──┬──         │
│    J  F  M  A  M  J          │     │    J  F  M  A  M  J          │
└──────────────────────────────┘     └──────────────────────────────┘

donut / pie — do not draw the arc     An ASCII arc reads as noise. Draw the
┌──────────────────────────────┐      container and the legend; the legend is
│ Status mix                   │      the part a reviewer can argue with.
│  ( donut  )    ▓ Paid    62% │
│  ( 3 parts)    ▒ Sent    24% │
│                ░ Overdue 14% │
└──────────────────────────────┘
```

## 4. Annotation convention

Four devices. Use one at a time: a frame carrying callouts *and* a notes column *and* markers is
harder to read than the screen it describes.

**Numbered callouts.** `(1)`…`(9)` inside the frame at the thing, numbered in reading order so the
legend runs in the order the eye moves. Legend directly beneath, one entry per number, two lines
maximum, each ending `[PROPOSED]` or `[EXISTING]` — without that marker reviewers argue about things
you were not proposing. Failure behaviour: past nine callouts the frame is doing too much; split it,
or move the detail into findings ([critique.md](critique.md)).

```
SCREEN /billing/invoices · 78 cols · [PROPOSED]
┌────────────────────────────────────────────────────────────────────────────┐
│ Invoices                                     (1) [ Import ]  [▓ New ▓]     │
│ (2) ⌕ acme       [ Overdue ▾ ]  [ Owner ▾ ]  [ Jul 2026 ▾ ]  [ Clear all ] │
├────────────────────────────────────────────────────────────────────────────┤
│ (3) 2 selected   [ Send reminder ]   [ Export ]   [ Void ]                 │
├────────────────────────────────────────────────────────────────────────────┤
│     [✓] INV-2041   Acme Corp      Overdue   $4,820.00   12d ago     ···    │
└────────────────────────────────────────────────────────────────────────────┘

(1) Primary action stays top-right, as on every list page. Template-level:
    moving it moves it on eleven screens. [EXISTING]
(2) Search and filters merged into one row. Today they are two, which pushes
    the first data row below the fold at 768px height. [PROPOSED]
(3) Bulk bar appears only while a selection exists, replacing the filter row
    rather than pushing the table down. [PROPOSED]
```

**Notes column.** For a frame narrower than the canvas, park notes to the right at a fixed column.
Use it when the notes explain why a default is the default — tedious as numbered callouts.

```
┌──────────────────────────────┐   pre-selected: the plan they already have.
│ Plan                         │   Changing plan is rarer than changing seats.
│ (●) Team      $12 /user /mo  │
│ ( ) Business  $28 /user /mo  │   seats default to today's count, so the
│ Seats  ┌──────┐              │   common case is zero edits.
│        │ 12   │              │
└────────┴──────┴──────────────┘
```

**Before → after.** Two frames stacked, the transition on its own line, labelled with the action in
the user's verb — "click the row checkbox", never "onSelectionChange fires". Failure behaviour: if
you have not observed the after-state, mark that frame `[UNOBSERVED]` and do not assert it.

```
[EXISTING]  nothing selected            [PROPOSED]  a selection exists
┌────────────────────────────────────┐  ┌────────────────────────────────────┐
│ [ ] INV-2041   Acme Corp   Overdue │  │ [✓] INV-2041   Acme Corp   Overdue │
│ [ ] INV-2040   Northwind   Sent    │  │ [ ] INV-2040   Northwind   Sent    │
└────────────────────────────────────┘  ├────────────────────────────────────┤
                                        │ 1 selected  [ Remind ]  [ Void ]   │
        →  click the row checkbox       └────────────────────────────────────┘
```

## 5. Showing three widths

Stack them widest first, each with its own header and canvas width, then one block naming what moved
and why. Never show only mobile — the reviewer cannot tell what was dropped; never show only desktop
— a layout that works at 1440px and nowhere else is unfinished. The rules for what may collapse,
reflow or be dropped are in [responsive.md](responsive.md); this file shows only the result.

```
DESKTOP · 78 cols · [PROPOSED]
┌────────────────────────────────────────────────────────────────────────────┐
│ ▓ Acme   Billing › Invoices › INV-2041    ⌕ Search      (AL) Ada L. ▾      │
├──────────────┬─────────────────────────────────────────────────────────────┤
│   Home       │ INV-2041                    [ Void ]  [▓ Send reminder ▓]   │
│ ▹ Invoices   │ Acme Corp · $4,820.00 · Overdue 12 days                     │
│   Customers  │                                                             │
│   Reports    │  Details │ Activity │ Documents (3)                         │
│   Settings   │  ═══════                                                    │
│              │  Design retainer                             $3,200.00      │
│              │  Hosting, Jul 2026                           $1,200.00      │
│              │  Tax (VAT 20%)                                 $420.00      │
│              │  ─────────────────────────────────────────────────────      │
│              │  Total                                       $4,820.00      │
│              │  Due 28 Jul 2026 · Sent to ap@acme.example · PO 44-901      │
└──────────────┴─────────────────────────────────────────────────────────────┘
```

```
TABLET · 56 cols · [PROPOSED]
┌──────────────────────────────────────────────────────┐
│ ▓  Billing › Invoices › INV-2041     ⌕    (AL) ▾     │
├───┬──────────────────────────────────────────────────┤
│ ▫ │ INV-2041                                         │
│ ▪ │ Acme Corp · $4,820.00 · Overdue 12 days          │
│ ▫ │ [ Void ]         [▓ Send reminder ▓]             │
│ ▫ │  Details │ Activity │ Documents (3)              │
│ ▫ │  ═══════                                         │
│   │  Design retainer                    $3,200.00    │
│   │  Hosting, Jul 2026                  $1,200.00    │
│   │  Tax (VAT 20%)                        $420.00    │
│   │  ────────────────────────────────────────────    │
│   │  Total                              $4,820.00    │
│   │  Due 28 Jul · ap@acme.example · PO 44-901        │
└───┴──────────────────────────────────────────────────┘
```

```
MOBILE · 34 cols · [PROPOSED]
┌────────────────────────────────┐
│ ◂ Invoices           (AL) ▾    │
├────────────────────────────────┤
│ INV-2041                       │
│ Acme Corp                      │
│ $4,820.00 · Overdue 12d        │
│ Details │ Activity │ Docs (3)  │
│ ═══════                        │
│ Design retainer     $3,200.00  │
│ Hosting, Jul 2026   $1,200.00  │
│ Tax (VAT 20%)         $420.00  │
│ ────────────────────────────── │
│ Total               $4,820.00  │
│ Due 28 Jul · PO 44-901         │
│ ap@acme.example                │
├────────────────────────────────┤
│ [▓ Send reminder ▓]  [ Void ]  │
└────────────────────────────────┘
```

What moved, and why:

- **Sidebar** — 5 labelled items → 5-slot icon rail → gone, replaced by `◂ Invoices`. Nothing is
  dropped: the back link returns to the list they came from, and navigation is not the task here.
- **Actions** — inline top-right → under the summary → pinned to the bottom of the viewport, so the
  primary stays reachable without scrolling and sits in the thumb arc (`fitts-law`).
- **Summary** — one line at 78 and 56, three lines at 34: it wraps rather than truncating, because
  `$4,820.00 · Overdue 12…` hides the number the user opened the screen for.
- **Tabs** — all three survive at 34 by shortening "Documents" to "Docs", not by folding into a `▾`.
  A tab behind a menu is a tab nobody visits.
- **Line items** — identical at every width, amounts still right-aligned. This is the content; if it
  does not fit, the width is wrong, not the content.

## 6. Two complete worked screens

### A — data table with filters and bulk actions

```
SCREEN /billing/invoices · 78 cols · [PROPOSED]
┌────────────────────────────────────────────────────────────────────────────┐
│ ▓ Acme    Billing › Invoices               ⌕ Search      (AL) Ada L. ▾     │
├──────────────┬─────────────────────────────────────────────────────────────┤
│   Home       │ Invoices               (1) [ Import ]  [▓ New invoice ▓]    │
│ ▹ Invoices   │ (2) ⌕ acme   [ Overdue ▾ ] [ Any owner ▾ ] [ Jul 2026 ▾ ]   │
│   Customers  │     3 filters · 12 of 412 invoices            [ Clear all ] │
│   Reports    │                                                             │
│   Settings   │ (3) 2 selected   [ Send reminder ]  [ Export ]  [ Void ]    │
│              │ ┌─────────────────────────────────────────────────────────┐ │
│              │ │[✓] Invoice ▾  Customer     Status       Amount Due   ···│ │
│              │ ├─────────────────────────────────────────────────────────┤ │
│              │ │[✓] INV-2041   Acme Corp    Overdue   $4,820.00 12d   ···│ │
│              │ │[✓] INV-2040   Acme Supply  Overdue   $1,150.00 4d    ···│ │
│              │ │[ ] INV-2039   Acme Labs    Sent        $980.00 in 6d ···│ │
│              │ │[ ] INV-2038   Acme Labs    Paid        $412.00 —     ···│ │
│              │ └─────────────────────────────────────────────────────────┘ │
│              │ (4) ◂ Prev 1 [2] 3 … 17  Next ▸  Rows [ 25 ▾ ] · 412 total  │
└──────────────┴─────────────────────────────────────────────────────────────┘

(1) Import sits beside New because both create invoices; everything else here
    only reads them. [EXISTING]
(2) One filter row with a live result count under it. The count is what stops
    the user re-running the filter to check it worked. [PROPOSED]
(3) Bulk bar occupies the row above the table only while a selection exists.
    It replaces and pushes nothing — the table does not jump. [PROPOSED]
(4) Row count and total sit beside the pager, so "412 total" answers "did my
    filter do anything" without scrolling back up. [EXISTING]

Scope: page-level. The bulk-bar pattern becomes template-level the moment you
apply it to Customers and Reports — say which you mean before proposing it.
```

A wireframe is the `proposal` line of a finding, never a substitute for one. Write the finding in the
format from [critique.md](critique.md), with its screenshot, cost and principle, and let `proposal`
read `see wireframe §6A callout (3)`. A frame handed over on its own carries no evidence that the
problem exists.

### B — multi-step form

```
SCREEN /onboarding/billing · 78 cols · [PROPOSED]
┌────────────────────────────────────────────────────────────────────────────┐
│ ▓ Acme                                                    Save and exit  ✗ │
├────────────────────────────────────────────────────────────────────────────┤
│ (1) ●─────────────●─────────────◉─────────────○─────────────○              │
│     Account       Company       Billing       Team          Invite         │
│     Step 3 of 5 · about 2 minutes left                                     │
│                                                                            │
│ (2) Where should invoices go?                                              │
│     You can change any of this later in Settings › Billing.                │
│                                                                            │
│     Billing email                        (3) Purchase order number         │
│     ┌──────────────────────────────┐         ┌──────────────────────────┐  │
│     │ ap@acme.example              │         │                          │  │
│     └──────────────────────────────┘         └──────────────────────────┘  │
│     Copied from your account.                Optional — blank if your      │
│                                              finance team has no PO        │
│                                                                            │
│ (4) [✓] Same as the company address from step 2                            │
│         12 Kingsway, London WC2B 6LH, UK       [ Use another address ]     │
├────────────────────────────────────────────────────────────────────────────┤
│ (5) [ ◂ Back ]                                Skip for now  [▓ Continue ▓] │
└────────────────────────────────────────────────────────────────────────────┘

(1) Rail and count together: the rail alone gives no number, the number alone
    no shape. See `goal-gradient` in principles.csv — run
    `python3 scripts/why.py --name goal-gradient` and cite the grade it
    returns, not this sentence. [PROPOSED]
(2) The heading is the question the user is answering, in their words, not the
    schema's group name ("Billing entity configuration"). [PROPOSED]
(3) "Optional" is written on the optional field: marking the minority is less
    to scan. Failure case — if most fields here were optional, invert it and
    mark the required ones. Mark whichever set is smaller. [PROPOSED]
(4) Ticked by default, and it shows what it filled in: four address fields
    collapse to one line the user can read and accept. Unticking expands them
    in place, so nothing below jumps further than that block. [PROPOSED]
(5) One primary. "Skip for now" is text, not a button — three same-weight
    buttons make the user choose between three things, not one. [PROPOSED]
```

Do not draw this footer:

```
├────────────────────────────────────────────────────────────────────────────┤
│ [ ◂ Back ]                          [ Skip ]  [ Save ]  [░ Continue ░]     │
└────────────────────────────────────────────────────────────────────────────┘
Continue is disabled with nothing beside it saying why, so the user's only
move is to click it and watch nothing happen. If a primary is disabled, the
frame must carry the sentence that unlocks it.
```

## 7. When to reach for mermaid instead

Wireframes show where things sit on one screen. Mermaid shows what leads to what across screens.

| You want to show | Use |
|---|---|
| Where elements sit on one screen | ASCII wireframe — this file |
| Two states of one screen and the click between | ASCII pair with a labelled `→` — §4 |
| What happens after a click, across screens | mermaid flowchart → [mindmap.md](mindmap.md) |
| The states a thing can be in, and the events | mermaid stateDiagram → [mindmap.md](mindmap.md) |
| The parts a feature is made of | mermaid mindmap → [mindmap.md](mindmap.md) |

Two cheap tests. **More arrows than boxes?** You are drawing a flow, not a layout — switch to
mermaid. **Mermaid nodes named "the filter bar", "the table header"?** You are drawing a layout in
the wrong tool — switch back to ASCII. Never draw a state machine in ASCII boxes: box art cannot
branch without moving boxes around, and a reviewer reads position as layout, so every branch becomes
a layout claim you did not mean to make.

---

**Where the principles come from.** Cite by `principles.csv` id and confirm the evidence grade with
`python3 scripts/why.py --name <id>` before stating it. The underlying research:

- `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/02-interaction-and-system-response.md#1-fittss-law`
- `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/03-gestalt-and-perception.md#4-law-of-common-region`
- `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/01-cognitive-load-and-memory.md#6-serial-position-effect`
