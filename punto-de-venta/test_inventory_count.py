import unittest,datetime as dt
from test_pos import POSTest
from core import Error
import inventory_count as count
class InventoryCountTest(unittest.TestCase):
 setUp=POSTest.setUp;tearDown=POSTest.tearDown;receive=POSTest.receive
 def prepare(self):return count.read(self.pos,1,{'id':str(self.pid)})
 def body(self,target,values,info=None):
  info=info or self.prepare()
  return {'product_id':self.pid,'version':info['version'],'counted_quantity':target,'batch_counts':[{'id':r['id'],'quantity':values.get(r['id'],r['quantity'])} for r in info['batches']],'reason':'Conteo QA'}
 def test_adjust_then_receive_preserves_lots_and_audit(self):
  info=self.prepare();before={r['id']:(r['expires_on'],r['unit_cost_cents']) for r in info['batches']}
  result=count.apply(self.pos,1,self.body(18,{self.early:8},info));self.assertEqual(result['difference'],-2)
  self.pos.restock(1,{'product_id':self.pid,'quantity':5});after=self.prepare();self.assertEqual(after['stock'],23)
  with self.pos.db() as db:
   for bid,(expiry,cost) in before.items():r=db.execute('SELECT * FROM batches WHERE id=?',(bid,)).fetchone();self.assertEqual((r['expires_on'],r['unit_cost_cents']),(expiry,cost))
   self.assertEqual(db.execute("SELECT quantity_delta FROM inventory_movements WHERE kind='adjustment'").fetchone()[0],-2)
   self.assertTrue(db.execute("SELECT 1 FROM audit_log WHERE action='inventory.product_count'").fetchone())
 def test_concurrent_receipt_or_sale_blocks_stale_count(self):
  info=self.prepare();body=self.body(19,{self.early:9},info);self.pos.restock(1,{'product_id':self.pid,'quantity':2})
  with self.assertRaises(Error) as e:count.apply(self.pos,1,body)
  self.assertEqual(e.exception.status,409);self.assertEqual(self.prepare()['stock'],22)
  info=self.prepare();body=self.body(21,{self.early:9},info);self.pos.sale(1,POSTest.body(self))
  with self.assertRaises(Error):count.apply(self.pos,1,body)
  self.assertEqual(self.prepare()['stock'],21)
 def test_validation_is_atomic_and_permissions_enforced(self):
  for body in (self.body(18,{self.early:9}),self.body(18,{self.early:8})|{'reason':''},self.body(18,{self.early:-2,self.late:20})):
   with self.assertRaises(Error):count.apply(self.pos,1,body)
  self.assertEqual(self.prepare()['stock'],20)
  uid=self.pos.save_user(1,{'username':'sellerqa','display_name':'QA','secret':'qa-password','permissions':['sell']})['id']
  with self.assertRaises(Error):count.apply(self.pos,uid,self.body(19,{self.early:9}))
  with self.assertRaises(Error):count.read(self.pos,uid,{'id':str(self.pid)})
 def test_zero_stock_and_expired_units_are_separate(self):
  with self.pos.db(True) as db:db.execute('UPDATE batches SET expires_on=?',(dt.date.today().isoformat(),))
  info=self.prepare();self.assertEqual((info['stock'],info['expired_quantity']),(0,20))
  body=self.body(3,{},info)
  with self.assertRaises(Error):count.apply(self.pos,1,body)
  body['confirm_new_batch']=True;count.apply(self.pos,1,body);after=self.prepare();self.assertEqual((after['stock'],after['expired_quantity']),(3,20))
 def test_edit_does_not_modify_historical_sale(self):
  sale=self.pos.sale(1,POSTest.body(self));p=self.prepare()['product'];p.update(name='Nombre corregido',barcode='NUEVO123',price_cents=2000)
  self.pos.save_product(1,{**p,'reason':'Actualización de precio de prueba'})
  with self.pos.db() as db:
   r=db.execute('SELECT product_name,unit_price_cents FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchone();self.assertEqual((r[0],r[1]),('Producto',1160))
if __name__=='__main__':unittest.main()
