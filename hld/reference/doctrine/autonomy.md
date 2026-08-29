<!-- Distilled from the owner's continuous-execution doctrine, snapshot 2026-08-30. -->

# Autonomy — grill once, then run to the end

All questions happen at H0. After the brief is signed and g0 passes, the run continues
through every gate without asking whether to proceed. Progress notes are short;
`.hld/STATUS.md` and the artifacts are the durable record, not the conversation.

**The pause list is closed.** Stop only when:

1. Required authorization is missing (an irreversible or externally visible action the
   brief did not cover).
2. The brief contains a material contradiction discovered mid-run — record it in
   `decisions/`, present the smallest question that resolves it.
3. A decision would significantly change scope or architecture.
4. A blocker cannot be resolved safely (record `[b]` with evidence first).
5. External state or input only the user can provide is required.
6. Continuing would exceed the scope boundary — a task needs a whole non-UI subsystem;
   stop, name the subsystem, point at Foreman.
7. The kill door closed (H5 still runs) or all gates are done.

Everything else keeps moving. A missing tool is a `COULD-NOT-RUN`, not a question. An
ambiguous small choice is a `decisions/D*.md` entry with the taken path and the
rejected one, not a question. Never claim done while a gate is open — `gate.py --final`
enforces this at session stop.
