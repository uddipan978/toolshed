#!/usr/bin/env bash
# Launch one Foreman worker session.
#
#   spawn.sh --name dev-m01-03 --agent foreman-developer --brief path/to/brief.md \
#            [--root .foreman] [--budget 15] [--turns 120] [--deadline 60] \
#            [--model opus] [--effort high] [--worktree yes|no] [--base ref]
#
# Workers are `claude -p` processes, not `claude --bg` sessions: --max-budget-usd,
# --max-turns and --output-format are print-mode only, and --bg refuses to combine
# with -p. The captured stream-json is what supervise.py reads for context and cost.
set -euo pipefail

NAME=""; AGENT="foreman-developer"; BRIEF=""; ROOT=".foreman"
BUDGET=15; TURNS=120; DEADLINE=60; MODEL="opus"; EFFORT="high"; WORKTREE="yes"
BASE=""
COMPACT_PCT="${FOREMAN_COMPACT_PCT:-55}"
ADAPTER_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$(cd "$ADAPTER_DIR/../.." && pwd)"

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

ROOT="$(cd "$(dirname "$ROOT")" && pwd)/$(basename "$ROOT")"
PROJECT_DIR="$(dirname "$ROOT")"
# Session state is scratchpad, not provenance: it churns every sweep and the
# durable record is the task file's Activity log.
SDIR="$ROOT/work/sessions/$NAME"
mkdir -p "$SDIR"

SESSION_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
STARTED=$(date +%s)
DEADLINE_TS=$(( STARTED + DEADLINE * 60 ))

# Centralised preparation keeps the Claude and Grok ancestry rules identical.
# Testers default to foreman/dev-<same suffix> and never silently fall back to
# project HEAD. A live, dirty, or empty predecessor is a hard launch failure.
PREP_ARGS=(prepare --project "$PROJECT_DIR" --root "$ROOT" --name "$NAME"
  --agent "$AGENT" --harness claude --worktree "$WORKTREE")
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
\`$BRANCH\`). This branch was verified to contain base \`$BASE_REF\` at
\`$BASE_COMMIT\`. Task files, the constitution and the glossary are under
\`$CWD/.foreman/\` — read them there, and update the task file there.

Before reporting done, commit task-scoped repository changes with explicit paths.
Never use \`git add -A\`; the Stop gate rejects a dirty worktree.
BRIEF
fi

# crossSessionInbound:accept is REQUIRED. Without it an unattended worker holds
# the manager's SendMessage poke behind a dialog nobody can answer, and it simply
# expires after dialogExpiry.
SETTINGS='{"crossSessionInbound":"accept"}'

# The Stop hook may run before a very short worker reaches its first tool call.
# Persist cwd/ancestry before launch so relative task paths always resolve in the
# worker worktree, never in the manager checkout.
python3 - "$SDIR/status.json" "$SDIR/worktree.json" "$NAME" "$AGENT" \
  "$SESSION_ID" "$ROOT" "$STARTED" "$DEADLINE_TS" "$BUDGET" "$TURNS" \
  "$COMPACT_PCT" <<'PY'
import json, sys
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
    "harness": "claude",
}
open(out, "w").write(json.dumps(status, indent=2) + "\n")
PY

cd "$CWD"
CLAUDE_AUTOCOMPACT_PCT_OVERRIDE="$COMPACT_PCT" \
FOREMAN_SESSION_DIR="$SDIR" \
FOREMAN_ROOT="$ROOT" \
FOREMAN_WORKTREE_ROOT="$CWD" \
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

python3 - "$SDIR/status.json" "$PID" <<'PY'
import json, os, sys
path, pid = sys.argv[1], int(sys.argv[2])
data = json.load(open(path))
data.update(pid=pid, state="running")
tmp = path + ".tmp"
open(tmp, "w").write(json.dumps(data, indent=2) + "\n")
os.replace(tmp, path)
PY

echo "spawned $NAME  pid=$PID  session=$SESSION_ID  cwd=$CWD  base=$BASE_REF"
