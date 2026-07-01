# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files


sdl3_bins = collect_dynamic_libs("sdl3")
sdl3_data = collect_data_files("sdl3")

a = Analysis(
    ["../../main.py"],
    pathex=["../.."],
    binaries=sdl3_bins + sdl3_data,
    datas=[
        ("../../masterlist.yaml", "."),
        ("../../pyproject.toml", "."),
        ("../../assets/icon.icns", "assets"),
        ("../../assets/ui/no_image.png", "assets/ui"),
        ("../../assets/ui/warning.png", "assets/ui"),
        ("../../assets/ui/folder-yellow.png", "assets/ui"),
        ("../../assets/styles.qss", "assets"),
        ("../../assets/ui/empty.png", "assets/ui"),
        ("../../assets/controller", "assets/controller"),
    ],
    hiddenimports=[
        "source.paths",
        "source.config",
        "source.models",
        "source.widgets",
        "source.window",
        "source.sorter",
        "toml",
        "yaml",
        "sdl3",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IsaacMM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["../../assets/icon.icns"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="IsaacMM",
)

app = BUNDLE(
    coll,
    name="IsaacMM.app",
    icon="../../assets/icon.icns",
    bundle_identifier="io.github.PetricaT.IsaacMM",
)
