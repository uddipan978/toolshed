#!/usr/bin/env bash
# Replay a finished worker lineage onto the base branch and clean up.
#
#   integrate.sh --name test-m01-02 [--root .foreman] [--base main] [--keep-worktree]
#
# Run this as soon as a task passes G4, not at the end of the run. The trunk
# stays green incrementally. Root workers default to HEAD; a successor launched
# before its dependency is integrated must use --base foreman/<predecessor>.
#
# Conflicts are reported, never auto-resolved. An integration Foreman cannot do cleanly
# is a decision for the manager or the human.
set -euo pipefail

NAME=""; ROOT=".foreman"; BASE=""; KEEP="no"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)          NAME="$2"; shift 2 ;;
    --root)          ROOT="$2"; shift 2 ;;
    --base)          BASE="$2"; shift 2 ;;
    --keep-worktree) KEEP="yes"; shift ;;
    *) echo "integrate.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$NAME" ]] || { echo "integrate.sh: --name is required" >&2; exit 2; }
if [[ "${FOREMAN_INTEGRATION_LOCK:-}" != "1" ]]; then
  LOCK_ARGS=(run --root "$ROOT" --name "$NAME")
  [[ -n "$BASE" ]] && LOCK_ARGS+=(--base "$BASE")
  [[ "$KEEP" == "yes" ]] && LOCK_ARGS+=(--keep-worktree)
  exec python3 "$SCRIPT_DIR/integration_record.py" "${LOCK_ARGS[@]}"
fi

ROOT="$(cd "$(dirname "$ROOT")" && pwd)/$(basename "$ROOT")"
PROJECT="$(dirname "$ROOT")"
STATUS="$ROOT/work/sessions/$NAME/status.json"
json_field() {
  python3 -c 'import json,sys
p,k=sys.argv[1],sys.argv[2]
try:
    print(json.load(open(p)).get(k) or "")
except Exception:
    print("")' "$1" "$2"
}
status_field() {
  json_field "$STATUS" "$1"
}
session_is_alive() {
  python3 - "$SCRIPT_DIR" "$1" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from foreman_lib import load_json
from ops import session_alive
sys.exit(0 if session_alive(load_json(Path(sys.argv[2]))) else 1)
PY
}
BRANCH="$(status_field branch)"
CWD="$(status_field cwd)"
PID="$(status_field pid)"
STATE="$(status_field state)"
AGENT="$(status_field agent)"
TASK_IDS="$(status_field task_ids)"
if [[ -n "$TASK_IDS" && "$TASK_IDS" != "[]" && "${AGENT##*:}" != "foreman-tester" ]]; then
  echo "integrate.sh: managed work must pass independent G4; integrate the tester session" >&2
  exit 1
fi
RECORDED_BASE="$(status_field base_commit)"
START_COMMIT="$(status_field start_commit)"
LINEAGE_START="$(status_field lineage_start_commit)"
BASE_SESSION="$(status_field base_session)"
[[ -n "$BRANCH" ]] || BRANCH="foreman/$NAME"
if [[ -n "$CWD" && -d "$CWD" && "$CWD" != "$PROJECT" ]]; then
  WT="$CWD"
elif [[ -d "$PROJECT/.claude/worktrees/foreman-$NAME" ]]; then
  WT="$PROJECT/.claude/worktrees/foreman-$NAME"
else
  WT="$PROJECT/.grok/worktrees/foreman-$NAME"
fi

cd "$PROJECT"
git rev-parse --git-dir >/dev/null 2>&1 || { echo "integrate.sh: not a git repo" >&2; exit 2; }
git show-ref --verify --quiet "refs/heads/$BRANCH" || {
  echo "integrate.sh: no branch $BRANCH — nothing to integrate"; exit 0; }

[[ -n "$BASE" ]] || BASE="$(git rev-parse --abbrev-ref HEAD)"
[[ "$BASE" != "$BRANCH" ]] || { echo "integrate.sh: base and worker branch are the same" >&2; exit 2; }

# Never change or remove a worktree beneath a live worker. A Stop hook may still
# be checking its task file there even after the manager has seen a final-looking
# message in the stream. Terminal non-success states get one fresh artefact check:
# a worker that finished cleanly at its turn/budget cap is READY, not failed work.
CHECK_TERMINAL="no"
case "$STATE" in
  ""|done) ;;
  ready:*|stopped:*|review:*) CHECK_TERMINAL="yes" ;;
  *)
    echo "integrate.sh: $NAME is not in a terminal state (state: $STATE)" >&2
    echo "  wait for DONE, READY, REVIEW, or a stopped state before integration" >&2
    exit 1
    ;;
esac
# A tester's evidence can be complete with a fail/could-not-run verdict. That is
# READY for manager disposition, but never ready to integrate.
if [[ "${AGENT##*:}" == "foreman-tester" ]]; then
  CHECK_TERMINAL="yes"
fi
# Legacy developer/tester statuses need a fresh provenance check even if an old
# supervisor labelled them done; otherwise protected committed paths are unknown.
if [[ -z "$START_COMMIT" ]] && [[ "${AGENT##*:}" =~ ^foreman-(developer|tester)$ ]]; then
  CHECK_TERMINAL="yes"
fi
if session_is_alive "$STATUS"; then
  echo "integrate.sh: $NAME is still running (pid $PID)" >&2
  echo "  wait for the supervisor's DONE/READY/REVIEW event before integration" >&2
  exit 1
fi
if [[ "$CHECK_TERMINAL" == "yes" ]]; then
  VERIFY_ARGS=(--check-session "$(dirname "$STATUS")")
  if [[ "${AGENT##*:}" == "foreman-tester" ]]; then
    VERIFY_ARGS+=(--require-pass)
  fi
  if ! python3 "$SCRIPT_DIR/verify_gate.py" "${VERIFY_ARGS[@]}"; then
    echo "integrate.sh: terminal session $NAME is not eligible for integration" >&2
    exit 1
  fi
  echo "integrate.sh: validated completed artefacts after $STATE"
fi

# Uncommitted work is evidence to rescue, not material to sweep into a commit.
# In particular, never use git add -A here: browser probes and tool scratch files
# are not automatically part of the task.
if [[ -d "$WT" ]] && [[ -n "$(git -C "$WT" status --porcelain)" ]]; then
  echo "integrate.sh: uncommitted work in $NAME's worktree:"
  git -C "$WT" status --short
  echo "  refusing to integrate or delete it; inspect and commit explicit task-scoped paths" >&2
  exit 1
fi

# Sessions created before ancestry metadata existed can still be integrated
# safely when their lineage can be reconstructed from the primary checkout's
# merge-base. worktree.py skips Foreman's synthetic launch commit exactly as the
# stop gate does. An unknowable lineage stays on the explicit legacy merge path.
if [[ -z "$LINEAGE_START" && -d "$WT" ]]; then
  INSPECT_JSON="$(python3 "$SCRIPT_DIR/worktree.py" inspect --cwd "$WT")"
  LINEAGE_START="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("effective_start_commit") or "")' <<<"$INSPECT_JSON")"
  LINEAGE_SOURCE="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("start_commit_source") or "unknown")' <<<"$INSPECT_JSON")"
  if [[ -n "$LINEAGE_START" ]]; then
    echo "integrate.sh: inferred legacy lineage start $LINEAGE_START ($LINEAGE_SOURCE)"
  fi
fi

if [[ -n "$RECORDED_BASE" ]] && ! git merge-base --is-ancestor "$RECORDED_BASE" "$BRANCH"; then
  echo "integrate.sh: ancestry check failed — $BRANCH does not contain its recorded base" >&2
  echo "  recorded base: $RECORDED_BASE" >&2
  exit 1
fi
if [[ -n "$LINEAGE_START" ]] && ! git merge-base --is-ancestor "$LINEAGE_START" "$BRANCH"; then
  echo "integrate.sh: lineage check failed — $BRANCH lost its recorded start" >&2
  echo "  lineage start: $LINEAGE_START" >&2
  exit 1
fi

# Retain the exact tested object independently of rebases and branch cleanup.
git update-ref "refs/foreman/tested/$NAME" "$(git rev-parse "$BRANCH")"

# Check the user's product edits BEFORE the bookkeeping commit. A pre-staged
# product change would otherwise be included in that commit unexpectedly.
if [[ -n "$(git status --porcelain | grep -vE ' (\.foreman/|\.gitignore)' || true)" ]]; then
  echo "integrate.sh: uncommitted changes outside .foreman; preserve them before integration" >&2
  exit 1
fi

PRED_INCLUDED="no"
if [[ -n "$BASE_SESSION" ]]; then
  BASE_STATUS="$ROOT/work/sessions/$BASE_SESSION/status.json"
  PRED_BRANCH="$(json_field "$BASE_STATUS" branch)"
  if [[ -n "$PRED_BRANCH" ]] \
      && git merge-base --is-ancestor "$PRED_BRANCH" "$BRANCH" 2>/dev/null; then
    PRED_INCLUDED="yes"
  fi
fi

# Foreman's own bookkeeping is often uncommitted — the board, the task file the
# manager just touched. That must not block a code merge. Commit it on BASE and
# fail out loud if the commit fails; `|| true` used to continue into a merge
# with a dirty tree.
if [[ -n "$(git status --porcelain -- .foreman .gitignore)" ]]; then
  echo "integrate.sh: committing .foreman bookkeeping on $BASE:"
  git status --short -- .foreman .gitignore
  git add -u -- .foreman
  git add -- .foreman
  if [[ -e .gitignore ]] || git ls-files --error-unmatch .gitignore >/dev/null 2>&1; then
    git add -u -- .gitignore
    [[ -e .gitignore ]] && git add -- .gitignore
  fi
  git commit -m "foreman: bookkeeping before integrating $NAME" || {
    echo "integrate.sh: failed to commit bookkeeping; refusing to merge over a dirty .foreman" >&2
    exit 1
  }
fi

# Anything dirty OUTSIDE .foreman/ is the user's own work. Never merge over it.
if [[ -n "$(git status --porcelain | grep -vE ' (\.foreman/|\.gitignore)' || true)" ]]; then
  echo "integrate.sh: '$BASE' has uncommitted changes outside .foreman/:" >&2
  git status --short | grep -vE ' (\.foreman/|\.gitignore)' | sed 's/^/    /' >&2
  echo "  commit or stash them first — Foreman will not merge over your work" >&2
  exit 1
fi

git checkout -q "$BASE"
INTEGRATE_LOG="/tmp/foreman-integrate-$$.log"

# Root workers start on a synthetic commit carrying uncommitted task inputs. That
# commit must not be merged: it makes the manager's normal status/log edits look
# like unrelated changes from a common ancestor. Replay only commits after the
# recorded lineage start onto the current base, then fast-forward.
if [[ -n "$LINEAGE_START" && -d "$WT" ]]; then
  if git -C "$WT" rebase --onto "$BASE" "$LINEAGE_START" "$BRANCH" >"$INTEGRATE_LOG" 2>&1 \
      || python3 "$SCRIPT_DIR/merge_task.py" --worktree "$WT" >>"$INTEGRATE_LOG" 2>&1; then
    python3 "$SCRIPT_DIR/integration_record.py" verify --name "$NAME" --root "$ROOT"
    git merge --ff-only "$BRANCH" >>"$INTEGRATE_LOG" 2>&1
    echo "integrated tested lineage $NAME into $BASE"
    rm -f "$INTEGRATE_LOG"
  else
    CONFLICTS="$(git -C "$WT" diff --name-only --diff-filter=U | tr '\n' ' ')"
    git -C "$WT" rebase --abort 2>/dev/null || true
    echo "integrate.sh: REBASE CONFLICT integrating $NAME into $BASE" >&2
    echo "  conflicting files: ${CONFLICTS:-unknown}" >&2
    echo "  product integration was aborted; $BRANCH still holds the tested work" >&2
    if [[ -n "$CONFLICTS" ]] && [[ -z "$(printf '%s\n' $CONFLICTS | grep -v '^\.foreman/' || true)" ]]; then
      echo "  this is a Foreman bookkeeping/coordination conflict, not evidence of bad task decomposition" >&2
      echo "  preserve task evidence and regenerate manager-owned log/board files" >&2
    else
      echo "  product files conflicted; possible causes include overlapping task scope or a stale base" >&2
    fi
    rm -f "$INTEGRATE_LOG"
    exit 1
  fi
elif git merge --no-ff --no-edit -m "foreman: integrate $NAME" "$BRANCH" >"$INTEGRATE_LOG" 2>&1; then
  # Last-resort compatibility when neither recorded nor inferred lineage exists.
  echo "integrated legacy session $NAME into $BASE"
  rm -f "$INTEGRATE_LOG"
else
  CONFLICTS="$(git diff --name-only --diff-filter=U | tr '\n' ' ')"
  git merge --abort 2>/dev/null || true
  echo "integrate.sh: MERGE CONFLICT integrating legacy session $NAME into $BASE" >&2
  echo "  conflicting files: ${CONFLICTS:-unknown}" >&2
  rm -f "$INTEGRATE_LOG"
  exit 1
fi

# Archive results and reconcile task/views before removing any worker checkout.
python3 "$SCRIPT_DIR/integration_record.py" finish --name "$NAME" --root "$ROOT"

if [[ "$KEEP" == "no" ]]; then
  if [[ -d "$WT" ]] && ! git worktree remove "$WT"; then
    echo "integrate.sh: merge succeeded, but clean worktree removal failed: $WT" >&2
    echo "  it was left in place; no force-removal was attempted" >&2
    exit 1
  fi
  git branch -q -d "$BRANCH" 2>/dev/null || true
  echo "cleaned up worktree and branch for $NAME"

  # A tested branch is normally based on its developer session. Once that exact
  # ancestry is merged, retire the predecessor too—but only if it is dead and
  # clean. A failed safety check leaves it recoverable.
  if [[ -n "$BASE_SESSION" ]]; then
    BASE_STATUS="$ROOT/work/sessions/$BASE_SESSION/status.json"
    PRED_WT="$(json_field "$BASE_STATUS" cwd)"
    PRED_BRANCH="$(json_field "$BASE_STATUS" branch)"
    PRED_PID="$(json_field "$BASE_STATUS" pid)"
    if session_is_alive "$BASE_STATUS"; then
      echo "left predecessor $BASE_SESSION in place: its pid is still live"
    elif [[ -n "$PRED_WT" && -d "$PRED_WT" ]] \
        && [[ -n "$(git -C "$PRED_WT" status --porcelain)" ]]; then
      echo "left predecessor $BASE_SESSION in place: its worktree is dirty"
    elif [[ "$PRED_INCLUDED" == "yes" ]]; then
      PRED_REMOVED="yes"
      if [[ -n "$PRED_WT" && -d "$PRED_WT" ]] \
          && ! git worktree remove "$PRED_WT" 2>/dev/null; then
        PRED_REMOVED="no"
        echo "left predecessor $BASE_SESSION in place: clean removal failed"
      fi
      if [[ "$PRED_REMOVED" == "yes" ]]; then
        # Rebase preserved these patches with new commit IDs, so the original
        # predecessor ref is no longer an ancestor even though PRED_INCLUDED was
        # verified before integration.
        git branch -q -D "$PRED_BRANCH" 2>/dev/null || true
        echo "cleaned up tested predecessor $BASE_SESSION"
      fi
    fi
  fi
fi
