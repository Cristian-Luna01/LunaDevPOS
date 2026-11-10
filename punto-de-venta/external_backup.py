"""Destino externo opcional; solo archivos automáticos propios tienen retención."""
import datetime as dt
import hashlib,json,os,re
from pathlib import Path
from tempfile import NamedTemporaryFile
from backup_crypto import PORTABLE
from core import Error

def config_path(pos):return Path(pos.path).parent/'respaldo-externo.json'
def settings(pos):
    try:return json.loads(config_path(pos).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {'directory':''}
def configure(pos,directory):
    if not isinstance(directory,str):raise Error('Carpeta inválida')
    if directory:
        folder=Path(directory)
        if not folder.is_absolute() or not folder.is_dir():raise Error('Selecciona una carpeta disponible')
        if folder.resolve().is_relative_to(Path(pos.path).parent.resolve()):raise Error('Elige una carpeta fuera de los datos del programa; preferentemente una USB o disco externo')
        directory=str(folder.resolve())
    path=config_path(pos);temp=path.with_suffix('.tmp');temp.write_text(json.dumps({'directory':directory}),encoding='utf-8');os.replace(temp,path)
    return settings(pos)
def write_copy(pos,source):
    directory=settings(pos).get('directory','')
    if not directory:return {'configured':False,'ok':False,'warning':'Sin respaldo externo configurado. Guarda también una copia fuera de esta computadora.'}
    try:
        folder=Path(directory)
        if not folder.is_dir():raise OSError('Destino no disponible')
        destination=folder/'LunaDevPOS-respaldos-automaticos';destination.mkdir(exist_ok=True)
        if destination.is_symlink():raise OSError('Destino no válido')
        raw=Path(source).read_bytes()
        if not raw.startswith(PORTABLE):
            return {'configured':True,'ok':False,'warning':'Configura una frase de respaldo portátil para guardar copias recuperables fuera de esta computadora.'}
        target=destination/Path(source).name
        temporary=None
        try:
            with NamedTemporaryFile(dir=destination,delete=False) as f:
                temporary=Path(f.name);f.write(raw);f.flush();os.fsync(f.fileno())
            if hashlib.sha256(temporary.read_bytes()).digest()!=hashlib.sha256(raw).digest():raise OSError('Copia incompleta')
            os.replace(temporary,target)
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
        cutoff=dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=30)
        for item in destination.iterdir():
            match=re.fullmatch(r'turno-\d+-(\d{8}T\d{12}Z)\.botica(?:\.json)?',item.name)
            if match and item.is_file() and not item.is_symlink():
                try:
                    if dt.datetime.strptime(match[1],'%Y%m%dT%H%M%S%fZ').replace(tzinfo=dt.timezone.utc)<=cutoff:item.unlink()
                except (ValueError,OSError):pass
        return {'configured':True,'ok':True,'path':str(target),'retention_days':30}
    except (OSError,ValueError,KeyError):return {'configured':True,'ok':False,'warning':'No se pudo verificar la copia externa. Conecta el destino y vuelve a intentarlo desde Mantenimiento; el respaldo local se conserva.'}
