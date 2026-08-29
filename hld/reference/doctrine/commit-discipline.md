<!-- Distilled from the owner's global CLAUDE.md §Git commits, snapshot 2026-08-30.
     The mechanical half lives in scripts/commit_check.py; this is the judgment half. -->

# Commit discipline

The unit of a commit is a **working piece of functionality**, not a step of your
process. Commit when something a user or reviewer would recognise as a whole is done
and verified: a complete task, a fix that actually fixes the thing. Commit frequently —
but at that size, never smaller.

- **No fragments useless alone.** A helper extracted for a caller belongs in the same
  commit as the caller. If the message needs "…so that the next commit can…", it is not
  finished — keep working and commit once.
- **Prove "useless alone".** Before committing a new module, grep for importers of it
  *at that commit*. Zero importers means the commit ships dead code — the module belongs
  with its first caller. (`commit_check.py` enforces this.)
- **Never commit something you are about to replace.** A commit is a claim that this
  state is good.
- **Amend your own unpushed commit** rather than stacking a fix-up on it. A defect in a
  commit made minutes ago and not yet pushed is an amend, not a new commit.
- **Do not batch to the end.** "This is done and checked" is the trigger; "I touched a
  file" is not.
- **Stage explicitly — never `git add -A` or `git add .`.** Name the exact paths of the
  task's scope. A working tree often carries someone else's changes.
- **No co-author trailers.** Plain commit messages. (`commit_check.py` enforces this.)
- **Check the diff is reviewable.** `git show --stat` must report line counts, not
  `Bin` — a stray control character makes a source file invisible to every reviewer.
- **Pushing ends the right to rewrite.** Fix shape before the push, not in a rebase
  after it.

In an HLD drive run: one task = one commit (or an amend of that task's own unpushed
commit). `commit_check.py --task <id>` verifies the staged paths sit inside the task's
declared scope. It wraps HLD's own commits only — it is **never** installed as a hook on
the product repository.
