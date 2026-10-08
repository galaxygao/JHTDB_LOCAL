#!/bin/bash
# Full-domain multi-sigma batch; shared gradients/FFTs are mapped to disk.
set -euo pipefail
TIME_INDEX="${1:-1}"
if [[ "$#" -gt 1 || ! "$TIME_INDEX" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: bash scripts/run_main_macos.sh [positive-time-index]" >&2
  exit 2
fi
cd "$(dirname "$0")/.."
PYTHON="$PWD/.venv-mac/bin/python"
CONFIG="${JHTDB_MAIN_CONFIG:-$PWD/configs/pipeline.macos.yaml}"
printf 'Starting full-domain process-batch: time-index=%s config=%s\n' "$TIME_INDEX" "$CONFIG"
exec caffeinate -i "$PYTHON" -u -m jhtdb_pipeline process-batch \
  --time-index "$TIME_INDEX" --config "$CONFIG"
