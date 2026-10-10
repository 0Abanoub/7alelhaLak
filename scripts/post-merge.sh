#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Reconcile dependencies using Replit's configured Python environment.
# No virtual environment, data migrations, or application changes are needed.
python -m pip install --prefix "$PWD/.pythonlibs" \
    --no-input --disable-pip-version-check -r requirements.txt
