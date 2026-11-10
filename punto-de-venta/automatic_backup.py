"""Respaldos completos locales después de confirmar el cierre de un turno."""
import datetime as dt
import os
import re
import json
from pathlib import Path
from inventory_io import backup_document
from external_backup import write_copy
from backup_crypto import PORTABLE, LOCAL, automatic_phrase, seal, unseal
from core import Error, fingerprint

AUTOMATIC_NAME = re.compile(r'turno-\d+-(\d{8}T\d{12}Z)\.botica(?:\.json)?')


def cleanup(pos):
    directory = Path(pos.path).parent / 'respaldos-automaticos'
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    if not directory.is_dir():
        return
    for candidate in directory.iterdir():
        match = AUTOMATIC_NAME.fullmatch(candidate.name)
        if not match or candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            created = dt.datetime.strptime(match[1], '%Y%m%dT%H%M%S%fZ').replace(tzinfo=dt.timezone.utc)
            if created <= cutoff:
                candidate.unlink()
        except (ValueError, OSError):
            pass


def after_shift(pos, shift_id):
    directory = Path(pos.path).parent / 'respaldos-automaticos'
    try:
        with pos.request_lock:
            directory.mkdir(parents=True, exist_ok=True)
            phrase = automatic_phrase(pos)
            with pos.db() as db:
                closed = dict(db.execute('SELECT * FROM cash_shifts WHERE id=?',(shift_id,)).fetchone())
            for candidate in sorted(directory.glob(f'turno-{shift_id}-*.botica'), reverse=True):
                try:
                    if candidate.is_symlink():continue
                    encrypted = candidate.read_bytes()
                    if not encrypted.startswith(PORTABLE if phrase else LOCAL):continue
                    document = json.loads(unseal(encrypted,phrase))
                    digest = document.pop('sha256')
                    saved = next(row for row in document['tables']['cash_shifts'] if row['id']==shift_id)
                    if digest == fingerprint(document) and saved == closed:
                        return {'ok':True,'path':str(candidate),'retention_days':30,'external':write_copy(pos,candidate)}
                except (Error,OSError, ValueError, KeyError, StopIteration, TypeError):
                    pass
            with pos.db() as db:
                raw, _, _ = backup_document(db)
            raw = seal(raw,phrase)
            now = dt.datetime.now(dt.timezone.utc)
            target = directory / f'turno-{shift_id}-{now:%Y%m%dT%H%M%S%fZ}.botica'
            temporary = target.with_suffix('.tmp')
            try:
                with temporary.open('xb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            cleanup(pos)
            return {'ok':True,'path':str(target),'retention_days':30,'external':write_copy(pos,target)}
    except Exception:
        return {'ok': False, 'warning': 'El turno quedó cerrado, pero no se pudo guardar el respaldo automático. Crea un respaldo desde Mantenimiento y revisa el espacio y los permisos de la carpeta de datos.'}
