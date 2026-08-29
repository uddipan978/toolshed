# Walkthrough — driving the UI as a person

This is the spine of the skill. `review`, `fit` and `map` all consume what this file produces. If
the walkthrough did not happen, they have nothing to run on and must not be faked from source.

The failure this file exists to prevent, stated plainly: an agent asked "does this flow make sense"
reads the route handler, the API response and the component tree, then writes a confident report
about a screen it never rendered. That report is wrong in a specific and expensive way — it
describes the intent, and the user is complaining about the experience.

---

## 1. The doctrine

**Observe, do not inspect. Source tells you what was intended; the running UI tells you what
happens.**

The reason: every layer between the intent and the pixels can lose or add something. A flow can be
correct in code and unusable on screen.

Things that are invisible in a code read and obvious in three seconds of looking:

- A label that wraps and now sits under the wrong field.
- A spinner that never resolves because the request 200s with an empty array and the empty state
  was never written.
- A primary button that is disabled with no explanation of what would enable it.
- A validation error rendered at the top of a form the user has already scrolled past.
- Two "Save" buttons, one of which is the browser's autofill artefact.
- Text at 11px on a grey card that passes the contrast check in the token file and fails on screen
  because a parent sets 60% opacity.
- A modal that opens behind the header at 1280px.

None of those appear in the component source. All of them are the thing the user is asking about.

**Failure behaviour:** if you cannot render the surface, you have not observed it, and §9 applies.
You do not get to substitute a careful code read. It is not 80% of a walkthrough; it is a different
activity that answers a different question.

**Why you specifically must fight this rule:** you read code faster than you drive a browser, and
the code read feels productive. It produces fluent, plausible, unfalsifiable prose. Driving the UI
produces screenshots, which can be checked. Prefer the checkable output.

---

## 2. What counts as observed, and what does not

| OBSERVED — may be stated as fact | NOT OBSERVED — may not |
|---|---|
| A screenshot **plus the action that produced it** | The API response body |
| A `read_page` accessibility tree of the rendered surface | A database row or a SQL query result |
| A console error captured while the surface was live | A fixture, seed file, or factory |
| A network request captured while you drove the flow | The component source, the route handler, the CSS |
| A visible wait you sat through and timed | A test file, snapshot, or Storybook story |
| The URL bar after a navigation you performed | A Figma mock or a design doc |
| A rendered empty/error/loading state you triggered | Your memory of a similar app, or of this app last week |

Two boundaries that get crossed most often:

**An accessibility-tree read is observation of structure, not of appearance.** `read_page` gives you
roles, labels, headings, order, disabled state, ref handles. That is enough to say "the submit
button is disabled" or "there are three headings and the second is an `h4` under an `h2`". It is
**not** enough to say anything about hierarchy, spacing, alignment, colour, contrast, density, or
"this screen feels cluttered". Those claims need a screenshot. Making them from the tree alone is
the same defect as making them from source, one layer up.

**A screenshot without its action is half-evidence.** "Screenshot 06 shows an error" is not usable;
"clicked Export with the date range empty → screenshot 06 shows the error" is. The action is what
makes the finding reproducible, and reproducibility is the whole reason the screenshot is there.

Anything you believe but did not observe is written `[UNOBSERVED]` (§8). That is not a weaker
finding — it is a different kind of statement, and mixing the two is what destroys the report's
credibility.

---

## 3. When backend reads ARE allowed

Exactly one case: **explaining a defect you have already observed in the UI.**

Observation comes first and gives you the symptom. The backend read comes second and gives you the
cause. Reversing the order — reading the endpoint to learn what the screen *would* show, instead of
loading the screen — is the banned move, because it answers a question nobody asked and skips the
one they did.

**Allowed — diagnosis after observation:**

> Step 5: navigated to `/billing/invoices`. Screenshot 05 shows the table header, the column
> labels, and no rows — no empty-state copy, no "0 results", just whitespace under the header.
> That is the finding. To say *why*, I opened `read_network_requests` and found
> `GET /api/invoices?status=all` returning `200 []`. So the list is genuinely empty and the empty
> state is missing, rather than the request failing silently.
>
> The finding is "the empty list renders as blank whitespace with no explanation." The backend read
> only distinguished "missing empty state" from "swallowed 500", which changes the fix.

**Banned — inspection instead of observation:**

> `GET /api/invoices` returns 24 invoices with `id`, `number`, `amount`, `dueDate` and `status`, so
> the invoice table shows 24 rows across five columns and the user can sort by due date.

Everything after "so" is invented. The table may paginate at 10. `status` may not be rendered.
Sorting may not exist. The rows may render and be unreadable at 1280px. This paragraph is
indistinguishable from a real observation in tone and completely different in truth value — which
is exactly why the rule is absolute rather than a matter of judgement.

**Failure behaviour:** if you find yourself reaching for the endpoint before you have a screenshot
of the surface it feeds, stop and load the surface. If the surface will not load, §9.

---

## 4. Setting up the drive

Use the Browser pane tools. **Dev servers are started with `preview_start`, never with Bash** — a
Bash-launched server is detached from the pane, so `navigate` has nothing to drive and you will
spend ten minutes discovering that.

| Tool | Use it for |
|---|---|
| `preview_start` | `{name}` — start a dev server by its entry in `.claude/launch.json`. `{url}` — open a browser tab on an already-running or deployed surface, no server needed. |
| `navigate` | Load a URL, or `"back"` / `"forward"`. |
| `read_page` | Accessibility tree of the rendered surface. Returns `ref_N` handles. Your primary way to find things. |
| `find` | Search the last `read_page` tree by description. Returns `ref_N`. Call `read_page` first. |
| `computer` | `screenshot`, `left_click`, `type`, `key`, `scroll`, `hover`, `double_click`, `left_click_drag`, `scroll_to`, `zoom`, `wait`. |
| `form_input` | Set an input/select/checkbox/textarea value by `ref`. More reliable than click-then-type for selects. |
| `resize_window` | `preset: mobile \| tablet \| desktop`, or explicit width/height. Also switches `colorScheme`. Reload after switching — load-time device gates do not re-run on resize. |
| `read_console_messages` | Errors and warnings thrown while you were on the page. |
| `preview_logs` | Server stdout/stderr — build errors, 500 traces. |
| `read_network_requests` | Requests made while you drove. Diagnosis only (§3). |

Opening sequence for a local app:

1. `preview_start {name: "<entry from .claude/launch.json>"}`. If no config exists, write one — the
   format is in the `preview_start` description — or ask the user for the dev command and port.
2. `resize_window {preset: "desktop"}` so every screenshot in the run shares a viewport. Findings
   about layout are meaningless if the width moved between captures.
3. `navigate` to the entry point a real user would arrive at — the app root or the login screen,
   not the deep link to the screen under review. How they get there is part of what you are
   measuring.
4. `computer {action: "screenshot"}` before you touch anything. This is capture `01`.
5. `read_page` to get `ref_N` handles for what is actually on screen.

### Two traps, both of which have already produced false bug reports

**Trap 1 — `computer` coordinates are SCREENSHOT PIXELS, not CSS pixels.**
Passing `getBoundingClientRect()` values, or any coordinate you computed in the page, clicks
somewhere else — often off-screen. The click silently does nothing, and you write "the Export
button does nothing when clicked", which is a fabricated high-severity finding that costs a
developer an afternoon.

Prefer `ref` handles from `read_page` / `find` over coordinates, always. Use coordinates only for
things with no accessible node — a canvas, a chart region, a drag inside a custom surface — and
when you do, take them off a fresh `screenshot`, not off the DOM. If a click appears to do nothing,
your first hypothesis is that you missed the element, not that the button is broken. Verify with a
`screenshot` showing hover or focus state before you write anything down.

**Trap 2 — the key name `"Return"` dispatches no keydown at all.**
Use `"Enter"`. `"Return"` is silently accepted and does nothing. This has already produced one bug
report claiming "the field never commits its value", which was entirely the tool call. If a field
does not commit, retry with `"Enter"`, and only then with a click on the submit control, before you
record anything.

General rule behind both: **when the UI appears not to respond, suspect your input before you
suspect the app.** Confirm the failure a second way. A false negative here is worse than a missed
finding, because it is confidently wrong and it is the kind of claim people act on.

---

## 5. The persona

Adopt one before the first click, and write it into the report. Four fields, one line each:

```
Persona   Priya, accounts assistant at a 30-person firm
Goal      export last month's invoices to send to the bookkeeper
Time      5 minutes between calls, this is an interruption
Knows     has used the app twice; knows there is a Billing section; has never opened Settings
```

Why it is mandatory: without a persona you unconsciously play yourself — an operator with the
source tree open, infinite patience and no other job. That user does not exist, and every finding
calibrated against them is calibrated wrong. The persona fixes what counts as "obvious", what
counts as "too slow", and what counts as "they'd just look it up". Two different personas produce
two different, both-correct reports on the same screen. See
[audience.md](audience.md) for choosing between a technical and a non-technical persona and for
how long each will sit on a screen before giving up.

Then behave like them:

- **No keyboard shortcuts a first-run user would not know.** No `Cmd+K` palette unless the persona
  has seen it, and if you use it, note that you did.
- **No typing URLs a real user would reach by clicking.** If you jump to `/billing/invoices/export`
  directly, you have skipped the navigation, which is usually where the cost is. Deep-link only to
  re-enter a flow you have already walked, and say so in the ledger.
- **No skipping the empty state by seeding data.** First-run is a real state with real users in it,
  and it is the state most often left unfinished.
- **No using your knowledge of the codebase to know where to click.** Covered in §6; it is the most
  common way a walkthrough quietly becomes an inspection.

**Failure behaviour — when you must seed:** if the flow genuinely cannot proceed without data (an
export with nothing to export), seed it, then write in the report: *"Seeded 3 invoices via <how>.
I did not observe the true first-run experience of this screen; the empty state is
`[UNOBSERVED]`."* Naming the gap costs one line and keeps the rest of the report trustworthy.

---

## 6. The drive itself

1. **State the goal in one sentence, as the persona would say it.** "Get last month's invoices out
   as a file I can email." Not "exercise the export flow." The persona's phrasing is what you
   measure against — if the UI's words and theirs never meet, that is a finding.
2. **Screenshot the entry point before acting.** Capture `01`. You cannot reconstruct a first
   impression after you have clicked.
3. **Take the most obvious next action, not the correct one.** Click what a person scanning for
   three seconds would click. If that is wrong, that is the finding — record the wrong turn, do not
   quietly correct it. Users do not read documentation; they start pushing buttons and absorb the
   errors (`paradox-of-the-active-user`, `evidence_grade` per `principles.csv`;
   `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/05-decision-making-and-simplicity.md`).
   Your walkthrough must reproduce that, not improve on it.
4. **Record every step in the ledger as you go** (§7). Not afterwards from memory — elapsed times
   and the order of small surprises are exactly what memory loses.
5. **Screenshot after every state change.** Navigation, modal open, validation error, list refresh,
   toast, disabled→enabled. A state change with no capture is a gap you cannot fill later without
   re-walking.
6. **When you hesitate, WRITE DOWN WHY. This is the single most valuable signal in the exercise.**
   Your hesitation is the user's confusion, sampled directly. "Paused ~4s deciding whether 'Export'
   meant the whole table or my current filter" is worth more than any amount of heuristic review,
   because it is a real moment of ambiguity caught in the act. Do not resolve the hesitation and
   then omit it — by the time you know the answer it feels obvious, and that feeling is the bug
   erasing its own evidence.
7. **Attempt one realistic mistake, then try to recover.** Pick the mistake this persona would
   actually make — wrong date range, wrong customer, submitting empty, closing the modal mid-way.
   Then measure recovery: is the error message next to the cause? Is the input preserved? How many
   steps back to good? Recovery is a full component of the Human Cost Score and it is almost never
   designed, only inherited.
8. **Time every wait over ~400ms.** Above that the user's attention leaves the task
   (`doherty-threshold`;
   `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/02-interaction-and-system-response.md`).
   Note whether anything on screen acknowledged the wait.
9. **Reach the goal, or record exactly where you stalled.** A stall is a result, not a failure of
   the walkthrough. Write the last thing you tried and what you expected instead.

**The hard rule inside the drive:** do not use your knowledge of the codebase to know where to
click. If you needed to read source to find the control, a user cannot find it either — and *that
is the finding*, probably the highest-severity one on the page. The moment you grep for the route
to locate a button, you have destroyed the measurement you came to take.

**Failure behaviour when genuinely stuck:** exhaust what the persona would do — scan the page, open
the obvious menu, try search, look in Settings — then stop and record it as a stall with the
elapsed time. Only after the ledger records the stall may you look at source to find the control,
and if you then continue the walk, mark every subsequent step `(post-hint)` in the notes column.
Those steps are still useful for the rest of the flow; they are not evidence about discoverability.

---

## 7. The evidence ledger

The artefact this file produces. One row per step, written as you go. It is the input to
[effort-ledger.md](effort-ledger.md), which turns it into the Human Cost Score.

Columns, exactly:

`step` · `screen/route` · `action` · `what appeared` · `shot` · `elapsed` · `notes`

- **action** — what the persona did, in their words. "clicked Export", not
  "dispatched click on `ref_14`".
- **what appeared** — what changed on screen. If nothing changed, write "nothing" — that is a row,
  and often the important one.
- **shot** — the capture number. Every screenshot is numbered in capture order and never
  renumbered, because findings, the ledger and the report all reference these numbers and
  renumbering silently breaks all three. Filename: `NN-short-slug.png` — `04-export-modal.png`,
  `07-date-range-error.png`. Two digits, lowercase, hyphens.
- **elapsed** — wall time for the step, including any wait. Rough is fine; ">400ms" and "~3s" are
  both usable. Precision matters less than not omitting it.
- **notes** — hesitations, surprises, wrong turns, anything you had to guess.

### Filled example — "export last month's invoices"

| step | screen/route | action | what appeared | shot | elapsed | notes |
|---|---|---|---|---|---|---|
| 1 | `/` dashboard | landed after login | 6 KPI cards, left nav with 9 items | 01 | — | No "Invoices" in nav. Scanned ~5s before spotting "Billing". |
| 2 | `/` dashboard | clicked "Billing" | Sub-nav expanded: Overview, Invoices, Payments, Plans | 02 | 0.2s | Guessed. "Billing" reads like plan settings, not documents. |
| 3 | `/billing/invoices` | clicked "Invoices" | Table, 24 rows, 5 columns, spinner first | 03 | 1.8s | Spinner 1.8s, no skeleton, header jumped when rows landed. |
| 4 | `/billing/invoices` | looked for export | Toolbar: search, "Filter", "New invoice", "⋯" | 03 | ~6s | Hesitated. Export not visible; tried "⋯" on a hunch. |
| 5 | `/billing/invoices` | clicked "⋯" | Menu: Import, Export, Column settings, Archive | 04 | 0.1s | Export is 2nd of 4 in an unlabelled overflow menu. |
| 6 | modal `Export invoices` | clicked "Export" | Modal: format select, date range (2 inputs), 3 checkboxes, Cancel/Export | 05 | 0.3s | Date range blank. No default, no "last month" preset. |
| 7 | modal `Export invoices` | clicked "Export" with dates blank | Modal stayed open, red text under the *first* date input only | 06 | 0.2s | Realistic mistake. Error says "Required" — not which field, not what format. |
| 8 | modal `Export invoices` | typed both dates, clicked "Export" | Button → spinner → modal closed, file downloaded, no toast | 07 | 3.4s | 3.4s with no progress text. Nothing on the page confirms it worked. |

Eight rows, one goal, and the report can now say what it costs instead of how it feels. Hand this
table to [effort-ledger.md](effort-ledger.md) for the Human Cost Score — do not compute the score
here.

---

## 8. Findings from the drive

Use the contract's finding format, unchanged. Severity is exactly one of
`blocker | high | medium | low | nit`. Scope is exactly one of `global | template-level |
page-level`.

```
F-07  [high]  scope: page-level   axis: effort
  screen    /billing/invoices
  observed  screenshot 04 → 05
  action    clicked "Export", filled date range, submitted
  cost      6 clicks · 2 waits >400ms · 1 backtrack
  principle hicks-law [replicated] · conflicts: pareto-principle
  problem   <one sentence, what the human experiences>
  proposal  <imperative. what to change.>
  build     S | M | L   <and what it touches>
```

Resolve the principle and its evidence grade with `python3 scripts/why.py --symptom "<what you
observed>"` — never from memory. A principle graded `contested` or `null-result` is stated with
that grade attached or not stated at all.

### An observed finding

```
F-03  [high]  scope: page-level   axis: effort
  screen    /billing/invoices
  observed  screenshot 03 → 04 → 05
  action    scanned toolbar ~6s, found no Export, opened the "⋯" overflow, clicked Export
  cost      2 clicks + ~6s search · 1 wrong-turn hesitation · 0 backtracks
  principle fitts-law [replicated] · conflicts: pareto-principle
  problem   Export is the reason this persona opened the page, and it is hidden behind an
            unlabelled overflow menu next to three lower-value actions.
  proposal  Promote Export to a visible secondary button in the toolbar, left of "New invoice".
            Leave Import and Column settings in the overflow.
  build     S · one toolbar component; no data or route changes.
```

### An unobserved finding

```
F-09  [UNOBSERVED]  scope: page-level   axis: responsiveness
  screen    /billing/invoices — export modal
  observed  not observed
  action    none — modal was only opened at 1280×800
  cost      unknown
  principle —
  problem   The modal packs a select, two date inputs and three checkboxes into a single row
            group. At 375px this either reflows to a long scroll or clips the Export button
            below the fold. Which of those happens determines whether the flow works on a
            phone at all.
  proposal  Re-open the modal at 375px and capture it before deciding. If the button falls
            below the fold, pin the modal footer.
  build     unknown until observed
```

**The `[UNOBSERVED]` entry is not padding, and it carries no severity.** It does two things nothing
else does: it tells the user precisely what still needs checking and why you could not check it,
and it stops you smuggling a guess in among the evidence. A report of six observed findings and two
honest gaps is more useful than eight findings of unmarked mixed provenance, because the reader can
act on the first and can only re-verify the second.

Write one `[UNOBSERVED]` entry per real gap. Do not manufacture them to look thorough, and do not
use one to dodge a check you could have run in thirty seconds — if `resize_window` was one call
away, make the call.

---

## 9. When it will not run

**An unwalked surface is a blocked task, not a degraded one.**

Report exactly what failed — the command, the error text, the URL, the port — state that the
walkthrough did not happen, and stop. Do not read source and present it as a walkthrough. Do not
produce a "preliminary review pending environment access". The user asked what it is like to use;
the honest answer is "I could not get it running, here is what broke, here is what I need."

Report it like this:

```
BLOCKED — walkthrough did not happen.
tried     preview_start {name: "builder"}
failed    Error: connect ECONNREFUSED 127.0.0.1:3000
also      preview_logs: "Error: Cannot find module '@repo/ui'"
need      confirmation the workspace is installed (pnpm install), or the correct dev command
state     0 screens observed. No findings, observed or unobserved, are available.
```

Four common causes and what to do about each:

| Cause | Symptom | Fix / what to ask for |
|---|---|---|
| No dev-server config | `.claude/launch.json` missing or has no entry for this app | Write the entry if the dev command is obvious from `package.json`; otherwise ask: **"What command starts this app, and on what port?"** |
| Server starts, port differs | `preview_logs` shows "ready on :5173", pane shows ECONNREFUSED on :3000 | Fix `port` in the launch entry to match the log, restart, retry. If the app prints no port, ask for it. |
| Auth wall, no credentials | Login screen renders, no account to use | Screenshot the login screen — that surface *is* observed and can be reviewed. Ask: **"Test credentials for a <persona-role> account, or a seeded demo user?"** Everything behind the wall is `[UNOBSERVED]`. |
| No seed data | App loads, every list is empty, the flow needs a record | Ask: **"Is there a seed command, or may I create one <record type> through the UI?"** Creating it through the UI is usually best — it is another flow worth walking. If you seed by any other route, apply the §5 disclosure. |

**Failure behaviour when the user is not available to answer:** report the block with the specific
question attached and stop. Do not pick the workaround that lets you produce output. A report built
on a guessed environment is worse than no report, because it looks like the thing that was asked
for.

---

## 10. Handoff

The walkthrough hands four artefacts downstream. Keep them together; each of the others needs all
four, and re-deriving any of them means re-walking.

| Artefact | Form | Consumed by |
|---|---|---|
| **The ledger** | The §7 table, one row per step | [effort-ledger.md](effort-ledger.md) for the Human Cost Score; [critique.md](critique.md) for the effort and flow axes |
| **The screenshot set** | `NN-short-slug.png`, capture order, never renumbered | [critique.md](critique.md) for presentation, cognition and hierarchy; [responsive.md](responsive.md) if you captured other widths |
| **The persona** | The four lines from §5, verbatim in the report | [critique.md](critique.md) and [feature-fit.md](feature-fit.md) — every judgement of "obvious" or "too slow" is relative to it |
| **The stall points and hesitations** | The notes column, plus any `(post-hint)` marks | [feature-fit.md](feature-fit.md) — a new feature that lands on an existing stall is a fit problem, not a feature problem; [mindmap.md](mindmap.md) — stalls are the edges that need drawing |

State in the handoff which screens were observed and which were not. `review`, `fit` and `map` may
only speak to observed screens; anything else they say is `[UNOBSERVED]` and inherits that mark
from here.

One walkthrough pass. Batch the findings once. Do not re-walk to polish.
