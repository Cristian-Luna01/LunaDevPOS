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
    excludes=['tkinter', '_tkinter', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtOpenGL'],
    noarchive=False,
    optimize=0,
)
# Do not bundle foreign ICU or Windows API-set DLLs from build-tool PATH.
a.binaries = [entry for entry in a.binaries if entry[0].lower() not in ('icuuc.dll','icudt78.dll') and not entry[0].lower().startswith(('api-ms-win-core-','ext-ms-win-'))]
# This application uses Qt Widgets/WebEngine, not QML. Keep Spanish and English UI resources.
def keep_language(entry):
    name = entry[0].replace('\\', '/').lower()
    if '/translations/qtwebengine_locales/' in name:
        return name.rsplit('/', 1)[-1] in ('es.pak', 'es-419.pak', 'en-us.pak', 'en-gb.pak')
    if '/translations/' in name and name.endswith('.qm'):
        stem = name.rsplit('/', 1)[-1][:-3]
        return stem.endswith(('_es', '_en')) or '_es_' in stem or '_en_' in stem
    return True
a.datas = [entry for entry in a.datas if keep_language(entry)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LunaDevPOS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name='LunaDevPOS',
)


