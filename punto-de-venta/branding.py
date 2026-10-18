"""Logotipo PNG compartido, incluido en el respaldo completo."""
import base64,binascii,struct,zlib
from core import Error
TABLE="CREATE TABLE IF NOT EXISTS business_branding(id INTEGER PRIMARY KEY CHECK(id=1),png_base64 TEXT NOT NULL)"
SETTINGS_TABLE="CREATE TABLE IF NOT EXISTS business_settings(id INTEGER PRIMARY KEY CHECK(id=1),name TEXT NOT NULL,receipt_footer TEXT NOT NULL)"

def settings(pos):
    with pos.db() as db:
        row=db.execute('SELECT name,receipt_footer FROM business_settings WHERE id=1').fetchone()
        has_logo=bool(db.execute('SELECT 1 FROM business_branding WHERE id=1').fetchone())
    return dict(row or {'name':'Punto de venta','receipt_footer':'Gracias por tu compra.'},has_logo=has_logo)

def save_settings(pos,uid,data):
    name=data.get('name');footer=data.get('receipt_footer','')
    if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise Error('Escribe un nombre de 1 a 80 caracteres')
    if not isinstance(footer,str) or len(footer)>200:raise Error('El mensaje del ticket admite hasta 200 caracteres')
    with pos.db(True) as db:
        pos.require(db,uid,'users.manage')
        db.execute('INSERT INTO business_settings VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,receipt_footer=excluded.receipt_footer',(name.strip(),footer.strip()))
        pos.audit(db,uid,'settings.save',1,{'name':name.strip()})
    return {'ok':True}

def validate(value):
    try:raw=base64.b64decode(value,validate=True)
    except (ValueError,TypeError,binascii.Error):raise Error('Selecciona una imagen PNG válida')
    if len(raw)>2*1024*1024 or raw[:8]!=b'\x89PNG\r\n\x1a\n':raise Error('Usa un PNG de hasta 2 MB')
    offset=8;seen=[]
    while offset+12<=len(raw):
        size=struct.unpack('>I',raw[offset:offset+4])[0];kind=raw[offset+4:offset+8];end=offset+12+size
        if end>len(raw):
            raise Error('PNG incompleto')
        chunk=raw[offset+8:offset+8+size]
        if zlib.crc32(kind+chunk)!=struct.unpack('>I',raw[end-4:end])[0]:raise Error('PNG dañado')
        if not seen:
            if kind!=b'IHDR' or size!=13:raise Error('PNG inválido')
            width,height=struct.unpack('>II',chunk[:8])
            if not 0<width<=4096 or not 0<height<=4096:raise Error('El logotipo debe medir como máximo 4096 × 4096 píxeles')
        seen.append(kind);offset=end
        if kind==b'IEND':break
    if not seen or seen[-1]!=b'IEND' or b'IDAT' not in seen or offset!=len(raw):raise Error('PNG inválido')
    return raw

def save(pos,uid,data):
    if data.get('remove') is True:
        with pos.db(True) as db:
            pos.require(db,uid,'users.manage')
            db.execute('DELETE FROM business_branding WHERE id=1')
            pos.audit(db,uid,'branding.remove',1,{})
        return {'ok':True}
    value=data.get('png_base64');validate(value)
    with pos.db(True) as db:
        pos.require(db,uid,'users.manage')
        db.execute('INSERT INTO business_branding VALUES (1,?) ON CONFLICT(id) DO UPDATE SET png_base64=excluded.png_base64',(value,))
        pos.audit(db,uid,'branding.save',1,{})
    return {'ok':True}

def read(pos):
    with pos.db() as db:row=db.execute('SELECT png_base64 FROM business_branding WHERE id=1').fetchone()
    return validate(row[0]) if row else None
