#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

# A separate environment avoids accidentally reusing a copied Windows .venv.
if [ ! -x .venv-mac/bin/python ]; then
    python3 -m venv .venv-mac
fi
.venv-mac/bin/python -m pip install -e .

export JHTDB_MAC_ROOT="${JHTDB_MAC_ROOT:-$HOME/JHTDB_DOWNLOAD}"
case "$JHTDB_MAC_ROOT" in
    /*) ;;
    *) echo 'JHTDB_MAC_ROOT must be an absolute path.' >&2; exit 1 ;;
esac
if [ -z "${JHTDB_TOKEN:-}" ]; then
    read -r -s -p 'JHTDB token (hidden): ' JHTDB_TOKEN
    printf '\n'
    export JHTDB_TOKEN
fi
if [ -z "$JHTDB_TOKEN" ]; then
    echo 'An empty token cannot be used.' >&2
    exit 1
fi

# Download and validate only; no qpower or multi-sigma computation.
caffeinate -i .venv-mac/bin/python -m jhtdb_pipeline cache \
    --field pressure_gradient --time-index 1 --config configs/mac_download.yaml

printf '\nDownload and validation completed. Data: %s/state\n' "$JHTDB_MAC_ROOT"
printf 'Follow docs/mac_download_transfer.md to transfer to Windows.\n'
