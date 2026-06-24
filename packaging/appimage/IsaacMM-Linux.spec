# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ["../../main.py"],
    pathex=["../.."],
    binaries=[],
    datas=[
        ("../../masterlist.yaml", "."),
        ("../../pyproject.toml", "."),
        ("../../assets/icon.png", "assets"),
        ("../../assets/no_image.png", "assets"),
        ("../../assets/warning.png", "assets"),
        ("../../assets/folder-yellow.png", "assets"),
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
    name="IsaacMM-Linux.elf",
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
    icon=["../../assets/icon.png"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="IsaacMM-Linux",
)
