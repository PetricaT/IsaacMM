#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
    uv venv
fi
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install pyinstaller

VERSION=$(python3 -c "import toml; print(toml.load('pyproject.toml')['project']['version'])")

pyinstaller IsaacMM-MacOS.spec

mv "dist/IsaacMM-MacOS.app" "dist/IsaacMM-${VERSION}-MacOS.app"
echo "Created dist/IsaacMM-${VERSION}-MacOS.app"
