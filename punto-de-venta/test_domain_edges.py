import copy, sqlite3, unittest
import test_pos
from core import POS, Error

class DomainEdgesTest(unittest.TestCase):
 setUp=test_pos.POSTest.setUp
 tearDown=test_pos.POSTest.tearDown
 receive=test_pos.POSTest.receive
 body=test_pos.POSTest.body
 scalar=test_pos.POSTest.scalar
 def rejects(self,fn,*args):
  with self.assertRaises(Error):fn(*args)
 def test_invalid_sales_preserve_stock_and_sales(self):
  samples=[dict(customer_id=999),dict(items=[]),dict(items=None),dict(items=[dict(product_id=self.pid,quantity=1)]*201),dict(items=[dict(product_id=self.pid,quantity=1)]*2),dict(items=[dict(product_id=999,quantity=1)]),dict(payments=None),dict(payments=[dict(method='cash',amount_cents=1)]*5),dict(payments=[dict(method='unknown',amount_cents=1160)]),dict(payments=[dict(method='cash',amount_cents=580)]*2),dict(payments=[dict(method='debit',amount_cents=1160,tendered_cents=1200)])]
  for i,change in enumerate(samples):self.rejects(self.pos.sale,1,dict(self.body('bad-%s'%i),**change))
  self.assertEqual(self.scalar('SELECT SUM(quantity) FROM batches'),20)
  self.assertEqual(self.scalar('SELECT COUNT(*) FROM sales'),0)
  with self.pos.db() as db:
   self.rejects(self.pos.ticket,db,999)
   self.rejects(self.pos.report,db,999)
  self.rejects(self.pos.cash_movement,1,dict(direction='wrong'))
 def test_invalid_initialization_and_batch_fields(self):
  self.rejects(self.pos.initialize,'admin','short')
  self.rejects(self.pos.initialize,'admin','long-password')
  for date in ['2026-1-01','2026-02-30','20260101']:
   self.rejects(self.pos.receive,1,dict(product_id=self.pid,quantity=1,unit_cost_cents=1,expires_on=date,reason='Prueba'))
  self.rejects(self.pos.adjust,1,dict(batch_id=999,counted_quantity=1,expected_quantity=0,reason='Prueba'))
  self.rejects(self.pos.adjust,1,dict(batch_id=self.early,counted_quantity=10,expected_quantity=10,reason='Prueba'))
  self.rejects(self.pos.edit_batch,1,dict(batch_id=self.early,expires_on='invalid',reason='Prueba'))
  self.rejects(self.pos.save_product,1,dict(id=999,barcode='x',name='x',category_id=1,price_cents=1))
 def test_user_edits_revoke_sessions_and_enforce_permissions(self):
  base=dict(username='qa',display_name='QA',secret='qa-password',permissions=['sell','products.edit'])
  for change in [dict(id=1),dict(permissions=['bad']),dict(permissions='sell'),dict(secret='short'),dict(secret=''),dict(id=999)]:self.rejects(self.pos.save_user,1,dict(base,**change))
  uid=self.pos.save_user(1,base)['id'];token=self.pos.login('qa','qa-password')
  self.pos.save_user(1,dict(base,id=uid,secret='new-password',display_name='QA editado'))
  self.rejects(self.pos.session_user,token)
  self.pos.login('qa','new-password')
  self.pos.save_user(1,dict(base,id=uid,secret=''))
  self.pos.save_product(uid,dict(reason='Cambio autorizado QA',id=self.pid,barcode='123',name='Editado',category_id=1,cost_cents=999,price_cents=1200,requires_prescription=True))
  self.assertEqual(self.scalar('SELECT cost_cents FROM products WHERE id=?',(self.pid,)),500)
  self.assertEqual(self.scalar('SELECT requires_prescription FROM products WHERE id=?',(self.pid,)),1)
 def test_return_validation_and_repeat_conflicts(self):
  ticket=self.pos.sale(1,self.body(qty=3));iid=ticket['items'][0]['id']
  entry=dict(sale_item_id=iid,quantity=1)
  base=dict(request_key='ret',sale_id=ticket['id'],reason='Prueba',items=[entry])
  for change in [dict(kind='bad'),dict(items=[]),dict(items=None),dict(items=[entry]*201),dict(items=[entry,entry]),dict(items=[dict(entry,sale_item_id=999)]),dict(items=[dict(entry,quantity=4)]),dict(items=[dict(entry,disposition='bad')])]:self.rejects(self.pos.return_sale,1,dict(base,**change))
  self.pos.return_sale(1,base)
  self.rejects(self.pos.return_sale,1,dict(base,reason='Otro motivo'))
  self.rejects(self.pos.return_sale,1,dict(base,request_key='void',kind='void'))
  self.pos.return_sale(1,dict(base,request_key='finish',items=[dict(entry,quantity=2)]))
  self.assertEqual(self.scalar('SELECT SUM(quantity) FROM batches'),20)
  credit=self.pos.sale(1,dict(request_key='credit',customer_id=1,on_account=True,items=[dict(product_id=self.pid,quantity=1)],payments=[]))
  self.rejects(self.pos.return_sale,1,dict(base,request_key='credit-return',sale_id=credit['id']))
 def test_fault_during_stock_update_rolls_back_sale(self):
  with self.pos.db(True) as db:db.execute("CREATE TRIGGER test_ignore BEFORE UPDATE OF quantity ON batches WHEN NEW.quantity<OLD.quantity BEGIN SELECT RAISE(IGNORE); END")
  self.rejects(self.pos.sale,1,self.body())
  self.assertEqual(self.scalar('SELECT COUNT(*) FROM sales'),0)
  self.assertEqual(self.scalar('SELECT SUM(quantity) FROM batches'),20)
 def test_inconsistent_refund_and_trace_are_rejected_atomically(self):
  ticket=self.pos.sale(1,self.body(qty=12));iid=ticket['items'][0]['id']
  base=dict(request_key='ret',sale_id=ticket['id'],reason='Prueba',items=[dict(sale_item_id=iid,quantity=10)])
  self.pos.return_sale(1,base)
  self.pos.return_sale(1,dict(base,request_key='rest',items=[dict(sale_item_id=iid,quantity=2)]))
  second=self.pos.sale(1,self.body('second',qty=1));iid2=second['items'][0]['id']
  with self.pos.db(True) as db:db.execute('DELETE FROM sale_payments WHERE sale_id=?',(second['id'],))
  bad=dict(request_key='bad',sale_id=second['id'],reason='Prueba',items=[dict(sale_item_id=iid2,quantity=1)])
  self.rejects(self.pos.return_sale,1,bad)
  with self.pos.db(True) as db:
   db.execute("INSERT INTO sale_payments(sale_id,method,amount_cents,tendered_cents) VALUES (?,'cash',1160,1160)",(second['id'],))
   db.execute('DELETE FROM sale_item_batches WHERE sale_item_id=?',(iid2,))
  self.rejects(self.pos.return_sale,1,bad)
  self.assertEqual(self.scalar('SELECT COUNT(*) FROM returns'),2)
