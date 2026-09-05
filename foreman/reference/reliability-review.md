# Foreman reliability review

Source reviewed: the plugin's skills, gates, adapters, task parser, supervisor,
integration, handover and evidence checks, plus the supplied FactoryOS session
observations and its local scheduling/status scripts. FactoryOS was inspected as
evidence; its product code and local scripts were not changed by this update.

| Observed gap | Cause found | Correction |
|---|---|---|
| Several days with no visible application | Vertical-slice advice without delivery commitments or an early preview lane | Product/targeted modes; MVP and production milestones; frozen sprints; static frontend alongside backend; shared contracts and explicit wiring |
| UI rebuilt in a later session | UI direction and browser evaluation arrived late | Accepted design direction before UI development; preview browser pass; representative UI states; contract-backed fixtures |
| Active workers shown in backlog | Spawn did not own Status/Session writes | Shared guarded dispatch records both; failed launches restore prior task text; all views refresh |
| Duplicate task header/incorrect totals | Tolerant parsing and unstructured merge unions | Detect duplicate headings, fields and task IDs; refuse state writes; merge only compatible task bookkeeping; show integrity errors on views |
| Dashboard repeatedly stale and very large | Refresh was a separate remembered step; every historical transcript embedded | State/launch/integration/loop-owned refresh; atomic files and dirty repair marker; 12 recent/live transcript previews, bounded events/detail and read size |
| Sessions lost with uncommitted worktrees | Branch existence mistaken for preserved work | Existing ancestry guards retained; periodic/pressure/exit/compaction recovery snapshots; explicit early commit triggers; archived evidence and original tested Git refs |
| Historical supervisor flood | Deduplication lived only in process memory | Persistent supervisor state, durable acknowledged outbox, terminal-threshold suppression, prefix filtering and bounded notifications |
| Completion was missed for 35 minutes | FactoryOS's `supervise-live.py` filters out dead PIDs, including completion | Runner exit marker independent of stream; no PID filtering of events; polling reconciliation and heartbeat; manager outbox checks |
| Jobs disappeared from the queue | FactoryOS dequeues before launch, with no durable launch acknowledgement | Queue states pending/launching/launched/failed/interrupted; recovery after reservation; single-instance locks |
| Laptop thrashing and ad hoc resource scripts | Worker ceiling alone did not represent RAM/CPU capacity | Built-in macOS/Linux resource sampling, admission thresholds, recovery hysteresis and visible pause reason; existing workers are not killed for capacity |
| Testing kept refilling backlog | No G4 triage boundary or distinction between acceptance failures and optional findings | Deduplicated findings ledger; optional 0–2 observations are known issues; acceptance failures block at any severity; explicit scope amendments and bounded fix rounds |
| Gate rules could be skipped | Status edits, spawn, reports and integration had separate unchecked paths | State transition checks and receipts; guarded launch; per-case verdict consistency; managed G3 Verify execution with content binding; G4 replay verification |
| “All beta” hid a large testing queue | Status reporting omitted remaining gate work | Sprint commitment/current scope and remaining G4/G5 counts are explicit; active sprint can finish without waiting for future module backlog |

## Validation and practical limits

The regression suite includes isolated Git repositories and simulated Claude/Grok
executables launched as real child processes. It exercises developer → independent
tester → integration → beta → sprint close, including manager bookkeeping conflicts,
durable evidence and refreshed views. Tests also cover resource pressure, queue
failure/crash recovery, duplicate task data, stale scope, contradictory verdicts,
notification loss, PID reuse and uncommitted recovery. No paid model workers are
launched by the suite. A read-only probe also verified aggregate RAM/CPU collection
on the development laptop.

A read-only render of the current FactoryOS data produced 2,081,097 bytes in
0.242 seconds, with 12 embedded transcript previews. This measures HTML generation,
not browser paint time, and does not overwrite FactoryOS's dashboard. The supplied
observation described the earlier dashboard as 53 MB and roughly 30 seconds to write.

These are executable workflow guarantees, not a guarantee that a model's technical
judgment is correct. Actual product tests, browser inspection and relevant production
checks still determine readiness. A copied recovery snapshot is not a Git commit;
skipped or concurrently changing files are reported. A complete power/disk failure
before preservation can still lose work. Resource control pauses admission and does
not forcibly reclaim memory from running workers.

New managed projects require a valid delivery plan. Existing runs without a plan
keep the labelled legacy launch path; this avoids breaking project scripts that
reference this checkout directly. Migrate remaining scope to use the managed loop
and retire conflicting local scripts/instructions. Source version 0.5.0 does not
automatically replace separately installed plugin caches.
