"""Instalación local y conservación de datos, sin operaciones en Cloudflare."""
from pathlib import Path
import os,shutil,datetime,json,uuid,sqlite3,contextlib
NAMES=('LunaDevPOS','NuvariaPOSEscritorioPrueba','NuvariaPOSPrueba')
REGISTRY_KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\LunaDevPOS'
def root():return Path(os.environ['LOCALAPPDATA'])
def known_data(base=None):return [(Path(base) if base else root())/name/'data' for name in NAMES]
def known_programs(base=None):return [(Path(base) if base else root())/'Programs'/name for name in NAMES]
def safe(path,allowed):
 path=Path(path)
 if path.absolute() not in [p.absolute() for p in allowed]:raise RuntimeError('Ruta fuera de los directorios de LunaDev POS')
 for ancestor in (path,*path.parents):
  if ancestor.is_symlink() or (hasattr(ancestor,'is_junction') and ancestor.is_junction()):raise RuntimeError('No se operará sobre enlaces o uniones de carpetas')
 if path.resolve()!=path.absolute():raise RuntimeError('Ruta resuelta inesperada')
 return path
def ensure_closed(base=None):
 for directory in known_data(base):
  safe(directory,known_data(base));lock=directory/'programa.lock'
  if lock.exists():
   import msvcrt
   with lock.open('r+b') as f:
    try:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
    except OSError:raise RuntimeError('Cierra los turnos, LunaDev POS y sus versiones anteriores antes de continuar.')
def portable(raw,destination):
 source=raw/'pos.sqlite3'
 if not source.exists():return None
 with contextlib.closing(sqlite3.connect(source)) as db:
  if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('El respaldo detectó una base dañada; se conserva la carpeta original.')
  if not db.execute("SELECT 1 FROM sqlite_master WHERE name='users'").fetchone():return None
  with contextlib.closing(sqlite3.connect(destination/'copia.sqlite3')) as copy:db.backup(copy)
 from core import POS
 import inventory_io
 pos=POS(destination/'copia.sqlite3')
 with pos.db() as db:ids=[r[0] for r in db.execute('SELECT id FROM users WHERE active=1')];uid=next((i for i in ids if 'backup.manage' in pos.permissions(db,i)),None)
 if uid is None:return 'Carpeta conservada; no hay cuenta activa con permiso para generar el respaldo portable.'
 body,name,mime=inventory_io.backup(pos,uid);(destination/name).write_bytes(body)
 return None
def archive_data(backup=None,base=None):
 ensure_closed(base);directories=[p for p in known_data(base) if p.exists()]
 if not directories:return None
 archive=Path(backup) if backup else Path.home()/'LunaDevPOS-Respaldos'/('antes-de-limpiar-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
 if archive.exists():raise RuntimeError('El destino del respaldo debe ser una carpeta nueva')
 for p in directories:
  safe(p,known_data(base))
  if archive.resolve().is_relative_to(p.resolve()):raise RuntimeError('El respaldo no puede quedar dentro de los datos que se van a retirar')
 archive.mkdir(parents=True);moved=[];notes=[]
 try:
  for source in directories:
   dest=archive/source.parent.name;dest.mkdir();raw=dest/'datos-originales'
   # Se mueve la carpeta completa: inventario, cuentas y vinculación no se pierden.
   source.rename(raw);moved.append((source,raw));note=portable(raw,dest)
   if note:notes.append(note)
  (archive/'LEEME.txt').write_text('Datos conservados antes de empezar de cero. Los archivos .botica.json se restauran desde Mantenimiento. Las carpetas datos-originales conservan también la vinculación anterior; no la actives antes de restaurar el negocio.\n'+'\n'.join(notes),encoding='utf-8')
 except Exception:
  for source,raw in reversed(moved):
   if raw.exists() and not source.exists():raw.rename(source)
  raise
 return archive
def register(target):
 import winreg
 target=safe(target,known_programs());exe=target/'Desinstalar-LunaDevPOS.exe'
 if not exe.exists():raise RuntimeError('Falta el desinstalador en el paquete')
 with winreg.CreateKey(winreg.HKEY_CURRENT_USER,REGISTRY_KEY) as key:
  values={'DisplayName':'LunaDev POS','DisplayVersion':__import__('build_info').VERSION,'Publisher':'LunaDev','InstallLocation':str(target),'DisplayIcon':str(target/'LunaDevPOS.exe'),'UninstallString':'"'+str(exe)+'"'}
  for name,value in values.items():winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)
  for name in ('NoModify','NoRepair'):winreg.SetValueEx(key,name,0,winreg.REG_DWORD,1)
  winreg.SetValueEx(key,'EstimatedSize',0,winreg.REG_DWORD,sum(p.stat().st_size for p in target.rglob('*') if p.is_file())//1024)
def uninstall(archive=False,backup=None,base=None,shortcuts=None,registry=True):
 ensure_closed(base);programs=[p for p in known_programs(base) if p.exists()]
 for p in programs:safe(p,known_programs(base))
 stored=archive_data(backup,base) if archive else None
 for p in programs:
  # Rutas absolutas comprobadas antes de cualquier retirada recursiva.
  checked=safe(p,known_programs(base));shutil.rmtree(checked)
 if shortcuts:
  for directory in shortcuts:
   for name in ('LunaDev POS.lnk','Nuvaria POS - Escritorio Prueba.lnk','Nuvaria POS - Prueba.lnk'):
    path=Path(directory)/name
    if path.exists():path.unlink()
 if registry:
  import winreg
  try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,REGISTRY_KEY)
  except FileNotFoundError:pass
 return stored
