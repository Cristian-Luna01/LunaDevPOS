import datetime as dt
import unittest
import test_pos,inventory_value,direction_replica
from branch_sync import snapshot
class InventoryValueTest(unittest.TestCase):
 setUp=test_pos.POSTest.setUp
 tearDown=test_pos.POSTest.tearDown
 receive=test_pos.POSTest.receive
 def test_lot_cost_not_reference_or_sale_price_and_expiry(self):
  with self.pos.db(True) as db:
   db.execute('UPDATE batches SET unit_cost_cents=700 WHERE id=?',(self.early,))
   db.execute('UPDATE products SET cost_cents=9999,price_cents=20000 WHERE id=?',(self.pid,))
   values=inventory_value.by_product(db,dt.date.today().isoformat())
   self.assertEqual(values[self.pid],12000)
   self.assertEqual(direction_replica.current(self.pos,db)['products'][0]['inventory_value_cents'],12000)
   db.execute('UPDATE batches SET expires_on=? WHERE id=?',(dt.date.today().isoformat(),self.early))
   self.assertEqual(inventory_value.by_product(db,dt.date.today().isoformat())[self.pid],5000)
  self.assertEqual(snapshot(self.pos)['direction']['products'][0]['inventory_value_cents'],5000)
 def test_inactive_zero_and_empty(self):
  with self.pos.db(True) as db:
   db.execute('UPDATE batches SET unit_cost_cents=0')
   self.assertEqual(sum(inventory_value.by_product(db,dt.date.today().isoformat()).values()),0)
   db.execute('UPDATE products SET active=0')
   self.assertEqual(inventory_value.by_product(db,dt.date.today().isoformat()),{})
class InventoryValueHTTPTest(unittest.TestCase):
 import test_customer_http as fixture
 setUp=fixture.CustomerHTTPTest.setUp
 tearDown=fixture.CustomerHTTPTest.tearDown
 receive=test_pos.POSTest.receive
 request=fixture.CustomerHTTPTest.request
 def test_total_all_products_and_cost_permission(self):
  import json
  with self.request('/api/inventory/overview') as r:self.assertEqual(json.load(r)['inventory_value_cents'],10000)
  pos_cookie=self.cookie
  with self.request('/direccion/api/login',{'username':'admin','secret':'test-only-password'}) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  with self.request('/direccion/api/summary') as r:self.assertEqual(sum(p['inventory_value_cents'] for p in json.load(r)['products']),10000)
  self.cookie=pos_cookie
  with self.pos.db(True) as db:db.execute("INSERT INTO user_permissions VALUES(1,'costs.view',0)")
  with self.request('/api/inventory/overview') as r:
   data=json.load(r)
   self.assertNotIn('inventory_value_cents',data)
   self.assertTrue(data['products'])
if __name__=='__main__':unittest.main()
