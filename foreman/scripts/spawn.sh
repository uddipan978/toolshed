#!/usr/bin/env bash
# Dispatch to the Claude or Grok spawn adapter.
#
# Same flags as before. Which adapter runs is detect_harness() — override with
# FOREMAN_HARNESS=claude|grok. Claude is the default so existing installs
# keep launching `claude -p`.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=harness.sh
source "$HERE/harness.sh"

ROOT_ARG=".foreman"
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  if [[ "${args[i]}" == "--root" && $((i + 1)) -lt ${#args[@]} ]]; then
    ROOT_ARG="${args[i+1]}"
    break
  fi
done
if [[ -d "$ROOT_ARG" ]]; then
  ROOT_ABS="$(cd "$(dirname "$ROOT_ARG")" && pwd)/$(basename "$ROOT_ARG")"
else
  ROOT_ABS="$ROOT_ARG"
fi

HARNESS="$(foreman_detect "$ROOT_ABS")"
ADAPTER="$HERE/adapters/$HARNESS/spawn.sh"
[[ -x "$ADAPTER" ]] || { echo "spawn.sh: no adapter for harness '$HARNESS' ($ADAPTER)" >&2; exit 2; }
exec python3 "$HERE/dispatch.py" "$@"
