#!/bin/bash
# Full-domain multi-sigma batch; shared gradients/FFTs are mapped to disk.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="$PWD/.venv-mac/bin/python"
CONFIG="${JHTDB_MAIN_CONFIG:-$PWD/configs/pipeline.macos.yaml}"
export MPLCONFIGDIR="$PWD/.local/cache/matplotlib"
# scipy.fft uses its explicit workers; keep unrelated BLAS pools from oversubscribing.
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
mkdir -p "$MPLCONFIGDIR"
exec caffeinate -i "$PYTHON" -u -m jhtdb_pipeline process-batch \
  --time-index 1 --config "$CONFIG"
