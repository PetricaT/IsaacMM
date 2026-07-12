#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

if command -v uv &>/dev/null; then
    if [ ! -d .venv ]; then
        uv venv
    fi
    source .venv/bin/activate
    uv pip install -r requirements.txt pyinstaller
else
    pip install -r requirements.txt pyinstaller
fi

APPNAME="IsaacMM"
APPDIR="${APPNAME}.AppDir"

pyinstaller packaging/appimage/IsaacMM-Linux.spec

# Build AppImage ----------------------------------------------------------
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"

cp -r "dist/IsaacMM-Linux/"* "${APPDIR}/usr/bin/"

# Bundle appimageupdatetool for delta self-updates
if [ ! -f appimageupdatetool ]; then
    wget -q "https://github.com/AppImageCommunity/AppImageUpdate/releases/download/continuous/appimageupdatetool-x86_64.AppImage" -O appimageupdatetool
    chmod +x appimageupdatetool
fi
cp appimageupdatetool "${APPDIR}/usr/bin/appimageupdatetool"
chmod +x "${APPDIR}/usr/bin/appimageupdatetool"

cat > "${APPDIR}/AppRun" << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/IsaacMM-Linux.elf" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

cp packaging/shared/IsaacMM-appimage.desktop "${APPDIR}/IsaacMM.desktop"
cp assets/icon.png "${APPDIR}/IsaacMM.png"

if ! command -v appimagetool &>/dev/null && [ ! -f appimagetool ]; then
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O appimagetool
    chmod +x appimagetool
fi

APPIMAGETOOL=$(command -v appimagetool || echo "./appimagetool")

# Embed update information so appimageupdatetool can do delta updates
export UPD_INFO="gh-releases-zsync|PetricaT|IsaacMM|latest|IsaacMM-*x86_64.AppImage.zsync"
export ARCH=x86_64
APPIMAGE_EXTRACT_AND_RUN=1 "${APPIMAGETOOL}" --updateinformation "${UPD_INFO}" "${APPDIR}" "${APPNAME}-x86_64.AppImage"

rm -rf "${APPDIR}"
echo "Created ${APPNAME}-x86_64.AppImage"

# Generate .zsync for delta updates
if command -v zsyncmake &>/dev/null; then
    zsyncmake "${APPNAME}-x86_64.AppImage"
    echo "Created ${APPNAME}-x86_64.AppImage.zsync"
else
    echo "WARNING: zsyncmake not found, skipping .zsync generation"
fi
