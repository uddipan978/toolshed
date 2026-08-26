#!/usr/bin/env bash
# Merge a finished worker's branch back into the base branch and clean up.
#
#   integrate.sh --name dev-m01-02 [--root .foreman] [--base main] [--keep-worktree]
#
# Run this as soon as a task passes G4, not at the end of the run. Two reasons:
# the trunk stays green incrementally, and spawn.sh branches from HEAD — so a
# dependent task spawned before its dependency is merged would never see that
# dependency's code.
#
# Conflicts are reported, never auto-resolved. A merge Foreman cannot do cleanly
# is a decision for the manager or the human.
set -euo pipefail

NAME=""; ROOT=".foreman"; BASE=""; KEEP="no"
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

ROOT="$(cd "$(dirname "$ROOT")" && pwd)/$(basename "$ROOT")"
PROJECT="$(dirname "$ROOT")"
BRANCH="foreman/$NAME"
WT="$PROJECT/.claude/worktrees/foreman-$NAME"

cd "$PROJECT"
git rev-parse --git-dir >/dev/null 2>&1 || { echo "integrate.sh: not a git repo" >&2; exit 2; }
git show-ref --verify --quiet "refs/heads/$BRANCH" || {
  echo "integrate.sh: no branch $BRANCH — nothing to integrate"; exit 0; }

[[ -n "$BASE" ]] || BASE="$(git rev-parse --abbrev-ref HEAD)"
[[ "$BASE" != "$BRANCH" ]] || { echo "integrate.sh: base and worker branch are the same" >&2; exit 2; }

# A worker may have left changes uncommitted in its worktree; commit them so the
# merge carries everything it produced rather than silently dropping it.
if [[ -d "$WT" ]] && [[ -n "$(git -C "$WT" status --porcelain)" ]]; then
  echo "integrate.sh: committing uncommitted work left in $NAME's worktree"
  git -C "$WT" add -A
  git -C "$WT" commit -q -m "foreman($NAME): work in progress at integration" || true
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "integrate.sh: base branch '$BASE' has uncommitted changes. Commit or stash first." >&2
  exit 1
fi

git checkout -q "$BASE"
if git merge --no-ff --no-edit -m "foreman: integrate $NAME" "$BRANCH" >/tmp/foreman-merge-$$.log 2>&1; then
  echo "integrated $NAME into $BASE"
  rm -f /tmp/foreman-merge-$$.log
else
  CONFLICTS="$(git diff --name-only --diff-filter=U | tr '\n' ' ')"
  git merge --abort 2>/dev/null || true
  echo "integrate.sh: MERGE CONFLICT integrating $NAME into $BASE" >&2
  echo "  conflicting files: ${CONFLICTS:-unknown}" >&2
  echo "  the merge was aborted; $BASE is unchanged and $BRANCH still holds the work" >&2
  echo "  two tasks touched the same files — this is a planning error, not a code error" >&2
  rm -f /tmp/foreman-merge-$$.log
  exit 1
fi

if [[ "$KEEP" == "no" ]]; then
  [[ -d "$WT" ]] && git worktree remove --force "$WT" 2>/dev/null || true
  git branch -q -d "$BRANCH" 2>/dev/null || git branch -q -D "$BRANCH" 2>/dev/null || true
  echo "cleaned up worktree and branch for $NAME"
fi
