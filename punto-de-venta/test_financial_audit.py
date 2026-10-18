"""Pruebas independientes de importes, persistencia y mercancía."""
from decimal import Decimal, ROUND_HALF_UP
import random, sqlite3, unittest
from core import POS, Error
import test_pos

class FinancialAuditTest(unittest.TestCase):
 setUp=test_pos.POSTest.setUp
 tearDown=test_pos.POSTest.tearDown
 receive=test_pos.POSTest.receive
 scalar=test_pos.POSTest.scalar
 def test_150_discount_tax_and_change_cases_against_decimal(self):
  rng=random.Random(20261011)
  cases=[(1,1,0,0),(1,1,5000,1600),(101,3,1000,1600),(1999,7,3333,800),(100,2,10000,0)]
  cases += [(rng.randint(1,999999),rng.randint(1,15),rng.randint(0,10000),rng.choice([0,800,1600,10000])) for _ in range(145)]
  self.receive(2500,90)
  expected_cash=10000
  for n,(price,qty,discount,tax) in enumerate(cases):
   with self.pos.db(True) as db:
    db.execute('UPDATE products SET price_cents=?,tax_bps=? WHERE id=?',(price,tax,self.pid))
    db.execute('UPDATE customers SET discount_bps=? WHERE id=1',(discount,))
   gross=price*qty
   reduced=int((Decimal(gross)*Decimal(discount)/10000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
   total=gross-reduced
   vat=int((Decimal(total)*tax/Decimal(10000+tax)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
   change=rng.randint(0,10000) if total else 0
   payload={'request_key':'audit-%d'%n,'customer_id':1,'items':[{'product_id':self.pid,'quantity':qty}],'payments':[{'method':'cash','amount_cents':total,'tendered_cents':total+change}] if total else []}
   ticket=self.pos.sale(1,payload)
   self.assertEqual((ticket['total_cents'],ticket['discount_cents'],ticket['tax_cents'],ticket['change_cents']),(total,reduced,vat,change))
   self.assertEqual(self.pos.sale(1,payload)['id'],ticket['id'])
   expected_cash+=total
  self.assertEqual(self.scalar('SELECT COUNT(*) FROM sales'),150)
  reopened=POS(self.pos.path)
  with reopened.db() as db:
   self.assertEqual(reopened.report(db,self.sid)['expected_cents'],expected_cash)
   self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
   self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

 def test_create_edit_receive_preserves_old_sale_and_cost(self):
  saved=self.pos.save_product(1,dict(barcode='NUEVO',name='Nuevo medicamento',category_id=1,cost_cents=325,price_cents=1000,tax_bps=0))['id']
  self.assertEqual(self.scalar('SELECT COUNT(*) FROM batches WHERE product_id=?',(saved,)),0)
  self.pos.receive(1,dict(product_id=saved,quantity=7,unit_cost_cents=325,reason='Factura nueva'))
  sale=self.pos.sale(1,{'request_key':'before-edit','items':[{'product_id':saved,'quantity':2}],'payments':[{'method':'cash','amount_cents':2000}]})
  self.pos.save_product(1,dict(reason='Actualización de lista QA',id=saved,barcode='NUEVO',name='Nombre actualizado',category_id=1,cost_cents=450,price_cents=1200,tax_bps=0))
  self.pos.receive(1,dict(product_id=saved,quantity=4,unit_cost_cents=450,reason='Otra factura'))
  reopened=POS(self.pos.path)
  with reopened.db() as db:
   self.assertEqual(db.execute('SELECT SUM(quantity) FROM batches WHERE product_id=?',(saved,)).fetchone()[0],9)
   row=db.execute('SELECT product_name,unit_price_cents,total_cents FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchone()
   self.assertEqual(tuple(row),('Nuevo medicamento',1000,2000))
   self.assertEqual(db.execute('SELECT SUM(quantity*unit_cost_cents) FROM sale_item_batches WHERE sale_item_id IN(SELECT id FROM sale_items WHERE sale_id=?)',(sale['id'],)).fetchone()[0],650)
   self.assertEqual(db.execute('SELECT name,price_cents FROM products WHERE id=?',(saved,)).fetchone()['price_cents'],1200)

 def test_invalid_receipts_leave_no_stock_or_audit_changes(self):
  before=[self.scalar('SELECT COUNT(*) FROM '+t) for t in ('batches','inventory_movements','audit_log')]
  for quantity,cost in [(0,500),(-1,500),(1,-1),(1.5,500),(True,500)]:
   with self.assertRaises(Error):self.pos.receive(1,dict(product_id=self.pid,quantity=quantity,unit_cost_cents=cost,reason='Prueba'))
  with self.assertRaises(Error):self.pos.receive(1,dict(product_id=self.pid,quantity=1,unit_cost_cents=500,reason=''))
  self.assertEqual([self.scalar('SELECT COUNT(*) FROM '+t) for t in ('batches','inventory_movements','audit_log')],before)

 def test_duplicate_barcode_edit_rolls_back(self):
  other=self.pos.save_product(1,dict(barcode='OTRO',name='Otro',category_id=1,cost_cents=100,price_cents=200,tax_bps=0))['id']
  with self.assertRaises(sqlite3.IntegrityError):self.pos.save_product(1,dict(reason='Prueba código duplicado',id=other,barcode='123',name='No debe guardarse',category_id=1,cost_cents=999,price_cents=999,tax_bps=0))
  with self.pos.db() as db:self.assertEqual(tuple(db.execute('SELECT name,barcode,price_cents FROM products WHERE id=?',(other,)).fetchone()),('Otro','OTRO',200))
