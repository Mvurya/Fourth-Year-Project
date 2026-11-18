#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ -x .venv/bin/python ]]; then
  shopflow_python=.venv/bin/python
elif [[ -x /Users/newton/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ]]; then
  shopflow_python=/Users/newton/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
else
  shopflow_python=python3
fi
if ! "$shopflow_python" -c 'import numpy, pandas, openpyxl' 2>/dev/null; then
  echo 'Install dependencies first using the instructions in README.md.'
  read 'reply?Press Return to close.'
  exit 1
fi
export SHOPFLOW_OPEN_BROWSER=1
"$shopflow_python" server.py
if [[ $? -ne 0 ]]; then
  echo 'Could not start ShopFlow. If port 8000 is busy, stop the existing server first.'
  read 'reply?Press Return to close.'
fi
