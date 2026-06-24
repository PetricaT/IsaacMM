#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

if [ ! -d .venv ]; then
    uv venv
fi
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install pyinstaller

VERSION=$(python3 -c "import toml; print(toml.load('pyproject.toml')['project']['version'])")

pyinstaller packaging/macos/IsaacMM-MacOS.spec

mkdir -p dmg
cp -r "dist/IsaacMM.app" "dmg/IsaacMM.app"
ln -s /Applications dmg/Applications
hdiutil create -volname "IsaacMM" -srcfolder dmg -ov -format UDZO "dist/IsaacMM-${VERSION}-MacOS.dmg"

rm -rf dmg
echo "Created dist/IsaacMM-${VERSION}-MacOS.dmg"
