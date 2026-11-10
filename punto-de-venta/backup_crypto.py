"""Respaldo portátil con frase y respaldo local protegido por Windows."""
import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from core import Error
from local_secret import protect, reveal, transform

PORTABLE = b'LunaDevBackup\x00\x01'
LOCAL = b'LunaDevBackup\x00\x02'


def validate_phrase(phrase):
    if not isinstance(phrase, str) or len(phrase.strip()) < 12 or len(phrase) > 256:
        raise Error('Usa una frase de respaldo de 12 a 256 caracteres')
    return phrase


def derive_key(phrase, salt):
    return hashlib.pbkdf2_hmac('sha256', validate_phrase(phrase).encode(), salt, 600_000)


def seal(raw, phrase=None):
    if phrase is None:
        return LOCAL + transform(raw, True)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, nonce = os.urandom(16), os.urandom(12)
    header = PORTABLE + salt + nonce
    return header + AESGCM(derive_key(phrase, salt)).encrypt(nonce, raw, header)


def unseal(raw, phrase=None):
    if raw.startswith(LOCAL):
        try:
            return transform(raw[len(LOCAL):], False)
        except (OSError, RuntimeError) as exc:
            raise Error('Este respaldo está protegido por el perfil original de Windows') from exc
    if not raw.startswith(PORTABLE):
        return raw
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    start = len(PORTABLE)
    salt, nonce = raw[start:start+16], raw[start+16:start+28]
    header, body = raw[:start+28], raw[start+28:]
    if len(nonce) != 12 or len(body) < 16:
        raise Error('Respaldo cifrado incompleto')
    if not phrase:
        raise Error('Escribe la frase de respaldo para abrir el archivo')
    try:
        return AESGCM(derive_key(phrase, salt)).decrypt(nonce, body, header)
    except InvalidTag as exc:
        raise Error('La frase no coincide o el respaldo cifrado fue modificado') from exc


def phrase_path(pos):
    return Path(pos.path).parent / 'clave-respaldo.dpapi'


def automatic_phrase(pos):
    try:
        return reveal(phrase_path(pos).read_text(encoding='ascii'))
    except FileNotFoundError:
        return None


def configure_phrase(pos, phrase):
    path = phrase_path(pos)
    protected = protect(validate_phrase(phrase))
    with NamedTemporaryFile(mode='w', encoding='ascii', dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(protected)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
