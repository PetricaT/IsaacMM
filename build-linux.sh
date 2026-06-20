#!/usr/bin/env bash
set -euo pipefail

APPNAME="IsaacMM"
APPDIR="${APPNAME}.AppDir"

uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install pyinstaller
pyinstaller IsaacMM-Linux.spec

# Build AppImage ----------------------------------------------------------
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"

# Copy PyInstaller bundle into AppDir
cp -r "dist/${APPNAME}-Linux/"* "${APPDIR}/usr/bin/"

# AppRun entry point
cat > "${APPDIR}/AppRun" << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/IsaacMM-Linux.elf" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

# Desktop file + icon
cp IsaacMM.desktop "${APPDIR}/"
cp assets/icon.png "${APPDIR}/IsaacMM.png"

# Download appimagetool if needed
if ! command -v appimagetool &>/dev/null && [ ! -f appimagetool ]; then
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O appimagetool
    chmod +x appimagetool
fi

APPIMAGETOOL=$(command -v appimagetool || echo "./appimagetool")

export ARCH=x86_64
"${APPIMAGETOOL}" "${APPDIR}" "${APPNAME}-x86_64.AppImage"

rm -rf "${APPDIR}"
echo "Created ${APPNAME}-x86_64.AppImage"
