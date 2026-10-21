# -*- mode: python ; coding: utf-8 -*-
import ssl
from pathlib import Path
runtime_ca=Path(ssl.__file__).with_name('codex-rejected-cas.pem')
runtime_data=[(str(runtime_ca),'.')] if runtime_ca.is_file() else []


a = Analysis(
    ['installer.py'],
    pathex=[],
    binaries=[],
    datas=[('programa.zip', '.'), ('schema.sql','.')]+runtime_data,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Instalar-LunaDevPOS',
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
)
