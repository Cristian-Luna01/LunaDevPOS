import csv,datetime as dt,io,unittest
import test_pos,analytics,credit
class PaymentBreakdownTest(unittest.TestCase):
 setUp=test_pos.POSTest.setUp
 tearDown=test_pos.POSTest.tearDown
 receive=test_pos.POSTest.receive
 def sell(self,key,method):return self.pos.sale(1,dict(request_key=key,items=[dict(product_id=self.pid,quantity=1)],payments=[dict(method=method,amount_cents=1160,tendered_cents=2000 if method=='cash' else 1160)]))
 def test_methods_include_abonos_exclude_credit_and_subtract_refunds(self):
  self.sell('cash','cash');card=self.sell('debit','debit');self.sell('bank-credit-card','credit');self.sell('transfer','transfer')
  self.pos.sale(1,dict(request_key='on-account',customer_id=1,on_account=True,items=[dict(product_id=self.pid,quantity=2)],payments=[]))
  for key,method in [('payment-cash','cash'),('payment-transfer','transfer')]:credit.payment(self.pos,1,dict(request_key=key,customer_id=1,amount_cents=500,method=method))
  self.pos.return_sale(1,dict(request_key='return-card',sale_id=card['id'],reason='Prueba',items=[dict(sale_item_id=card['items'][0]['id'],quantity=1)]))
  with self.pos.db() as db:
   r=analytics.history(db,{},True)
   self.assertEqual(r['totals']['payments_by_method'],dict(cash=1660,card=1160,transfer=1660))
   self.assertEqual(sum(r['totals']['payments_by_method'].values()),r['totals']['net_cents'])
   self.assertEqual(r['daily'][0]['payments_by_method'],r['totals']['payments_by_method'])
   rows=list(csv.DictReader(io.StringIO(analytics.export_history(r,True).decode('utf-8-sig'))))
   self.assertEqual(rows[0]['Cobrado en efectivo MXN'],'16.60');self.assertEqual(rows[0]['Cobrado con tarjeta MXN'],'11.60');self.assertEqual(rows[0]['Cobrado por transferencia MXN'],'16.60')
   self.assertEqual(self.pos.report(db,self.sid)['expected_cents'],11660)
 def test_refund_on_later_day_is_negative_by_original_method(self):
  s=self.sell('card','debit');yesterday=(dt.date.today()-dt.timedelta(days=1)).isoformat()
  with self.pos.db(True) as db:db.execute('UPDATE sales SET created_at=? WHERE id=?',(yesterday+'T18:00:00Z',s['id']))
  self.pos.return_sale(1,dict(request_key='return',sale_id=s['id'],reason='Prueba',items=[dict(sale_item_id=s['items'][0]['id'],quantity=1)]))
  with self.pos.db() as db:
   r=analytics.history(db,{})
   self.assertEqual(r['totals']['payments_by_method'],dict(cash=0,card=-1160,transfer=0));self.assertEqual(r['totals']['net_cents'],-1160)
   old=analytics.history(db,{'from':yesterday,'to':yesterday})
   self.assertEqual(old['totals']['payments_by_method']['card'],1160)
 def test_empty_period_methods_are_zero(self):
  with self.pos.db() as db:r=analytics.history(db,{})
  self.assertEqual(r['totals']['payments_by_method'],dict(cash=0,card=0,transfer=0))
