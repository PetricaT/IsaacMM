#!/usr/bin/env bash
set -euo pipefail

uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install pyinstaller
pyinstaller IsaacMM-MacOS.spec

echo "Created dist/IsaacMM-MacOS.app"
