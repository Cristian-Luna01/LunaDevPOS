import unittest,datetime as dt
import test_pos,credit,analytics,profit
class CashBasisTest(unittest.TestCase):
 setUp=test_pos.POSTest.setUp
 tearDown=test_pos.POSTest.tearDown
 receive=test_pos.POSTest.receive
 def configure(self):
  with self.pos.db(True) as db:
   db.execute('UPDATE customers SET discount_bps=0 WHERE id=1')
   db.execute('UPDATE products SET price_cents=1000,tax_bps=0 WHERE id=?',(self.pid,))
 def sell(self,key,on_account=False):
  return self.pos.sale(1,{'request_key':key,'customer_id':1 if on_account else None,'on_account':on_account,'items':[{'product_id':self.pid,'quantity':1}],'payments':[] if on_account else [{'method':'cash','amount_cents':1000}]})
 def test_two_day_example_with_collection_and_new_sale(self):
  self.configure();paid=self.sell('paid-day1');loan=self.sell('credit-day1',True)
  with self.pos.db() as db:
   self.assertEqual(self.pos.report(db,self.sid)['net_sales_cents'],1000)
   self.assertEqual(self.pos.report(db,self.sid)['expected_cents'],11000)
   self.assertEqual(profit.shift(db,self.sid)['profit_cents'],500)
  first=self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':11000})
  yesterday=(dt.date.today()-dt.timedelta(days=1)).isoformat()
  with self.pos.db(True) as db:
   db.execute('UPDATE sales SET created_at=? WHERE id IN (?,?)',(yesterday+'T12:00:00Z',paid['id'],loan['id']))
   db.execute('UPDATE customer_ledger SET created_at=?',(yesterday+'T12:00:00Z',))
  sid=self.pos.open_shift(1,{'shift_number':1,'opening_cents':0})['id']
  self.sell('paid-day2')
  credit.payment(self.pos,1,{'request_key':'collection-day2','customer_id':1,'amount_cents':1000,'method':'cash'})
  with self.pos.db() as db:
   report=self.pos.report(db,sid)
   self.assertEqual(report['net_sales_cents'],2000)
   self.assertEqual(report['expected_cents'],2000)
   self.assertEqual(sum(d['net_cents'] for d in report['departments']),2000)
   self.assertEqual(profit.shift(db,sid)['profit_cents'],1000)
   history=analytics.history(db,{'from':yesterday,'to':dt.date.today().isoformat()},True)
   self.assertEqual([(d['sales_cents'],d['profit_cents']) for d in history['daily']],[(1000,500),(2000,1000)])
   self.assertEqual(history['totals']['sold_units'],3)
   self.assertEqual(history['totals']['tickets'],3)
   self.assertEqual(next(e['cents'] for e in history['events'] if e['kind']=='Crédito'),0)
   self.assertEqual(next(e['units'] for e in history['events'] if e['kind']=='Abono'),0)
   self.assertEqual(self.pos.report(db,self.sid)['net_sales_cents'],first['net_sales_cents'])
   self.assertEqual(sum(p['profit_cents'] for p in history['products']),1500)
 def test_partial_payments_round_to_exact_historical_cost(self):
  with self.pos.db(True) as db:db.execute('UPDATE customers SET discount_bps=0 WHERE id=1')
  pid=self.pos.save_product(1,{'barcode':'CENTAVOS','name':'Producto centavos','category_id':1,'price_cents':3})['id']
  self.pos.receive(1,{'product_id':pid,'quantity':1,'lot_number':'C','unit_cost_cents':1,'reason':'Prueba'})
  self.pos.sale(1,{'request_key':'cent-credit','customer_id':1,'on_account':True,'items':[{'product_id':pid,'quantity':1}],'payments':[]})
  for i in range(3):credit.payment(self.pos,1,{'request_key':'cent-pay-'+str(i),'customer_id':1,'amount_cents':1,'method':'transfer'})
  with self.pos.db() as db:
   from cash_basis import collections
   events=collections(db)
   self.assertEqual(sum(e['cents'] for e in events),3)
   self.assertEqual(sum(e['cost_cents'] for e in events),1)
   self.assertEqual(sum(e['profit_cents'] for e in events),2)
   self.assertEqual(sum(e['units'] for e in events),0)
   self.assertEqual(self.pos.report(db,self.sid)['expected_cents'],10000)
 def test_oldest_purchases_first_and_no_profit_before_collection(self):
  self.configure();self.sell('oldest',True);self.sell('later',True)
  with self.pos.db() as db:self.assertEqual(profit.shift(db,self.sid)['profit_cents'],0)
  credit.payment(self.pos,1,{'request_key':'partial','customer_id':1,'amount_cents':1500,'method':'cash'})
  with self.pos.db() as db:
   from cash_basis import collections
   events=collections(db)
   self.assertEqual([e['cents'] for e in events],[1000,500])
   self.assertEqual(profit.shift(db,self.sid)['profit_cents'],750)
   self.assertEqual(self.pos.report(db,self.sid)['net_sales_cents'],1500)

 def test_full_collection_recognizes_cost_of_zero_price_item(self):
  self.configure()
  pid=self.pos.save_product(1,{'barcode':'REGALO','name':'Producto incluido','category_id':1,'price_cents':0})['id']
  self.pos.receive(1,{'product_id':pid,'quantity':1,'lot_number':'R','unit_cost_cents':100,'reason':'Prueba'})
  self.pos.sale(1,{'request_key':'with-free','customer_id':1,'on_account':True,'items':[{'product_id':self.pid,'quantity':1},{'product_id':pid,'quantity':1}],'payments':[]})
  credit.payment(self.pos,1,{'request_key':'collect-free','customer_id':1,'amount_cents':1000,'method':'cash'})
  with self.pos.db() as db:
   self.assertEqual(profit.shift(db,self.sid)['cost_cents'],600)
   self.assertEqual(profit.shift(db,self.sid)['profit_cents'],400)
