#!/usr/bin/env bash
# Launch one Foreman worker session.
#
#   spawn.sh --name dev-m01-03 --agent foreman-developer --brief path/to/brief.md \
#            [--root .foreman] [--budget 15] [--turns 120] [--deadline 60] \
#            [--model opus] [--effort high] [--worktree yes|no]
#
# Workers are `claude -p` processes, not `claude --bg` sessions: --max-budget-usd,
# --max-turns and --output-format are print-mode only, and --bg refuses to combine
# with -p. The captured stream-json is what supervise.py reads for context and cost.
set -euo pipefail

NAME=""; AGENT="foreman-developer"; BRIEF=""; ROOT=".foreman"
BUDGET=15; TURNS=120; DEADLINE=60; MODEL="opus"; EFFORT="high"; WORKTREE="yes"
COMPACT_PCT="${FOREMAN_COMPACT_PCT:-55}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)     NAME="$2"; shift 2 ;;
    --agent)    AGENT="$2"; shift 2 ;;
    --brief)    BRIEF="$2"; shift 2 ;;
    --root)     ROOT="$2"; shift 2 ;;
    --budget)   BUDGET="$2"; shift 2 ;;
    --turns)    TURNS="$2"; shift 2 ;;
    --deadline) DEADLINE="$2"; shift 2 ;;
    --model)    MODEL="$2"; shift 2 ;;
    --effort)   EFFORT="$2"; shift 2 ;;
    --worktree) WORKTREE="$2"; shift 2 ;;
    *) echo "spawn.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$NAME"  ]] || { echo "spawn.sh: --name is required" >&2; exit 2; }
[[ -n "$BRIEF" ]] || { echo "spawn.sh: --brief is required" >&2; exit 2; }
[[ -f "$BRIEF" ]] || { echo "spawn.sh: brief not found: $BRIEF" >&2; exit 2; }

ROOT="$(cd "$(dirname "$ROOT")" && pwd)/$(basename "$ROOT")"
PROJECT_DIR="$(dirname "$ROOT")"
# Session state is scratchpad, not provenance: it churns every sweep and the
# durable record is the task file's Activity log.
SDIR="$ROOT/work/sessions/$NAME"
mkdir -p "$SDIR"

SESSION_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
STARTED=$(date +%s)
DEADLINE_TS=$(( STARTED + DEADLINE * 60 ))

# Isolate in a worktree so a fully autonomous worker cannot damage the main
# checkout. Created explicitly rather than via --worktree, whose interaction with
# -p is unverified; doing it here also gives us the path deterministically.
CWD="$PROJECT_DIR"
BRANCH=""
if [[ "$WORKTREE" == "yes" ]] && git -C "$PROJECT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  # A worktree is a fresh checkout of the branch, so anything uncommitted is
  # invisible inside it. .foreman/ is almost always uncommitted at spawn time,
  # which would hand the worker a tree with no task file, no constitution and no
  # glossary — it cannot do its job and is right to refuse. Commit the tracked
  # half first. work/ is gitignored, so this only ever picks up real artefacts.
  # .gitignore is included because it carries the worktree exclusion — leaving it
  # untracked is how a worker worktree eventually gets committed by accident.
  if [[ -n "$(git -C "$PROJECT_DIR" status --porcelain -- .foreman .gitignore)" ]]; then
    git -C "$PROJECT_DIR" add -A -- .foreman .gitignore
    git -C "$PROJECT_DIR" commit -q -m "foreman: bookkeeping before spawning $NAME" || true
  fi
  WT="$PROJECT_DIR/.claude/worktrees/foreman-$NAME"
  BRANCH="foreman/$NAME"
  if [[ ! -d "$WT" ]]; then
    mkdir -p "$(dirname "$WT")"
    git -C "$PROJECT_DIR" worktree add -q -b "$BRANCH" "$WT" 2>/dev/null \
      || git -C "$PROJECT_DIR" worktree add -q "$WT" "$BRANCH"
  fi
  CWD="$WT"
fi

# The manager normally writes the brief straight to its canonical path, so
# copying it onto itself would abort the script under set -e.
if [[ "$(cd "$(dirname "$BRIEF")" && pwd)/$(basename "$BRIEF")" != "$SDIR/brief.md" ]]; then
  cp "$BRIEF" "$SDIR/brief.md"
fi

# The worker runs in the worktree, so "your session directory" must be absolute —
# a relative path would land inside the worktree, where the supervisor and the
# handover hook never look.
if ! grep -q "## Where to write your working files" "$SDIR/brief.md"; then
cat >> "$SDIR/brief.md" <<BRIEF

## Where to write your working files
Your session directory is \`$SDIR\`. Use that absolute path.
- progress notes  -> \`$SDIR/progress.md\`
- anything else you want the manager to see -> the same directory

The project root for this task is \`$CWD\` (your own git worktree on branch
\`$BRANCH\`). Task files, the constitution and the glossary are under
\`$CWD/.foreman/\` — read them there, and update the task file there.
BRIEF
fi

# crossSessionInbound:accept is REQUIRED. Without it an unattended worker holds
# the manager's SendMessage poke behind a dialog nobody can answer, and it simply
# expires after dialogExpiry.
SETTINGS='{"crossSessionInbound":"accept"}'

cd "$CWD"
CLAUDE_AUTOCOMPACT_PCT_OVERRIDE="$COMPACT_PCT" \
FOREMAN_SESSION_DIR="$SDIR" \
FOREMAN_ROOT="$ROOT" \
nohup claude -p "$(cat "$SDIR/brief.md")" \
  --output-format stream-json --verbose \
  --agent "$AGENT" \
  --permission-mode bypassPermissions \
  --max-budget-usd "$BUDGET" \
  --max-turns "$TURNS" \
  --model "$MODEL" \
  --effort "$EFFORT" \
  --name "$NAME" \
  --session-id "$SESSION_ID" \
  --settings "$SETTINGS" \
  >"$SDIR/stream.jsonl" 2>"$SDIR/stderr.log" &
PID=$!

cat > "$SDIR/status.json" <<JSON
{
  "name": "$NAME",
  "agent": "$AGENT",
  "pid": $PID,
  "session_id": "$SESSION_ID",
  "cwd": "$CWD",
  "branch": "$BRANCH",
  "started_at": $STARTED,
  "deadline_ts": $DEADLINE_TS,
  "budget_usd": $BUDGET,
  "max_turns": $TURNS,
  "compact_pct": $COMPACT_PCT,
  "state": "running",
  "pokes": 0
}
JSON

echo "spawned $NAME  pid=$PID  session=$SESSION_ID  cwd=$CWD"
