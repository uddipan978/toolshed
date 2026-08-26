#!/usr/bin/env bash
# Launch one Foreman worker on Grok Build.
#
#   spawn.sh --name dev-m01-03 --agent foreman-developer --brief path/to/brief.md \
#            [--root .foreman] [--budget 15] [--turns 120] [--deadline 60] \
#            [--model grok-4.6] [--effort high] [--worktree yes|no]
#
# Workers are `grok -p` processes. `--output-format streaming-messages-json`
# is the Messages-shaped stream supervise.py already knows how to read.
# Grok has no --max-budget-usd; budget is recorded in status.json and the
# supervisor emits BUDGET when captured spend crosses it.
#
# Headless `-p` does not honour `--worktree`, so this script creates the
# worktree itself (same reason the Claude adapter does).
set -euo pipefail

NAME=""; AGENT="foreman-developer"; BRIEF=""; ROOT=".foreman"
BUDGET=15; TURNS=120; DEADLINE=60; MODEL=""; EFFORT="high"; WORKTREE="yes"
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
command -v grok >/dev/null || { echo "spawn.sh: grok is not on PATH" >&2; exit 2; }

ROOT="$(cd "$(dirname "$ROOT")" && pwd)/$(basename "$ROOT")"
PROJECT_DIR="$(dirname "$ROOT")"
SDIR="$ROOT/work/sessions/$NAME"
mkdir -p "$SDIR"

SESSION_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
STARTED=$(date +%s)
DEADLINE_TS=$(( STARTED + DEADLINE * 60 ))

CWD="$PROJECT_DIR"
BRANCH=""
if [[ "$WORKTREE" == "yes" ]] && git -C "$PROJECT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  bookkeeping_commit() {
    local project="$1" msg="$2"
    local tmpindex tree parent head_tree
    tmpindex="$(mktemp)"
    if ! GIT_INDEX_FILE="$tmpindex" git -C "$project" read-tree HEAD; then
      rm -f "$tmpindex"
      echo "spawn.sh: cannot read HEAD — need a git repo with at least one commit" >&2
      return 1
    fi
    local paths=()
    [[ -d "$project/.foreman" ]] && paths+=(.foreman)
    [[ -f "$project/.gitignore" ]] && paths+=(.gitignore)
    if [[ ${#paths[@]} -gt 0 ]]; then
      if ! GIT_INDEX_FILE="$tmpindex" git -C "$project" add -A -- "${paths[@]}"; then
        rm -f "$tmpindex"
        echo "spawn.sh: failed to stage .foreman for the worker snapshot" >&2
        return 1
      fi
    fi
    tree="$(GIT_INDEX_FILE="$tmpindex" git -C "$project" write-tree)" || {
      rm -f "$tmpindex"; echo "spawn.sh: write-tree failed" >&2; return 1
    }
    rm -f "$tmpindex"
    parent="$(git -C "$project" rev-parse HEAD)"
    head_tree="$(git -C "$project" rev-parse "HEAD^{tree}")"
    if [[ "$tree" == "$head_tree" ]]; then
      echo "$parent"
      return 0
    fi
    git -C "$project" commit-tree "$tree" -p "$parent" -m "$msg" || {
      echo "spawn.sh: failed to write bookkeeping commit for the worker" >&2
      return 1
    }
  }
  WT="$PROJECT_DIR/.grok/worktrees/foreman-$NAME"
  BRANCH="foreman/$NAME"
  if [[ ! -d "$WT" ]]; then
    mkdir -p "$(dirname "$WT")"
    BASE="$(bookkeeping_commit "$PROJECT_DIR" "foreman: bookkeeping before spawning $NAME")" || exit 1
    git -C "$PROJECT_DIR" worktree add -q -b "$BRANCH" "$WT" "$BASE" 2>/dev/null \
      || git -C "$PROJECT_DIR" worktree add -q "$WT" "$BRANCH"
  fi
  CWD="$WT"
fi

if [[ "$(cd "$(dirname "$BRIEF")" && pwd)/$(basename "$BRIEF")" != "$SDIR/brief.md" ]]; then
  cp "$BRIEF" "$SDIR/brief.md"
fi

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

# Plugin agents load as foreman:<name>. Pass the file if the qualified name
# is not how this install registered them.
if [[ "$AGENT" == *:* ]]; then
  AGENT_ARG="$AGENT"
else
  AGENT_ARG="foreman:${AGENT}"
fi

GROK_ARGS=(
  --prompt-file "$SDIR/brief.md"
  --output-format streaming-messages-json
  --agent "$AGENT_ARG"
  --permission-mode bypassPermissions
  --always-approve
  --max-turns "$TURNS"
  --effort "$EFFORT"
  --session-id "$SESSION_ID"
  --cwd "$CWD"
  --no-subagents
)
[[ -n "$MODEL" ]] && GROK_ARGS+=(--model "$MODEL")

cd "$CWD"
FOREMAN_SESSION_DIR="$SDIR" \
FOREMAN_ROOT="$ROOT" \
FOREMAN_HARNESS=grok \
GROK_ASK_USER_QUESTION_TIMEOUT_SECS=300 \
nohup grok "${GROK_ARGS[@]}" \
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
  "pokes": 0,
  "harness": "grok"
}
JSON

echo "spawned $NAME  pid=$PID  session=$SESSION_ID  cwd=$CWD  harness=grok"
