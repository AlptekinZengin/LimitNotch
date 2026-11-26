# -*- mode: python ; coding: utf-8 -*-
"""LimitNotch tek dosya (.exe) PyInstaller yapılandırması."""

a = Analysis(
    ["limit_cubugu.pyw"],
    pathex=["."],
    binaries=[],
    datas=[("assets/limitnotch.ico", "assets")],
    hiddenimports=[
        "baglayicilar",
        "baglayicilar.taban",
        "baglayicilar.claude",
        "baglayicilar.codex",
        "baglayicilar.antigravity",
        "baglayicilar.copilot",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageTk",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="LimitNotch",
    icon="assets/limitnotch.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
