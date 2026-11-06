"""Diario durable de solicitudes. El dominio sigue siendo dueño de la transacción."""
import json
import uuid
from core import Error, required, fingerprint, integer

PERMISSIONS = {'/sales':'sell','/returns':'sales.return','/cash':None,
               '/inventory/receive':'inventory.receive','/inventory/restock':'inventory.receive',
               '/credit/payment':'customers.manage'}

def install(db):
    db.execute('CREATE TABLE IF NOT EXISTS local_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    db.execute("INSERT OR IGNORE INTO local_metadata VALUES('identity',?)",(uuid.uuid4().hex,))
    db.execute('''CREATE TABLE IF NOT EXISTS pending_operations(
        request_key TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
        identity TEXT NOT NULL,path TEXT NOT NULL,payload TEXT NOT NULL,request_hash TEXT NOT NULL,
        shift_id INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')))''')
    db.execute('CREATE INDEX IF NOT EXISTS pending_owner ON pending_operations(user_id)')

def identity(db):
    return db.execute("SELECT value FROM local_metadata WHERE key='identity'").fetchone()[0]

def listing(pos,uid):
    with pos.db() as db:
        return {'identity':identity(db),'items':[dict(r) for r in db.execute(
            'SELECT request_key,path,shift_id,created_at FROM pending_operations WHERE user_id=? AND identity=? ORDER BY created_at', (uid,identity(db)))]}

def prepare(pos,uid,data):
    path=data.get('path');payload=data.get('payload')
    if path not in PERMISSIONS or not isinstance(payload,dict):raise Error('Operación no admitida')
    key=required(payload,'request_key');digest=fingerprint(payload)
    if key != payload['request_key']:raise Error('Clave inválida')
    if len(json.dumps(payload))>200000:raise Error('Operación demasiado grande')
    with pos.db(True) as db:
        permission=PERMISSIONS[path]
        if path=='/cash':permission='cash.'+str(payload.get('direction'))
        if path=='/returns':permission='sales.void' if payload.get('kind')=='void' else 'sales.return'
        pos.require(db,uid,permission)
        previous=db.execute('SELECT * FROM pending_operations WHERE request_key=?',(key,)).fetchone()
        if previous:
            if previous['user_id']!=uid or previous['path']!=path or previous['request_hash']!=digest:raise Error('Clave reutilizada',409)
            return {'request_key':key}
        if db.execute('SELECT 1 FROM pending_operations WHERE user_id=?',(uid,)).fetchone():
            raise Error('Resuelve primero la operación pendiente antes de confirmar otra.',409)
        shift=pos.shift(db,uid)
        db.execute('INSERT INTO pending_operations(request_key,user_id,identity,path,payload,request_hash,shift_id) VALUES(?,?,?,?,?,?,?)',
                   (key,uid,identity(db),path,json.dumps(payload),digest,shift['id']))
    return {'request_key':key}

def committed(db,row):
    key=row['request_key'];path=row['path']
    if path=='/sales':return db.execute('SELECT id FROM sales WHERE request_key=?',(key,)).fetchone()
    if path=='/returns':return db.execute('SELECT id FROM returns WHERE request_key=?',(key,)).fetchone()
    if path=='/credit/payment':return db.execute('SELECT id FROM customer_ledger WHERE request_key=?',(key,)).fetchone()
    action={'/cash':'cash.movement','/inventory/receive':'inventory.receive','/inventory/restock':'inventory.restock'}[path]
    return db.execute("SELECT entity_id FROM audit_log WHERE action=? AND json_extract(details,'$.request_key')=?",(action,key)).fetchone()

def row_for(db,uid,data):
    row=db.execute('SELECT * FROM pending_operations WHERE request_key=? AND user_id=? AND identity=?',
                   (required(data,'request_key'),uid,identity(db))).fetchone()
    if not row:raise Error('Operación pendiente inexistente',404)
    return row

def recover(pos,uid,data):
    with pos.db() as db:
        row=row_for(db,uid,data)
        shift=db.execute('SELECT id FROM cash_shifts WHERE user_id=? AND closed_at IS NULL',(uid,)).fetchone()
        if not committed(db,row) and (not shift or shift['id']!=row['shift_id']):
            raise Error('El turno original ya terminó. Esta operación no se confirmó; descártala y revisa el registro.',409)
    payload=json.loads(row['payload'])
    if row['path']=='/credit/payment':
        from credit import payment
        return payment(pos,uid,payload)
    method={'/sales':'sale','/returns':'return_sale','/cash':'cash_movement',
            '/inventory/receive':'receive','/inventory/restock':'restock'}[row['path']]
    return getattr(pos,method)(uid,payload)

def finish(pos,uid,data,cancel=False):
    with pos.db(True) as db:
        row=row_for(db,uid,data);done=bool(committed(db,row))
        if cancel and done:raise Error('La operación ya está confirmada. Recupera su comprobante.',409)
        if not cancel and not done:raise Error('La operación todavía no está confirmada',409)
        db.execute('DELETE FROM pending_operations WHERE request_key=?',(row['request_key'],))
    return {'ok':True}

def reset(db):
    db.execute('DELETE FROM pending_operations')
    db.execute("UPDATE local_metadata SET value=? WHERE key='identity'",(uuid.uuid4().hex,))
