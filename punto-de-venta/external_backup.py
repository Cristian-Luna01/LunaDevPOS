"""Respaldos fuera de la carpeta de datos, verificación y prueba de restauración."""
import base64
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import threading
from core import Error, fingerprint

def config_path(pos):return Path(pos.path).parent/'respaldos-config.json'

def atomic_write(target,raw):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    handle,name=tempfile.mkstemp(prefix='.lunadev-',suffix='.tmp',dir=target.parent)
    try:
        with os.fdopen(handle,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(name,target)
    finally:
        Path(name).unlink(missing_ok=True)

def settings(pos):
    try:
        data=json.loads(config_path(pos).read_text(encoding='utf-8'))
    except FileNotFoundError:data={}
    return {'directory':data.get('directory',''),'interval_minutes':30,**data}

def save_settings(pos,uid,data):
    with pos.db() as db:pos.require(db,uid,'backup.manage')
    value=data.get('directory','')
    if not isinstance(value,str) or len(value)>1000:raise Error('Ruta no válida')
    if value:
        target=Path(value)
        if not target.is_absolute():raise Error('Elige una ruta completa de USB, otro disco o una carpeta sincronizada')
        target=target.resolve();source=Path(pos.path).parent.resolve()
        if target==source or target.is_relative_to(source):
            raise Error('El respaldo debe guardarse fuera de la carpeta de datos')
        if target==Path(target.anchor):raise Error('Elige una carpeta de respaldos, no la raíz del disco')
        target.mkdir(parents=True,exist_ok=True)
        descriptor,probe=tempfile.mkstemp(prefix='.prueba-lunadev-',dir=target)
        os.close(descriptor);Path(probe).unlink()
        value=str(target)
    atomic_write(config_path(pos),json.dumps({'directory':value}).encode())
    return settings(pos)

def verify_raw(raw):
    from inventory_io import read_backup
    document=read_backup({'file_base64':base64.b64encode(raw).decode()})
    return document

def restore_test(raw):
    from core import POS
    from inventory_io import restore
    original=verify_raw(raw)
    with tempfile.TemporaryDirectory(prefix='lunadev-restauracion-') as directory:
        target=POS(Path(directory)/'test.sqlite3');target.initialize('verificador','verification-only-password')
        restore(target,1,{'file_base64':base64.b64encode(raw).decode(),'confirmation':'RESTAURAR'})
        with target.db() as db:
            for table,rows in original['tables'].items():
                if table=='audit_log':continue  # La restauración añade su propia entrada.
                if db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]!=len(rows):raise Error('La restauración no conserva '+table)
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise Error('Restauración no íntegra')
    return {'ok':True,'tables':len(original['tables']),'created_at':original['created_at']}

class BackupService:
    def __init__(self,pos):
        self.pos=pos;self.closed=threading.Event();self.lock=threading.Lock();self.thread=None
        self.status={'ok':False,'message':'Elige una carpeta externa para proteger tus datos.'}

    def run(self,verify_restore=False,raw=None):
        try:return self._run(verify_restore,raw)
        except OSError:
            self.status={'ok':False,'message':'No se pudo guardar el respaldo externo. Comprueba la unidad, el espacio y los permisos.'}
            raise Error(self.status['message'],503) from None

    def _run(self,verify_restore=False,raw=None):
        with self.lock:
            directory=settings(self.pos)['directory']
            if not directory:raise Error('Configura primero la carpeta de respaldos externos')
            from inventory_io import backup_document
            if raw is None:
                with self.pos.request_lock,self.pos.db() as db:raw,_,_=backup_document(db)
            verify_raw(raw)
            target=Path(directory)/('lunadev-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.botica.json')
            atomic_write(target,raw)
            saved=target.read_bytes();verify_raw(saved)
            if saved!=raw:raise Error('El archivo externo no coincide con el respaldo')
            checked=restore_test(saved) if verify_restore else None
            self.status={'ok':True,'message':'Respaldo externo verificado.','path':str(target),
                         'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'restore_test':checked,
                         'same_drive':target.drive.lower()==Path(self.pos.path).drive.lower()}
            atomic_write(config_path(self.pos).with_name('respaldos-estado.json'),json.dumps(self.status).encode())
            return self.status

    def start(self):
        if self.thread:return
        def run():
            while not self.closed.is_set():
                try:
                    if settings(self.pos)['directory']:self.run()
                except Exception:
                    self.status={'ok':False,'message':'No se pudo guardar el respaldo externo. Comprueba la unidad, el espacio y los permisos.'}
                self.closed.wait(1800)
        self.thread=threading.Thread(target=run,daemon=True);self.thread.start()

    def stop(self):
        self.closed.set()
        if self.thread:self.thread.join(timeout=5)
