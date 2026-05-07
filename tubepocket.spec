# SPDX-License-Identifier: GPL-3.0-only

# Build with:
#   uv run pyinstaller tubepocket.spec

from PyInstaller.utils.hooks import collect_submodules


a = Analysis(
    ["src/tubepocket/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("tkinter"),
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
    [],
    exclude_binaries=True,
    name="TubePocket",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TubePocket",
)

