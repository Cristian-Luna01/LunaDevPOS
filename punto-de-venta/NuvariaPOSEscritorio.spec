# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['native_desktop.py'],
    pathex=[],
    binaries=[],
    datas=[('static', 'static'), ('schema.sql', '.'), ('vendor','vendor')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Do not bundle foreign ICU or Windows API-set DLLs from build-tool PATH.
a.binaries = [entry for entry in a.binaries if entry[0].lower() not in ('icuuc.dll','icudt78.dll') and not entry[0].lower().startswith(('api-ms-win-core-','ext-ms-win-'))]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NuvariaPOSEscritorio',
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
    name='NuvariaPOSEscritorio',
)


