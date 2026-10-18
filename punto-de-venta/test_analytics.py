import csv
import datetime as dt
import io
from pathlib import Path
import tempfile
import unittest
from core import POS,Error
import analytics
import promotions
import profit
import inventory_io
import base64
import json
from core import fingerprint

class AnalyticsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.pos=POS(Path(self.temp.name)/'test.db')
        self.pos.initialize('admin','test-password')
        self.pos.open_shift(1,{'shift_number':1,'opening_cents':0})
        self.pid=self.pos.save_product(1,dict(barcode='00123',name='=Producto de prueba',category_id=1,cost_cents=100,price_cents=16000,tax_bps=0))['id']
        for lot in ['A','B']:
            self.pos.receive(1,dict(product_id=self.pid,lot_number=lot,quantity=2,unit_cost_cents=100,reason='Prueba'))
        self.sale=self.pos.sale(1,{'request_key':'sample','items':[{'product_id':self.pid,'quantity':3}],'payments':[{'method':'cash','amount_cents':16000},{'method':'debit','amount_cents':32000}]})
        self.today=dt.date.today();self.range={'from':(self.today-dt.timedelta(days=2)).isoformat(),'to':self.today.isoformat()}
    def tearDown(self):self.temp.cleanup()
    def report(self,data=None,metrics=False):
        with self.pos.db() as db:return (analytics.metrics if metrics else analytics.history)(db,data or self.range)
    def test_no_duplicate_payments_lots_and_zero_days(self):
        result=self.report()
        self.assertEqual(len(result['events']),1)
        self.assertEqual(result['totals']['sales_cents'],48000)
        self.assertEqual(result['totals']['sold_units'],3)
        self.assertEqual(result['totals']['tickets'],1)
        self.assertEqual(len(result['daily']),3)
        self.assertEqual(result['daily'][0]['net_cents'],0)
    def test_returns_traced_to_original_and_local_date(self):
        with self.pos.db(True) as db:
            db.execute("UPDATE sales SET created_at=strftime('%Y-%m-%dT%H:%M:%fZ','now','-1 day') WHERE id=?",(self.sale['id'],))
        self.pos.return_sale(1,dict(sale_id=self.sale['id'],kind='void',reason='Prueba',request_key='void'))
        result=self.report({'from':self.today.isoformat(),'to':self.today.isoformat()})
        self.assertEqual(result['totals']['sales_cents'],0)
        self.assertEqual(result['totals']['refunds_cents'],48000)
        self.assertEqual(result['totals']['net_cents'],-48000)
        self.assertEqual(result['events'][0]['ticket_id'],self.sale['id'])
        self.assertEqual(result['events'][0]['units'],-3)
        self.assertEqual(self.report()['totals']['net_cents'],0)
    def test_metrics_coverage_zero_sales_and_prior_period(self):
        self.pos.save_product(1,dict(barcode='zero',name='Sin ventas',category_id=1,cost_cents=0,price_cents=100,tax_bps=0))
        result=self.report(metrics=True)
        sold=next(p for p in result['products'] if p['id']==self.pid)
        self.assertEqual(sold['coverage_days'],1)
        self.assertEqual(sold['daily_units'],1)
        self.assertEqual(result['previous']['totals']['sales_cents'],0)
        self.assertEqual(sum(d['days'] for d in result['weekdays']),3)
        self.assertEqual(sum(d['net_cents'] for d in result['weekdays']),48000)
        self.assertIsNone(next(p for p in result['products'] if p['barcode']=='zero')['coverage_days'])
    def test_csv_decimals_formula_safety_and_valid_ranges(self):
        parsed=list(csv.reader(io.StringIO(analytics.export_history(self.report()).decode('utf-8-sig'))))
        self.assertEqual(parsed[1][9],'480.00')
        self.assertTrue(parsed[1][7].startswith("'="))
        self.assertEqual(parsed[1][6],'00123')
        daily=list(csv.reader(io.StringIO(analytics.export_history(self.report(),True).decode('utf-8-sig'))))
        self.assertEqual(len(daily),4)
        self.assertEqual(daily[-1][1:4],['480.00','0.00','480.00'])
        for data in [{'from':'invalid'},{'from':'0001-01-01'},{'from':(self.today-dt.timedelta(days=366)).isoformat(),'to':self.today.isoformat()},{'from':(self.today+dt.timedelta(days=1)).isoformat()}]:
            with self.assertRaises(Error):self.report(data)

    def test_historical_profit_and_returns(self):
        with self.pos.db(True) as db:db.execute('UPDATE products SET cost_cents=99999 WHERE id=?',(self.pid,))
        with self.pos.db() as db:
            report=analytics.history(db,self.range,True)
            self.assertEqual(report['totals']['profit_cents'],47700)
            self.assertEqual(profit.shift(db,1)['profit_cents'],47700)
            self.assertNotIn('profit_cents',analytics.history(db,self.range)['totals'])
        self.pos.return_sale(1,dict(sale_id=self.sale['id'],kind='void',reason='Prueba',request_key='profit-void'))
        with self.pos.db() as db:
            report=analytics.history(db,self.range,True)
            self.assertEqual(report['totals']['profit_cents'],0)
            self.assertEqual(report['totals']['cost_cents'],0)

    def test_quarantine_keeps_original_cost_and_subtracts_refund(self):
        self.pos.return_sale(1,dict(sale_id=self.sale['id'],kind='return',reason='Dañado',request_key='quarantine',items=[{'sale_item_id':self.sale['items'][0]['id'],'quantity':3,'disposition':'quarantine'}]))
        with self.pos.db() as db:self.assertEqual(analytics.history(db,self.range,True)['totals']['profit_cents'],-300)

    def test_counter_sale_and_purchase_difference_examples(self):
        pids=[]
        for code,cost,price in [('PRUEBA',20000,30000),('CONDONES',1000,2000)]:
            pid=self.pos.save_product(1,dict(barcode=code,name=code,category_id=1,cost_cents=cost,price_cents=price,tax_bps=1600))['id']
            pids.append(pid)
            self.pos.receive(1,dict(product_id=pid,lot_number=code,quantity=1,unit_cost_cents=cost,reason='Compra'))
            self.pos.sale(1,dict(request_key=code,items=[dict(product_id=pid,quantity=1)],payments=[dict(method='cash',amount_cents=price)]))
        with self.pos.db() as db:
            result=analytics.history(db,self.range,True)
            products={p['id']:p for p in result['products']}
            self.assertEqual((products[pids[0]]['net_cents'],products[pids[0]]['profit_cents']),(30000,10000))
            self.assertEqual((products[pids[1]]['net_cents'],products[pids[1]]['profit_cents']),(2000,1000))
            self.assertEqual(result['totals']['profit_cents'],47700+11000)
            self.assertEqual(profit.shift(db,1)['profit_cents'],47700+11000)
            daily=list(csv.DictReader(io.StringIO(analytics.export_history(result,True).decode('utf-8-sig'))))
            self.assertEqual(daily[-1]['Ganancia real MXN'],'587.00')

    def test_promotion_best_discount_and_permissions(self):
        data=dict(product_id=self.pid,name='Oferta',price_cents=10000,starts_on=self.today.isoformat(),ends_on=self.today.isoformat())
        promotions.save(self.pos,1,data)
        with self.pos.db(True) as db:
            cid=db.execute("INSERT INTO customers(name,discount_bps) VALUES ('Cliente',2000)").lastrowid
        body={'request_key':'promo','customer_id':cid,'items':[{'product_id':self.pid,'quantity':1}],'payments':[{'method':'cash','amount_cents':10000}]}
        ticket=self.pos.sale(1,body)
        self.assertEqual(ticket['discount_cents'],6000)
        self.assertEqual(self.pos.sale(1,body)['id'],ticket['id'])
        self.pos.return_sale(1,dict(sale_id=ticket['id'],kind='void',reason='Prueba',request_key='promo-void'))
        with self.pos.db(True) as db:db.execute('UPDATE customers SET discount_bps=9000 WHERE id=?',(cid,))
        body['request_key']='loyalty';body['payments'][0]['amount_cents']=1600
        self.assertEqual(self.pos.sale(1,body)['total_cents'],1600)
        uid=self.pos.save_user(1,dict(username='cashier',display_name='Caja',secret='123456',permissions=['sell']))['id']
        with self.assertRaises(Error):promotions.save(self.pos,uid,data)
        with self.assertRaises(Error):promotions.save(self.pos,1,dict(data,price_cents=16001))

    def test_promotions_backup_and_legacy_restore(self):
        promotions.save(self.pos,1,dict(product_id=self.pid,name='Oferta',price_cents=10000,starts_on=self.today.isoformat(),ends_on=self.today.isoformat()))
        raw,_,_=inventory_io.backup(self.pos,1)
        target=POS(Path(self.temp.name)/'restore.db');target.initialize('admin','test-password')
        inventory_io.restore(target,1,dict(file_base64=base64.b64encode(raw).decode(),filename='backup.json',confirmation='RESTAURAR'))
        with target.db() as db:self.assertEqual(promotions.active(db)[self.pid]['price_cents'],10000)
        old=json.loads(raw);old.pop('sha256');old['version']=2;old['tables'].pop('promotions');old['sha256']=fingerprint(old)
        loaded=inventory_io.read_backup(dict(file_base64=base64.b64encode(json.dumps(old).encode()).decode(),filename='old.json'))
        self.assertEqual(loaded['tables']['promotions'],[])

    def test_tax_historical_batch_cost_and_expired_promotion(self):
        with self.pos.db(True) as db:
            db.execute('UPDATE products SET price_cents=1160,tax_bps=1600 WHERE id=?',(self.pid,))
        yesterday=(self.today-dt.timedelta(days=1)).isoformat()
        promotions.save(self.pos,1,dict(product_id=self.pid,name='Terminada',price_cents=500,starts_on=yesterday,ends_on=yesterday))
        ticket=self.pos.sale(1,{'request_key':'tax','items':[{'product_id':self.pid,'quantity':1}],'payments':[{'method':'cash','amount_cents':1160}]})
        self.assertEqual(ticket['tax_cents'],160)
        with self.pos.db() as db:
            e=next(r for r in profit.entries(db,start=self.range['from'],end=self.range['to']) if r['item_id']==ticket['items'][0]['id'])
            self.assertEqual(e['profit_cents'],1060)
        promotions.save(self.pos,1,dict(product_id=self.pid,disable=True))
        with self.pos.db() as db:self.assertNotIn(self.pid,promotions.active(db))

if __name__=='__main__':unittest.main()
