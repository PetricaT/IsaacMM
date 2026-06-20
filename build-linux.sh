#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
    uv venv
fi
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install pyinstaller

VERSION=$(grep -Po '^version = "\K[^"]*' pyproject.toml)
APPNAME="IsaacMM-${VERSION}"
APPDIR="${APPNAME}.AppDir"

pyinstaller IsaacMM-Linux.spec

# Build AppImage ----------------------------------------------------------
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"

cp -r "dist/IsaacMM-Linux/"* "${APPDIR}/usr/bin/"

cat > "${APPDIR}/AppRun" << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/IsaacMM-Linux.elf" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

cp IsaacMM.desktop "${APPDIR}/"
cp assets/icon.png "${APPDIR}/IsaacMM.png"

if ! command -v appimagetool &>/dev/null && [ ! -f appimagetool ]; then
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O appimagetool
    chmod +x appimagetool
fi

APPIMAGETOOL=$(command -v appimagetool || echo "./appimagetool")

export ARCH=x86_64
"${APPIMAGETOOL}" --comp zstd "${APPDIR}" "${APPNAME}-x86_64.AppImage"

rm -rf "${APPDIR}"
echo "Created ${APPNAME}-x86_64.AppImage"
