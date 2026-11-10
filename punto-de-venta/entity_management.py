"""Baja reversible sin borrar referencias históricas."""
from core import Error,integer,required
def install(db):
 for table in ('customers','suppliers'):
  if 'active' not in {r[1] for r in db.execute('PRAGMA table_info('+table+')')}:db.execute('ALTER TABLE '+table+' ADD COLUMN active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1))')
def listing(pos,uid,kind):
 table,permission={'customers':('customers','customers.manage'),'suppliers':('suppliers','suppliers.manage')}[kind]
 with pos.db() as db:
  pos.require(db,uid,permission)
  rows=[dict(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY '+('name' if kind=='customers' else 'business_name')+',id')]
  if kind=='customers':
   for r in rows:r['balance_cents']=db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM customer_ledger WHERE customer_id=?',(r['id'],)).fetchone()[0]
  return rows
def status(pos,uid,kind,data):
 table,permission={'customers':('customers','customers.manage'),'suppliers':('suppliers','suppliers.manage'),'users':('users','users.manage')}[kind]
 target=integer(data.get('id'),'Registro',1);active=integer(data.get('active'),'Estado',0,1)
 with pos.db(True) as db:
  if kind=='users':
   role,allowed=pos.account_access(db,uid)
  else:
   pos.require(db,uid,permission)
  row=db.execute('SELECT * FROM '+table+' WHERE id=?',(target,)).fetchone()
  if not row:raise Error('Registro inexistente',404)
  if kind=='users' and not pos.can_edit_account(db,uid,target,role,allowed,pos.permissions(db,target)):
   raise Error('No tienes permiso para modificar esta cuenta',403)
  if not active and kind=='customers':
   debt=db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM customer_ledger WHERE customer_id=?',(target,)).fetchone()[0]
   if debt:raise Error('El cliente tiene deuda o saldo pendiente. Liquida su cuenta antes de darlo de baja',409)
  if not active and kind=='users':
   if db.execute('SELECT 1 FROM cash_shifts WHERE user_id=? AND closed_at IS NULL',(target,)).fetchone():raise Error('El usuario tiene un turno abierto. Ciérralo antes de darlo de baja',409)
  db.execute('UPDATE '+table+' SET active=? WHERE id=?',(active,target))
  if kind=='users':db.execute('DELETE FROM sessions WHERE user_id=?',(target,))
  details={'before':row['active'],'after':active,'reason':required(data,'reason')}
  if kind=='users':details.update(username=row['username'],actor_role=role)
  pos.audit(db,uid,kind+'.status',target,details)
  return {'id':target,'active':active}
