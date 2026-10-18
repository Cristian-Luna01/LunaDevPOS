"""Conteo de existencias vendibles con lotes, auditoría y detección de cambios."""
import datetime as dt
from core import Error,integer,required,fingerprint
def snapshot(db,pid):
 p=db.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
 if not p:raise Error('Producto inexistente o dado de baja',404)
 rows=[dict(r) for r in db.execute('SELECT * FROM batches WHERE product_id=? ORDER BY id',(pid,))]
 today=dt.date.today().isoformat();eligible=[r for r in rows if r['expires_on'] is None or r['expires_on']>today]
 return dict(p),eligible,sum(r['quantity'] for r in rows)-sum(r['quantity'] for r in eligible),fingerprint({'day':today,'product':dict(p),'batches':rows})
def read(pos,uid,data):
 pid=integer(int(data.get('id',0)),'Producto',1)
 with pos.db() as db:
  permissions=pos.permissions(db,uid)
  if not permissions.intersection({'products.edit','inventory.adjust'}):raise Error('No tienes permiso para editar o ajustar inventario',403)
  p,rows,expired,version=snapshot(db,pid)
  if 'costs.view' not in permissions:
   p.pop('cost_cents',None)
   for r in rows:r.pop('unit_cost_cents',None)
  return {'product':p,'batches':rows,'expired_quantity':expired,'stock':sum(r['quantity'] for r in rows),'version':version}
def apply(pos,uid,data):
 pid=integer(data.get('product_id'),'Producto',1);target=integer(data.get('counted_quantity'),'Nueva existencia',0,10**9);reason=required(data,'reason')
 with pos.db(True) as db:
  pos.require(db,uid,'inventory.adjust');p,rows,expired,version=snapshot(db,pid)
  if data.get('version')!=version:raise Error('La existencia o los lotes cambiaron durante el conteo. Cierra y vuelve a abrir el ajuste para revisar.',409)
  old=sum(r['quantity'] for r in rows);counts=data.get('batch_counts')
  if not isinstance(counts,list):raise Error('Indica el conteo por lote')
  values={}
  for entry in counts:
   if not isinstance(entry,dict):raise Error('Conteo por lote inválido')
   bid=integer(entry.get('id'),'Lote',1);qty=integer(entry.get('quantity'),'Conteo del lote',0,10**9)
   if bid in values:raise Error('Lote repetido')
   values[bid]=qty
  if set(values)!=set(r['id'] for r in rows):raise Error('Revisa todos los lotes vendibles del producto')
  if rows and sum(values.values())!=target:raise Error('La suma de los conteos por lote debe coincidir con la nueva existencia total')
  changed=[]
  if not rows and target:
   if data.get('confirm_new_batch') is not True:raise Error('Confirma que son unidades vendibles adicionales, sin incluir productos caducados')
   latest=db.execute('SELECT unit_cost_cents FROM batches WHERE product_id=? ORDER BY received_at DESC,id DESC LIMIT 1',(pid,)).fetchone();cost=latest[0] if latest else p['cost_cents']
   bid=db.execute("INSERT INTO batches(product_id,lot_number,quantity,unit_cost_cents) VALUES(?,'CONTEO SIN LOTE CAPTURADO',?,?)",(pid,target,cost)).lastrowid
   changed.append((bid,0,target))
  else:
   for row in rows:
    counted=values[row['id']]
    if counted!=row['quantity']:
     db.execute('UPDATE batches SET quantity=? WHERE id=?',(counted,row['id']));changed.append((row['id'],row['quantity'],counted))
  if not changed:raise Error('El conteo no cambia la existencia')
  for bid,before,after in changed:
   db.execute("INSERT INTO inventory_movements(batch_id,user_id,quantity_delta,kind,reason) VALUES(?,?,?,'adjustment',?)",(bid,uid,after-before,reason))
  pos.audit(db,uid,'inventory.product_count',pid,{'before':old,'after':target,'reason':reason,'batches':[{'id':bid,'before':before,'after':after} for bid,before,after in changed]})
  return {'product_id':pid,'stock_before':old,'stock_after':target,'difference':target-old}
