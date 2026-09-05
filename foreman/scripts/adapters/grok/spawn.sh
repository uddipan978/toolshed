#!/usr/bin/env bash
# Launch one Foreman worker on Grok Build.
#
#   spawn.sh --name dev-m01-03 --agent foreman-developer --brief path/to/brief.md \
#            [--root .foreman] [--budget 15] [--turns 120] [--deadline 60] \
#            [--model grok-4.6] [--effort high] [--worktree yes|no] [--base ref]
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
BASE=""
COMPACT_PCT="${FOREMAN_COMPACT_PCT:-55}"
ADAPTER_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$(cd "$ADAPTER_DIR/../.." && pwd)"
if [[ "${FOREMAN_MANAGED_LAUNCH:-}" != "1" ]]; then
  FOREMAN_HARNESS=grok exec python3 "$SCRIPTS_DIR/dispatch.py" "$@"
fi

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
    --base)     BASE="$2"; shift 2 ;;
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

SESSION_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
STARTED=$(date +%s)
DEADLINE_TS=$(( STARTED + DEADLINE * 60 ))

# Centralised preparation keeps the Claude and Grok ancestry rules identical.
PREP_ARGS=(prepare --project "$PROJECT_DIR" --root "$ROOT" --name "$NAME"
  --agent "$AGENT" --harness grok --worktree "$WORKTREE")
[[ -n "$BASE" ]] && PREP_ARGS+=(--base "$BASE")
python3 "$SCRIPTS_DIR/worktree.py" "${PREP_ARGS[@]}" > "$SDIR/worktree.json"

json_field() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))' \
    "$SDIR/worktree.json" "$1"
}
CWD="$(json_field cwd)"
BRANCH="$(json_field branch)"
BASE_REF="$(json_field base_ref)"
BASE_COMMIT="$(json_field base_commit)"

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
\`$BRANCH\`). This branch was verified to contain base \`$BASE_REF\` at
\`$BASE_COMMIT\`. Task files, the constitution and the glossary are under
\`$CWD/.foreman/\` — read them there, and update the task file there.

Before reporting done, commit task-scoped repository changes with explicit paths.
Never use \`git add -A\`; the Stop gate rejects a dirty worktree.
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

python3 - "$SDIR/status.json" "$SDIR/worktree.json" "$NAME" "$AGENT" \
  "$SESSION_ID" "$ROOT" "$STARTED" "$DEADLINE_TS" "$BUDGET" "$TURNS" \
  "$COMPACT_PCT" <<'PY'
import json, os, sys
(out, prep_path, name, agent, session_id, root, started, deadline,
 budget, turns, compact) = sys.argv[1:]
prep = json.load(open(prep_path))
status = {
    "name": name, "agent": agent, "pid": 0, "session_id": session_id,
    "cwd": prep["cwd"], "branch": prep["branch"], "root": root,
    "base_ref": prep["base_ref"], "base_commit": prep["base_commit"],
    "start_commit": prep["start_commit"],
    "lineage_start_commit": prep["lineage_start_commit"],
    "base_session": prep.get("base_session", ""),
    "started_at": int(started), "deadline_ts": int(deadline),
    "budget_usd": float(budget), "max_turns": int(turns),
    "compact_pct": float(compact), "state": "starting", "pokes": 0,
    "harness": "grok",
    "task_ids": os.environ.get("FOREMAN_TASK_IDS", "").split(",") if os.environ.get("FOREMAN_TASK_IDS") else [],
    "sprint": os.environ.get("FOREMAN_SPRINT", ""),
}
open(out, "w").write(json.dumps(status, indent=2) + "\n")
PY

cd "$CWD"
FOREMAN_SESSION_DIR="$SDIR" \
FOREMAN_ROOT="$ROOT" \
FOREMAN_WORKTREE_ROOT="$CWD" \
FOREMAN_HARNESS=grok \
GROK_ASK_USER_QUESTION_TIMEOUT_SECS=300 \
nohup python3 "$SCRIPTS_DIR/runner.py" --session-dir "$SDIR" -- grok "${GROK_ARGS[@]}" \
  >"$SDIR/stream.jsonl" 2>"$SDIR/stderr.log" &
PID=$!

python3 - "$SCRIPTS_DIR" "$SDIR" "$PID" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from ops import update_session
update_session(Path(sys.argv[2]), runner_pid=int(sys.argv[3]))
PY

echo "spawned $NAME  pid=$PID  session=$SESSION_ID  cwd=$CWD  base=$BASE_REF  harness=grok"
