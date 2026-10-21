"""Reintentos en la misma transacción que el movimiento; aislamiento por usuario."""
import json
from core import Error,fingerprint,required

def previous(db,uid,kind,data):
    if 'request_key' not in data:return None  # llamadas internas anteriores; HTTP exige clave.
    key=required(data,'request_key');digest=fingerprint(data)
    row=db.execute('SELECT request_hash,result_json FROM operation_requests WHERE kind=? AND user_id=? AND request_key=?',(kind,uid,key)).fetchone()
    if row:
        if json.loads(row[1]).get('cancelled'):raise Error('Esta operación fue cancelada',409)
        if row[0]!=digest:raise Error('Clave reutilizada con otros datos',409)
        return json.loads(row[1])
    return None

def save(db,uid,kind,data,result):
    if 'request_key' in data:
        db.execute('INSERT INTO operation_requests(kind,user_id,request_key,request_hash,result_json) VALUES(?,?,?,?,?)',(kind,uid,data['request_key'],fingerprint(data),json.dumps(result)))
    return result
