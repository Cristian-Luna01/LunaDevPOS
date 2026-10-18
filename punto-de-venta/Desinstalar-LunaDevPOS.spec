a = Analysis(['uninstaller.py'],pathex=[],binaries=[],datas=[('schema.sql','.')],hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['PySide6','PyInstaller'],noarchive=False,optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,a.binaries,a.datas,[],name='Desinstalar-LunaDevPOS',debug=False,bootloader_ignore_signals=False,strip=False,upx=True,upx_exclude=[],runtime_tmpdir=None,console=False)
