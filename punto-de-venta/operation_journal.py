"""Diario durable de operaciones pendientes; no depende del almacenamiento del navegador."""
import json
from core import Error,required,fingerprint
KINDS={'sale':('sell','/sales'),'cash':(None,'/cash'),'restock':('inventory.receive','/inventory/restock'),'receive':('inventory.receive','/inventory/receive')}
TABLE="CREATE TABLE IF NOT EXISTS operation_intents(kind TEXT NOT NULL,user_id INTEGER NOT NULL REFERENCES users(id),request_key TEXT NOT NULL,body_json TEXT NOT NULL,shift_id INTEGER,acknowledged INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged IN(0,1)),PRIMARY KEY(kind,user_id,request_key))"

def permit(pos,db,uid,kind,body=None):
    if kind not in KINDS:raise Error('Operación no admitida')
    permission=KINDS[kind][0]
    if kind=='cash':
        permission='cash.'+str((body or {}).get('direction',''))
        if permission not in ('cash.in','cash.out'):raise Error('Dirección inválida')
    pos.require(db,uid,permission)

def lookup(pos,db,uid,kind,key):
    if kind=='sale':
        row=db.execute('SELECT id FROM sales WHERE user_id=? AND request_key=?',(uid,key)).fetchone()
        if row:return {'state':'confirmed','result':pos.ticket(db,row[0])}
    row=db.execute('SELECT result_json FROM operation_requests WHERE kind=? AND user_id=? AND request_key=?',(kind,uid,key)).fetchone()
    if row:
        result=json.loads(row[0]);return {'state':'cancelled' if result.get('cancelled') else 'confirmed','result':result}
    return {'state':'not_found'}

def handle(pos,uid,action,data,write):
    with pos.db(write) as db:
        if action=='pending' and not write:
            row=db.execute('SELECT * FROM operation_intents WHERE user_id=? AND acknowledged=0 ORDER BY rowid LIMIT 1',(uid,)).fetchone()
            if not row:return {'pending':None}
            body=json.loads(row['body_json']);permit(pos,db,uid,row['kind'],body)
            return {'pending':{'kind':row['kind'],'path':KINDS[row['kind']][1],'key':row['request_key'],'body':body,'shift_id':row['shift_id'],**lookup(pos,db,uid,row['kind'],row['request_key'])}}
        if not write:raise Error('Método inválido',405)
        kind=required(data,'kind');key=required(data,'key')
        row=db.execute('SELECT * FROM operation_intents WHERE kind=? AND user_id=? AND request_key=?',(kind,uid,key)).fetchone()
        if action=='prepare':
            body=data.get('body')
            if not isinstance(body,dict) or body.get('request_key')!=key:raise Error('Solicitud incompleta')
            permit(pos,db,uid,kind,body)
            other=db.execute('SELECT 1 FROM operation_intents WHERE user_id=? AND acknowledged=0 AND NOT(kind=? AND request_key=?)',(uid,kind,key)).fetchone()
            if other:raise Error('Comprueba la operación pendiente antes de iniciar otra',409)
            if row and fingerprint(json.loads(row['body_json']))!=fingerprint(body):raise Error('Clave reutilizada con otros datos',409)
            shift=db.execute('SELECT id FROM cash_shifts WHERE user_id=? AND closed_at IS NULL',(uid,)).fetchone()
            db.execute('INSERT OR IGNORE INTO operation_intents(kind,user_id,request_key,body_json,shift_id) VALUES(?,?,?,?,?)',(kind,uid,key,json.dumps(body),shift[0] if shift else None))
            return lookup(pos,db,uid,kind,key)
        if not row:raise Error('Operación pendiente inexistente',404)
        permit(pos,db,uid,kind,json.loads(row['body_json']))
        found=lookup(pos,db,uid,kind,key)
        if action=='cancel':
            if found['state']=='not_found':
                db.execute('INSERT INTO operation_requests(kind,user_id,request_key,request_hash,result_json) VALUES(?,?,?,?,?)',(kind,uid,key,'cancelled',json.dumps({'cancelled':True})))
                found={'state':'cancelled'}
            db.execute('UPDATE operation_intents SET acknowledged=1 WHERE kind=? AND user_id=? AND request_key=?',(kind,uid,key))
            return found
        if action=='ack':
            if found['state']=='not_found':raise Error('Todavía no se confirmó la operación',409)
            db.execute('UPDATE operation_intents SET acknowledged=1 WHERE kind=? AND user_id=? AND request_key=?',(kind,uid,key));return found
        raise Error('Ruta inexistente',404)
