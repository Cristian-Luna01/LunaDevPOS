import unittest
from test_customer_http import CustomerHTTPTest
from core import Error
import entity_management as entities,credit
class EntityManagementTest(unittest.TestCase):
 setUp=CustomerHTTPTest.setUp;tearDown=CustomerHTTPTest.tearDown;request=CustomerHTTPTest.request;receive=CustomerHTTPTest.receive
 def test_customer_baja_preserves_history_and_blocks_new_sale(self):
  sale=self.pos.sale(1,{'request_key':'entity-sale','customer_id':1,'items':[{'product_id':self.pid,'quantity':1}],'payments':[{'method':'cash','amount_cents':1044}]})
  entities.status(self.pos,1,'customers',{'id':1,'active':0,'reason':'QA'})
  with self.pos.db() as db:self.assertEqual(db.execute('SELECT customer_id FROM sales WHERE id=?',(sale['id'],)).fetchone()[0],1)
  self.assertEqual(credit.read(self.pos,1,{}),[])
  with self.assertRaises(Error):self.pos.sale(1,{'request_key':'inactive-sale','customer_id':1,'items':[{'product_id':self.pid,'quantity':1}],'payments':[{'method':'cash','amount_cents':1000}]})
  entities.status(self.pos,1,'customers',{'id':1,'active':1,'reason':'QA restore'});self.assertEqual(len(credit.read(self.pos,1,{})),1)
 def test_debt_blocks_customer_baja(self):
  self.pos.sale(1,{'request_key':'entity-credit','customer_id':1,'on_account':True,'items':[{'product_id':self.pid,'quantity':1}],'payments':[]})
  with self.assertRaises(Error):entities.status(self.pos,1,'customers',{'id':1,'active':0,'reason':'QA'})
 def test_supplier_baja_preserves_batches(self):
  with self.pos.db(True) as db:sid=db.execute("INSERT INTO suppliers(business_name) VALUES('QA proveedor')").lastrowid
  self.pos.receive(1,{'product_id':self.pid,'supplier_id':sid,'quantity':1,'unit_cost_cents':500,'reason':'QA'})
  entities.status(self.pos,1,'suppliers',{'id':sid,'active':0,'reason':'QA'})
  with self.pos.db() as db:self.assertTrue(db.execute('SELECT 1 FROM batches WHERE supplier_id=?',(sid,)).fetchone())
  with self.assertRaises(Error):self.pos.receive(1,{'product_id':self.pid,'supplier_id':sid,'quantity':1,'unit_cost_cents':500,'reason':'QA'})
 def test_user_baja_blocks_open_shift_self_and_revokes_login(self):
  with self.assertRaises(Error):entities.status(self.pos,1,'users',{'id':1,'active':0,'reason':'QA'})
  uid=self.pos.save_user(1,{'username':'entityqa','display_name':'QA','secret':'qa-password','permissions':['sell']})['id'];token=self.pos.login('entityqa','qa-password')
  shift=self.pos.open_shift(uid,{'register_id':'ENTITY','opening_cents':0})['id']
  with self.assertRaises(Error):entities.status(self.pos,1,'users',{'id':uid,'active':0,'reason':'QA'})
  self.pos.close_shift(uid,{'shift_id':shift,'counted_cents':0});entities.status(self.pos,1,'users',{'id':uid,'active':0,'reason':'QA'})
  with self.assertRaises(Error):self.pos.session_user(token)
  with self.assertRaises(Error):self.pos.login('entityqa','qa-password')
 def test_status_requires_permission_and_reason(self):
  uid=self.pos.save_user(1,{'username':'limitedqa','display_name':'QA','secret':'qa-password','permissions':['sell']})['id']
  with self.assertRaises(Error):entities.status(self.pos,uid,'customers',{'id':1,'active':0,'reason':'QA'})
  with self.assertRaises(Error):entities.status(self.pos,1,'customers',{'id':1,'active':0,'reason':''})
  with self.pos.db() as db:self.assertEqual(db.execute('SELECT active FROM customers WHERE id=1').fetchone()[0],1)
if __name__=='__main__':unittest.main()
