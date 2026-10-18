import datetime as dt,io,json,unittest
from decimal import Decimal
from openpyxl import load_workbook
from test_billing import BillingTest
from core import Error
import card_fees,credit,analytics,inventory_io
from history_xlsx import export_history_xlsx
class FeeTest(unittest.TestCase):
 setUp=BillingTest.setUp;tearDown=BillingTest.tearDown
 def config(self,rate=350):return card_fees.settings(self.pos,1,dict(enabled=True,provider='Mercado Pago QA',rate_bps=rate,vat_bps=1600,fixed_cents=0))
 def sell_card(self,key='fee',amount=10000):
  self.pos.save_product(1,dict(reason='Cambio de precio QA',id=self.pid,barcode='QA',name='QA',category_id=1,cost_cents=500,price_cents=amount,tax_bps=1600,max_stock=100))
  return self.pos.sale(1,dict(request_key=key,items=[dict(product_id=self.pid,quantity=1)],payments=[dict(method='debit',amount_cents=amount)]))
 def history(self):
  with self.pos.db() as db:return analytics.history(db,{'from':dt.date.today().isoformat(),'to':dt.date.today().isoformat()},True)
 def test_100_pesos_exact_and_historical_rate(self):
  self.config();sale=self.sell_card();self.sell_card();r=self.history();self.assertEqual(len(r['card_fees']),1)
  f=r['card_fees'][0];self.assertEqual((f['base_cents'],f['vat_cents'],f['fee_cents'],f['net_cents']),(350,56,406,9594))
  self.config(500);self.assertEqual(self.history()['card_fees'][0]['fee_cents'],406)
  self.assertEqual(r['totals']['payments_by_method']['card'],10000);self.assertEqual(r['totals']['after_fees_cents'],r['totals']['net_cents']-406)
  self.assertEqual(r['totals']['profit_after_fees_cents'],r['totals']['profit_cents']-406)
 def test_credit_payment_and_change_not_duplicated(self):
  self.config()
  with self.pos.db(True) as db:db.execute("INSERT INTO customers(name) VALUES('QA crédito')")
  sale=self.pos.sale(1,dict(request_key='debt',customer_id=1,on_account=True,items=[dict(product_id=self.pid,quantity=1)],payments=[]))
  self.assertEqual(self.history()['totals']['card_fee_cents'],0)
  body=dict(request_key='abono',customer_id=1,amount_cents=1160,method='debit')
  credit.payment(self.pos,1,body);credit.payment(self.pos,1,body)
  f=self.history()['card_fees'][0];self.assertEqual(f['source_kind'],'ledger');self.assertEqual(f['fee_cents'],47)
 def test_unconfigured_and_invalid_fee_atomic(self):
  s=self.sell_card();r=self.history();self.assertEqual(r['totals']['card_fee_unconfigured_cents'],10000)
  self.config(10000)
  with self.assertRaises(Error):self.sell_card('invalid')
  with self.pos.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM sales').fetchone()[0],2)
 def test_excel_and_backup_complete(self):
  self.config();self.sell_card();r=self.history();wb=load_workbook(io.BytesIO(export_history_xlsx(r)),data_only=True)
  self.assertIn('Comisiones tarjeta',wb.sheetnames);sheet=wb['Comisiones tarjeta'];self.assertEqual(sheet['E6'].value,4.06);self.assertEqual(sheet['F6'].value,95.94)
  raw,_,_=inventory_io.backup(self.pos,1);doc=json.loads(raw);self.assertEqual(doc['version'],10);self.assertEqual(doc['tables']['card_fees'][0]['fee_cents'],406)
 def test_small_amount_rounding_consistent(self):
  cfg=self.config()
  for n in range(1,20000):
   fee=card_fees.calculate(n,cfg);self.assertEqual(fee['fee_cents'],int((Decimal(n)*Decimal('0.0406')).quantize(Decimal(1),rounding='ROUND_HALF_UP')));self.assertEqual(fee['base_cents']+fee['vat_cents'],fee['fee_cents'])
