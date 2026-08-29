# Dead references — the `sweep` command

Something was removed: a tab, a page, a route, a whole feature. The removal commit deleted the
thing. It did not delete the seventeen other places that still point at it. This file is the hunt
for those, and it is a checklist, not an essay — work top to bottom and tick.

**Precondition.** You must know exactly what was removed: the route path, the display name, the
component, and the commit or branch that removed it. If you do not have all four, ask before
searching. Searching for the wrong name returns zero hits, and zero hits reads identically to
clean. That single failure mode is why most sweeps are worthless.

**Output.** Findings in the standard format (§6), plus the list of searches you ran, so the reader
can see what you did *not* search. Findings from grep alone are `[UNOBSERVED]`. They become real
findings with a severity only after §4, when you have clicked the thing in a browser.

---

## 0. Name the removed thing four ways before you search a single time

One term finds one kind of reference. The slug finds route tables and hrefs. The display name finds
copy, docs, emails and i18n values. The component name finds imports and tests. The route constant
finds everything that was written by someone who did it properly. Search one and you find roughly
a quarter of the damage while feeling finished.

Set these once and reuse them in every recipe below.

```sh
SLUG=invoices              # the URL segment:            /billing/invoices
NAME="Invoices"            # what the user saw:          the tab label, the page title
COMP=InvoicesTab           # component / file / class:   InvoicesTab.tsx, useInvoices
CONST=ROUTE_INVOICES       # the identifier:             ROUTE_INVOICES, Routes.Invoices, 'invoices' enum member
BASE=main                  # what the removal branched from
```

Failure behaviour when one of the four does not exist:

- **No route constant** — the codebase writes paths as literals. Skip the `$CONST` searches and say
  so in the report; do not silently drop the row, because a reader will assume it was clean.
- **The display name is a common word** (`Reports`, `Settings`, `Team`) — do not widen your search
  to compensate and do not narrow it either. Run it, expect noise, and filter by hand. A
  three-hundred-hit search you triaged beats a zero-hit search you trusted.
- **The name was renamed at some point** — search both. `git log --diff-filter=D --name-only $BASE..`
  gives you the deleted files; `git log -S"$NAME" --oneline` gives you every commit that ever
  touched the string, including the one that introduced the old name.

Start from the removal diff, not from a blank prompt:

```sh
git diff --stat $BASE..HEAD
git log --diff-filter=D --name-only $BASE..HEAD    # what actually disappeared
```

---

## 1. Why grep alone is insufficient

A removed route leaves traces in forms no single search matches. `rg invoices` misses all of these,
and each of them is a real thing users hit:

- **Constructed paths.** `` `/billing/${tab}` `` contains neither `invoices` nor the full route.
- **Translated copy.** The English string was deleted; `de.json` still says *Rechnungen*.
- **Config, not code.** A redirect map in `vercel.json`, a nav array in a CMS, a role name in a
  seed file.
- **Names that only exist at runtime.** An analytics event `billing_invoices_viewed` still fires
  from a dashboard tile; a saved user preference `lastTab: "invoices"` still loads on next login.
- **Pictures.** A screenshot in the onboarding tour showing a tab that no longer exists. No text
  search on earth finds that.

So the method is fixed, and it is three passes in this order:

1. **Enumerate reference kinds** (§2) — decide what *categories* can exist in this codebase before
   you search for any of them. A kind you never listed is a kind you never searched.
2. **Search each kind with its own recipe** (§2, §3) — four names per kind, not one.
3. **Verify in the running UI** (§4) — because the code sweep tells you what points at the removal;
   only the browser tells you what a user now experiences when they follow it.

Skipping pass 3 is not a shortcut, it is the whole defect. This is hard rule 1 of the skill
([walkthrough.md](walkthrough.md)): a reference you did not click is `[UNOBSERVED]`.

---

## 2. The reference inventory

Work every row. Mark rows that do not apply to this codebase as `n/a` in the report rather than
omitting them — an omitted row is indistinguishable from a clean one.

| # | Kind | Where it lives | Search | A dead one looks like |
|---|---|---|---|---|
| 1 | Route definitions & constants | router files, `app/`/`pages/` dirs, `routes.ts`, path enums | `rg -n "$SLUG\|$CONST" --glob '*rout*' --glob '*path*'` | a route entry whose component import was deleted; a constant nothing imports |
| 2 | Navigation config | sidebar, top nav, tab bar, mobile drawer, footer, command palette, quick-add menus | `rg -n "$CONST\|$COMP\|\"$NAME\"" --glob '*{nav,menu,sidebar,tabs,footer,shell}*'` | a nav item rendering a label with no destination, or with a destination that 404s |
| 3 | Breadcrumbs & back-links | breadcrumb builders, `<BackLink to=…>`, page headers, "Return to X" buttons | `rg -n "breadcrumb\|backTo\|returnTo" -A3 \| rg -i "$SLUG\|$NAME"` | a child page whose breadcrumb still names the deleted parent |
| 4 | Links inside copy | body text, empty states, success toasts, error messages, tooltips, validation hints | `rg -n -i "$NAME" --glob '*.{tsx,jsx,vue,svelte,md,mdx}'` | an empty state saying "Add one from the Invoices tab" |
| 5 | Redirects & rewrites | `next.config`, `vercel.json`, `netlify.toml`, nginx conf, middleware, CDN rules | `rg -n "$SLUG" --glob '*.{json,toml,conf,yaml,yml}' --glob '*middleware*'` | a rule redirecting *to* the removed path — a redirect into a 404 |
| 6 | Deep links & share URLs | share/copy-link builders, QR generators, mobile deep-link schemes, `apple-app-site-association` | `rg -n "$SLUG" --glob '*{share,deeplink,universal,qr}*'` | a share button producing a URL that now 404s for the recipient |
| 7 | Feature flags | flag definitions, defaults, remote config, kill switches, flag-gated branches | `rg -n -i "$SLUG\|$COMP" --glob '*{flag,toggle,feature,config}*'` | a flag whose only consumer is gone; worse, a flag defaulting `true` that gates nothing |
| 8 | Permissions & roles | permission enums, policy files, role seeds, RBAC matrices, admin UI checkboxes | `rg -n -i "$SLUG" --glob '*{perm,role,policy,acl,ability,scope}*'` | a permission still listed in the admin role editor that grants access to nothing |
| 9 | i18n keys | `en.json` + **every** other locale, ICU files, plural groups | `rg -rn "$SLUG\|$COMP" locales/ i18n/ lang/` then `rg -c '"'"$SLUG"'\.' locales/*` | key deleted from `en` only; other locales keep it, or the UI falls back and shows a raw key |
| 10 | Analytics & telemetry | event constant files, `track(` call sites, funnel/dashboard definitions, alerting rules | `rg -n "$SLUG\|${SLUG}_" --glob '*{analytics,track,event,telemetry,metric}*'` | a funnel step that will now report 0 forever and read as a conversion collapse |
| 11 | Tests | e2e specs, page objects, route snapshots, MSW handlers, fixtures, seeds, visual baselines | `rg -n "$SLUG\|$COMP\|$NAME" tests/ e2e/ cypress/ playwright/ __fixtures__/` | a skipped spec, a page object with dead selectors, a route snapshot still listing the path |
| 12 | Documentation | README, `docs/`, changelog, in-app tour steps, tooltips, help centre, video captions | `rg -n -i "$NAME\|$SLUG" docs/ *.md` | a tour step anchored to a selector that no longer mounts — the tour silently stalls |
| 13 | Notifications & jobs | email templates, digest builders, push payloads, cron/scheduled jobs, webhooks | `rg -n "$SLUG" --glob '*{email,mail,template,notif,digest,cron,job,worker}*'` | a weekly digest still linking to the removed page, sent to everyone, forever |
| 14 | API endpoints | client API modules, server route handlers, OpenAPI spec, gateway config | `rg -n "$SLUG" --glob '*{api,client,handler,controller,openapi,swagger}*'` | a server endpoint with zero remaining callers, still authenticated, still deployed |
| 15 | Assets | icons, illustrations, images, lottie files, sprite sheets, static exports | `rg -rn "$SLUG\|$COMP" --glob '*.{svg,png,json}' assets/ public/` + `rg -c "$(basename asset)" src/` | an SVG imported nowhere, still shipped in the bundle |
| 16 | Ordering constants | `NAV_ORDER`, sort weights, index-based tab selection, keyboard shortcut maps (`⌘3`) | `rg -n "$CONST" --glob '*{order,sort,index,shortcut,keymap}*'` | a gap in the order array, or `⌘4` now opening what `⌘3` used to |
| 17 | Persisted user state | `localStorage`, cookies, saved views, user prefs table, "last visited tab" columns | `rg -n "lastTab\|activeTab\|defaultView\|savedView"` + check the DB column's stored values | a returning user restored onto a tab that no longer exists — blank screen, no error |

### The five rows that need more than one grep

**Row 9, i18n.** Two searches, not one. First `rg` the key prefix across `locales/` to find keys.
Then, for each locale file, confirm the key is gone *everywhere*: `rg -l "\"$SLUG\." locales/`.
An orphaned key is invisible in your language and visible in someone else's, because the fallback
chain resolves in `en` and stops. If your i18n tooling has an unused-key linter, run it and paste
the output; if it does not, say that in the report rather than claiming the row is clean.

**Row 10, analytics.** The code search finds the emitter. It does not find the *consumer*: the
dashboard, the saved funnel, the anomaly alert, the weekly metrics email. Those live outside the
repo. List the event names you removed and hand them to whoever owns the dashboards. Failure
behaviour if you cannot reach that system: report the event names as an outstanding item with
severity `medium`, not as done. A funnel that silently reads zero gets diagnosed as a product
collapse three weeks later by someone who does not know the tab was deleted.

**Row 13, scheduled jobs.** These are the worst class, because they fire on a timer with nobody
watching. A digest job that links to the removed page will keep emailing that link to every user
every Monday until someone complains. Grep the job registry, then grep the templates the jobs
render — they are usually in a different directory from the code that schedules them.

**Row 14, API endpoints.** Removing the page does not remove its endpoint. Two questions per
endpoint: does anything else call it (`rg` the client method name, not the URL), and is it public?
An orphaned authenticated endpoint is dead weight; an orphaned *public* endpoint is dead weight
with an attack surface. Do not delete a server route in the same change as a UI removal without
checking mobile clients and third-party API consumers, which do not live in this repo and will not
show up in any grep you run here.

**Row 17, persisted state.** This is the one that produces "the app is broken and I can't tell you
why" reports. A user whose stored preference is `activeTab: "invoices"` gets restored onto a tab
the router no longer knows. Whether that 404s, blank-screens, or falls back to the first tab is a
property of your router's default case — and you cannot read it off the source with confidence.
Set the value by hand in devtools, reload, and look. That is a §4 check, not a §2 check.

---

## 3. The constructed-path trap

A path assembled at runtime matches no literal search:

```tsx
const TABS = ['overview', 'invoices', 'payouts'] as const;
navigate(`/billing/${tab}`);            // rg "/billing/invoices" → 0 hits
<Link href={`${base}/${slug}/settings`} />
```

Three searches find these, and you need all three:

```sh
rg -n "/$SLUG\b|'$SLUG'|\"$SLUG\""       # the bare segment, quoted and unquoted
rg -n 'billing/\$\{|`/billing'           # the builder: template literals over the parent segment
rg -n "TABS|TAB_IDS|type .*Tab =" -A6    # the enum/union that supplies the values
```

The enum is the highest-yield of the three and the one people skip. `'invoices'` sitting in a
`const TABS` array is a live reference: it renders a tab, it accepts a URL, and it survives every
search for the full path. In a typed codebase, deleting the union member turns the dead references
into compile errors for free — so delete the union member *first* and let the type checker do
pass 2 for you. Failure behaviour when the codebase is untyped or the values come from a CMS or
database: the compiler cannot help, so the enum search is mandatory and you must also query the
data source for stored values.

Same trap, other shapes: `t(\`nav.${tab}.label\`)` for i18n keys, `track(\`${section}_viewed\`)`
for analytics, `import(\`./tabs/${tab}\`)` for lazy component loading. Any backtick with a `${`
inside a path, key, or event name is a place your literal searches are blind.

---

## 4. Verify in the UI, not only in the tree

Mandatory. The code sweep produces candidates; the browser produces findings. Walk every surface
that linked to the removed thing — every row you found a hit in — and record what a user now
experiences. Screenshot each. Do not reason about what the router "should" do.

Four outcomes. Each requires something different:

| Outcome | What you see | Verdict | Required action |
|---|---|---|---|
| **Gone** | the link is not rendered; the surface looks intentional, no gap, no stray separator | good | screenshot as evidence, no finding |
| **404s** | an error page, and it names the problem | bad | fix or redirect (§5). Severity `high` if reachable from nav or a sent email, `medium` if only from docs |
| **Silently does nothing** | click, nothing happens; no navigation, no error, no spinner, no toast | **worst** | severity `blocker` on a primary path. The user cannot tell whether they mis-clicked, the app is slow, or it is broken — so they click again, wait, and blame themselves |
| **Goes somewhere plausible but wrong** | lands on a real page that is not what the label promised | bad, and hardest to detect | severity `high`. This is the one that survives QA, because the screen renders fine and only the label is lying |

The silent case deserves its severity. A 404 is honest: it tells the user the destination is gone
and offers a way out. A dead click communicates nothing, so the user's model of the product is now
"this app randomly ignores me" rather than "that page moved" — cite `mental-model` [heuristic]
(`python3 scripts/why.py --name "Mental Model"`;
`/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/05-decision-making-and-simplicity.md`).
Rank a silent failure above a 404 every time.

What to walk, minimum:

1. Every nav surface at desktop width — sidebar, top bar, command palette, footer.
2. The same surfaces at mobile width. Mobile nav is frequently a separate config file and is
   frequently the one that still has the item ([responsive.md](responsive.md)).
3. One page whose breadcrumb named the removed parent.
4. The old URL typed directly into the address bar, cold, with no history — this is the bookmark
   case and the emailed-link case, and it is the one nobody tests.
5. The old URL while logged out, then logged in as a role that used to have the permission.
6. A returning user with the stale persisted preference (row 17): set it in devtools, reload.
7. Any in-app tour or tooltip that referenced the removal — run the tour to its end.

Failure behaviour when a surface cannot be reached (no test account for that role, no way to
trigger the digest email): do not guess. Write it as an outstanding item in §6 with the reason.
An unwalked surface is a blocked check, not a passed one.

---

## 5. What to do with each dead reference

| Situation | Do this | Why |
|---|---|---|
| Internal-only link, no user ever saw the URL | **delete** the reference | nothing to preserve; a redirect you do not need is a rule someone maintains forever |
| The feature moved or was renamed | **redirect** old path → new path, `301` if permanent | preserves bookmarks, sent emails and search results at zero user cost |
| The feature is genuinely gone, and users used it | **explanatory page** at the old path: what happened, what to do instead, one link out | a bare 404 answers none of the three questions the user actually has |
| Removal is staged, or third parties integrate with it | **keep with a deprecation notice** and a removal date | gives integrators a window; keeps you honest about the date |
| Orphaned asset, i18n key, unused endpoint, dead test | **delete** | dead weight; an orphaned public endpoint is also an attack surface |
| Analytics event | **stop emitting, annotate the dashboard** | deleting the event without annotating turns a removal into an apparent metric collapse |

**The rule that is not negotiable:** if users had bookmarks, saved views, or received emails
pointing at the removed thing, a bare 404 is not an acceptable outcome. Redirect it or explain it.
A 404 is a message that says *you did something wrong*, delivered to a person who did exactly what
your product told them to do last week. The product changed under them; the error page blames them
for it. That is a `high` finding, not a nit.

Two principles carry this, and both are honest about their grade:

- `postels-law` [heuristic] — be liberal in what you accept. The UX form of it is: accept the old
  URL, normalise it to the new one, and never make the human retype what you can resolve.
  `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/02-interaction-and-system-response.md`
- `peak-end` [replicated] — an experience is judged by its peak and its end. A dead link is
  frequently the *end* of a session: the user came back for one thing and hit a wall.
  `/Users/shankhajeettaran/workspace/learning/research/laws-of-ux/04-motivation-and-memory-bias.md`

Do not cite these as proof that a redirect is required — they are a heuristic and an applied
inference respectively, and stating them as measurement is exactly the misuse hard rule 3 forbids.
The argument for the redirect stands on its own: the cost is one config line, once; the cost of not
doing it is paid by every user who follows the old link, every time.

**Two secondary consequences to check, not to skip:**

- **Removing an item reorders the rest.** Keyboard shortcuts bound by index (`⌘3`) now open
  something different, and muscle memory takes users to the wrong screen with no error at all.
  Rebind explicitly or renumber deliberately.
- **Position in a list carries weight.** `serial-position` [replicated] says first and last items
  are the ones remembered; deleting the last item promotes whatever was above it into a position it
  was not designed for. Look at the nav after the removal and decide the order on purpose.

---

## 6. The sweep report

Fixed sections, in this order. The second section is the one that makes the report trustworthy:
it shows what was *not* searched.

```
SWEEP — <what was removed>
removed   /billing/invoices · "Invoices" tab · InvoicesTab.tsx · ROUTE_INVOICES
commit    a1b2c3d (branch chore/remove-invoices, base main)
names     SLUG=invoices NAME="Invoices" COMP=InvoicesTab CONST=ROUTE_INVOICES

SEARCHED  (17 kinds · 14 run · 2 n/a · 1 not possible)
  01 routes         rg -n "invoices|ROUTE_INVOICES" --glob '*rout*'        → 3 hits
  02 nav config     rg -n "ROUTE_INVOICES" --glob '*{nav,menu,sidebar}*'   → 2 hits
  …
  10 analytics      rg -n "invoices_" --glob '*analytics*'                 → 1 hit
     └ dashboards NOT searched — no access to the analytics workspace
  15 assets         n/a — no per-feature assets in this codebase

FINDINGS  (by kind, most severe first)

F-01  [blocker]  scope: global   axis: effort
  screen    / (sidebar, all pages)
  observed  screenshot 01 → 02
  action    clicked sidebar item "Invoices"
  cost      1 click · no navigation · no error · 1 retry before giving up
  principle mental-model [heuristic] · conflicts: —
  problem   The item still renders and clicking it does nothing at all — no route, no error.
  proposal  Delete the entry from NAV_ITEMS; add a 301 from /billing/invoices to /billing.
  build     S · apps/web/src/nav/items.ts, next.config.js

F-02  [high]  scope: page-level   axis: flow
  screen    /billing/invoices (typed directly, cold session)
  observed  screenshot 03
  action    pasted the URL from last month's digest email
  cost      1 navigation · dead end · 0 routes out
  principle postels-law [heuristic]
  problem   A URL we emailed to every user last Monday now returns a bare 404.
  proposal  Redirect to /billing; keep the redirect for two release cycles.
  build     S · next.config.js redirects

F-07  [UNOBSERVED]
  file      locales/de.json:412  "billing.invoices.title"
  problem   Key removed from en.json only; de/fr/es still carry it.
  proposal  Delete from all locale files.
  build     S · locales/*.json
  note      no UI path renders this key any more; not reachable to observe

OUTSTANDING
  · analytics dashboards using billing_invoices_viewed — hand to <owner>
  · digest email template not verifiable without triggering Monday's job
```

Severity vocabulary, exactly: `blocker|high|medium|low|nit`. Scope vocabulary, exactly:
`global|template-level|page-level`. A grep hit you have not clicked is `[UNOBSERVED]` and carries
no severity — it is a lead, not a finding.

---

## 7. Copy-paste checklist

Give the user this block so they can re-run the sweep themselves on the next removal.

```sh
# 1 — name it four ways
SLUG=…  NAME=…  COMP=…  CONST=…  BASE=main

# 2 — what actually disappeared
git log --diff-filter=D --name-only $BASE..HEAD

# 3 — the four-name sweep (run all four; one is not a sweep)
rg -n "$SLUG"  ; rg -n -i "$NAME" ; rg -n "$COMP" ; rg -n "$CONST"

# 4 — the kinds a bare name search misses
rg -n "\`.*\\\$\{.*\}"        --glob '*.{ts,tsx,js,jsx}'   # constructed paths
rg -rn "$SLUG" locales/ i18n/ lang/                        # every locale, not just en
rg -n "$SLUG" --glob '*.{json,toml,yaml,yml,conf}'         # redirects, flags, config
rg -n "$SLUG" --glob '*{email,cron,job,digest,worker}*'    # things that fire on a timer
rg -n "$SLUG" --glob '*{analytics,track,event,metric}*'    # events + whatever charts them
rg -n "$SLUG" --glob '*{perm,role,policy,acl}*'            # permissions gating a ghost
rg -n "$COMP" tests/ e2e/ cypress/ playwright/             # specs, page objects, fixtures
rg -n -i "$NAME" docs/ *.md                                # docs, changelog, tour copy
rg -n "lastTab|activeTab|defaultView|savedView"            # persisted state pointing at it

# 5 — walk it (no substitute exists for this step)
#  desktop nav · mobile nav · breadcrumb on a child page · the old URL cold in the address bar
#  · logged out · stale saved preference restored · the in-app tour to its end
```

**Stop condition.** One sweep pass, one report, one follow-up to confirm the fixes landed. If the
sweep keeps finding new kinds after the second pass, the problem is that §2 was not enumerated
before searching — restart from §0 rather than grinding, because an unbounded search costs more
than it finds and never terminates on its own.

**Related:** [walkthrough.md](walkthrough.md) for the driving discipline and the evidence ledger ·
[critique.md](critique.md) for severity and the five axes · [effort-ledger.md](effort-ledger.md)
for costing the Recovery component a dead link creates.
