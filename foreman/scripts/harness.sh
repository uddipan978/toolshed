# Shared harness detection for spawn.sh. Source this file; do not execute it.
# The Python twin is detect_harness() in foreman_lib.py — keep the order in sync.
foreman_detect() {
  local root="${1:-}" here
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  python3 - "$here" "$root" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from foreman_lib import detect_harness
root = sys.argv[2]
print(detect_harness(Path(root) if root else None))
PY
}
