import json
from core import Error, integer, required, fingerprint
TABLE = "CREATE TABLE IF NOT EXISTS customer_ledger(id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES customers(id),sale_id INTEGER UNIQUE REFERENCES sales(id),shift_id INTEGER NOT NULL REFERENCES cash_shifts(id),user_id INTEGER NOT NULL REFERENCES users(id),amount_cents INTEGER NOT NULL CHECK(amount_cents!=0),method TEXT CHECK(method IN ('cash','debit','transfer')),request_key TEXT UNIQUE,request_hash TEXT,created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')))"
def read(pos,uid,data):
 with pos.db() as db:
  pos.require(db,uid,'customers.manage')
  if 'id' not in data:
   q='%'+str(data.get('q',''))+'%'
   return [dict(r) for r in db.execute('SELECT c.*,COALESCE(SUM(l.amount_cents),0) balance_cents FROM customers c LEFT JOIN customer_ledger l ON l.customer_id=c.id WHERE c.active=1 AND (c.name LIKE ? OR c.phone LIKE ?) GROUP BY c.id ORDER BY c.name',(q,q))]
  cid=integer(int(data['id']),'Cliente',1)
  rows=[dict(r) for r in db.execute('SELECT * FROM customer_ledger WHERE customer_id=? ORDER BY id DESC',(cid,))]
  for r in rows:r['items']=[dict(i) for i in db.execute('SELECT product_name,quantity,total_cents FROM sale_items WHERE sale_id=?',(r['sale_id'],))]
  return {'balance_cents':sum(r['amount_cents'] for r in rows),'movements':rows}
def payment(pos,uid,data):
 with pos.db(True) as db:
  pos.require(db,uid,'customers.manage');pos.require(db,uid,'sell')
  key=required(data,'request_key');digest=fingerprint(data)
  old=db.execute('SELECT * FROM customer_ledger WHERE request_key=?',(key,)).fetchone()
  if old:
   if old['request_hash']!=digest or old['user_id']!=uid:
       raise Error('Clave reutilizada',409)
   audit=db.execute("SELECT details FROM audit_log WHERE action='customer.payment' AND entity_id=? ORDER BY id DESC LIMIT 1",(str(old['id']),)).fetchone()
   details=json.loads(audit['details']) if audit else {}
   return {'id':old['id'],'applied_cents':-old['amount_cents'],'change_cents':details.get('change_cents',0),'balance_cents':details.get('balance_after_cents')}
  sid=pos.shift(db,uid)['id'];cid=integer(data.get('customer_id'),'Cliente',1);amount=integer(data.get('amount_cents'),'Abono',1)
  balance=db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM customer_ledger WHERE customer_id=?',(cid,)).fetchone()[0]
  method=data.get('method')
  if method not in ('cash','debit','transfer'):
      raise Error('Forma de pago inválida')
  if balance<=0:
      raise Error('El cliente no tiene deuda pendiente')
  if method!='cash' and amount>balance:
      raise Error('Tarjeta y transferencia no permiten cambio; el abono no puede exceder la deuda')
  received=integer(data.get('received_cents',amount),'Dinero recibido',amount)
  if method!='cash' and received!=amount:
      raise Error('Solo el efectivo permite cambio')
  amount=min(amount,balance);change=received-amount
  lid=db.execute('INSERT INTO customer_ledger(customer_id,shift_id,user_id,amount_cents,method,request_key,request_hash) VALUES (?,?,?,?,?,?,?)',(cid,sid,uid,-amount,method,key,digest)).lastrowid
  if method=='debit':
   from card_fees import record
   record(db,'ledger',lid,amount)
  pos.audit(db,uid,'customer.payment',lid,{'amount_cents':amount,'customer_id':cid,'received_cents':received,'change_cents':change,'balance_after_cents':balance-amount})
  return {'id':lid,'balance_cents':balance-amount,'applied_cents':amount,'change_cents':change}
