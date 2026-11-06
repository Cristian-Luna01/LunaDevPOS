import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from app import Handler
from core import POS, Error, password_hash

class POSTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pos = POS(Path(self.temp.name)/'test.db')
        self.pos.initialize('admin','test-only-password')
        self.uid = 1
        self.sid = self.pos.open_shift(1,{'register_id':'A','opening_cents':10000})['id']
        with self.pos.db(True) as db:
            db.execute("INSERT INTO suppliers(business_name) VALUES ('Distribuidor')")
            db.execute("INSERT INTO customers(name,discount_bps) VALUES ('Cliente',1000)")
        self.pid = self.pos.save_product(1,dict(barcode='123',name='Producto',generic_name='Sustancia',category_id=1,cost_cents=500,price_cents=1160,tax_bps=1600,max_stock=100))['id']
        self.late = self.receive(10,90)
        self.early = self.receive(10,30)

    def tearDown(self):
        self.temp.cleanup()

    def receive(self,qty,days):
        return self.pos.receive(1,dict(product_id=self.pid,supplier_id=1,lot_number=f'L{days}',expires_on=(dt.date.today()+dt.timedelta(days=days)).isoformat(),quantity=qty,unit_cost_cents=500,reason='Factura A'))['id']

    def body(self,key='sale-1',qty=1,total=None):
        return {'request_key':key,'items':[{'product_id':self.pid,'quantity':qty}], 'payments':[{'method':'cash','amount_cents':total if total is not None else qty*1160}]}

    def scalar(self,sql,args=()):
        with self.pos.db() as db:
            return db.execute(sql,args).fetchone()[0]

    def test_mixed_fefo_tax_discount_and_idempotency(self):
        body=self.body(qty=12)
        body['customer_id']=1
        body['payments']=[{'method':'cash','amount_cents':5000,'tendered_cents':6000},{'method':'transfer','amount_cents':7528}]
        sale=self.pos.sale(1,body)
        self.assertEqual((sale['total_cents'],sale['discount_cents'],sale['tax_cents'],sale['change_cents']),(12528,1392,1728,1000))
        self.assertEqual(self.scalar('SELECT quantity FROM batches WHERE id=?',(self.early,)),0)
        self.assertEqual(self.scalar('SELECT quantity FROM batches WHERE id=?',(self.late,)),8)
        self.assertEqual(self.pos.sale(1,body)['id'],sale['id'])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM sales'),1)
        changed=dict(body,customer_id=None)
        with self.assertRaises(Error):self.pos.sale(1,changed)

    def test_atomic_insufficient_stock_and_invalid_payment(self):
        for body in [self.body(qty=21),self.body(total=1)]:
            with self.assertRaises(Error):self.pos.sale(1,body)
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM batches'),20)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM sales'),0)

    def test_concurrent_sale_last_stock(self):
        def attempt(i):
            try:return self.pos.sale(1,self.body(key=f'concurrent-{i}',qty=15))
            except Error:return None
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results=list(pool.map(attempt,range(2)))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM batches'),5)

    def test_cash_report_and_frozen_z(self):
        body=self.body(qty=2)
        body['payments']=[{'method':'cash','amount_cents':1000,'tendered_cents':2000},{'method':'credit','amount_cents':1320}]
        self.pos.sale(1,body)
        self.pos.cash_movement(1,dict(direction='in',category='change',amount_cents=500,concept='Cambio'))
        self.pos.cash_movement(1,dict(direction='out',category='supplier',amount_cents=300,supplier_id=1,invoice_ref='F-001',concept='Pago'))
        result=self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':11190})
        self.assertEqual(result['expected_cents'],11200)
        self.assertEqual(result['difference_cents'],-10)
        self.assertEqual(result['movements'][1]['supplier_name'],'Distribuidor')
        self.assertEqual(self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':11190}),result)
        with self.assertRaises(Error):self.pos.sale(1,self.body('after-close'))
        with self.assertRaises(Error):self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':11200})

    def test_returns_next_shift_and_rounding(self):
        with self.pos.db(True) as db:
            db.execute('UPDATE products SET price_cents=101 WHERE id=?',(self.pid,))
        b=self.body(qty=3,total=273);b['customer_id']=1
        s=self.pos.sale(1,b);iid=s['items'][0]['id']
        self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':10273})
        sid=self.pos.open_shift(1,{'register_id':'A','opening_cents':1000})['id']
        amounts=[]
        for n in range(3):
            payload={'request_key':f'r{n}','sale_id':s['id'],'reason':'Devolución','items':[{'sale_item_id':iid,'quantity':1,'disposition':'restock'}]}
            r=self.pos.return_sale(1,payload);amounts.append(r['total_cents'])
            self.assertEqual(self.pos.return_sale(1,payload)['id'],r['id'])
        self.assertEqual(sum(amounts),273)
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM batches'),20)
        with self.pos.db() as db:
            self.assertEqual(self.pos.report(db,sid)['expected_cents'],727)
        with self.assertRaises(Error):self.pos.return_sale(1,dict(payload,request_key='excess'))

    def test_expired_quarantine_adjust_and_kardex(self):
        expired=self.receive(10,-1)
        with self.assertRaises(Error):self.pos.sale(1,self.body(qty=21))
        s=self.pos.sale(1,self.body())
        self.pos.return_sale(1,{'request_key':'q','sale_id':s['id'],'reason':'Empaque dañado','items':[{'sale_item_id':s['items'][0]['id'],'quantity':1,'disposition':'quarantine'}]})
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM quarantine'),1)
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM batches'),29)
        with self.assertRaises(Error):self.pos.adjust(1,{'batch_id':self.early,'expected_quantity':10,'counted_quantity':7,'reason':'Conteo'})
        self.pos.adjust(1,{'batch_id':self.early,'expected_quantity':9,'counted_quantity':7,'reason':'Conteo'})
        with self.pos.db() as db:
            rows=db.execute('SELECT b.id,b.quantity, SUM(m.quantity_delta) balance FROM batches b JOIN inventory_movements m ON m.batch_id=b.id GROUP BY b.id').fetchall()
            self.assertTrue(all(r['quantity']==r['balance'] for r in rows))

    def test_prescription_and_permissions(self):
        with self.pos.db(True) as db:
            db.execute('UPDATE products SET requires_prescription=1 WHERE id=?',(self.pid,))
        with self.assertRaises(Error):self.pos.sale(1,self.body())
        b=self.body();b['items'][0]['prescription']={'doctor_name':'Médico','license_number':'CED1','prescription_ref':'RX1'}
        self.pos.sale(1,b)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM prescriptions'),1)
        user=self.pos.save_user(1,dict(username='cajero',display_name='Cajero',secret='123456',permissions=['sell']))['id']
        with self.assertRaises(Error):self.pos.adjust(user,dict(batch_id=1,expected_quantity=10,counted_quantity=8,reason='No autorizado'))

    def test_fault_after_stock_write_rolls_back_everything(self):
        with self.pos.db(True) as db:
            db.execute("CREATE TRIGGER reject_payment BEFORE INSERT ON sale_payments BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.pos.sale(1,self.body())
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM batches'),20)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM sales'),0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM inventory_movements WHERE kind='sale'"),0)

    def test_void_restores_original_batches(self):
        s=self.pos.sale(1,self.body(qty=12))
        self.pos.return_sale(1,{'request_key':'void','sale_id':s['id'],'kind':'void','reason':'Error de captura'})
        self.assertEqual(self.scalar('SELECT quantity FROM batches WHERE id=?',(self.early,)),10)
        self.assertEqual(self.scalar('SELECT quantity FROM batches WHERE id=?',(self.late,)),10)
        self.assertEqual(self.scalar('SELECT status FROM sales'),'voided')

    def test_duplicate_shift_and_supplier_fields(self):
        with self.assertRaises(Error):self.pos.open_shift(1,dict(register_id='B',opening_cents=0))
        with self.assertRaises(sqlite3.IntegrityError):self.pos.cash_movement(1,dict(direction='out',category='supplier',amount_cents=10,concept='Pago'))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM cash_movements'),0)

    def test_http_blind_report_costs_csrf_and_login_throttling(self):
        uid=self.pos.save_user(1,dict(username='cashier',display_name='Caja',secret='123456',permissions=['sell']))['id']
        sid=self.pos.open_shift(uid,dict(register_id='B',opening_cents=1000))['id']
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.pos=self.pos
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            req=Request(base+'/api/login',json.dumps({'username':'cashier','secret':'123456'}).encode(),headers={'Content-Type':'application/json','X-POS-Request':'1'})
            with urlopen(req) as r:cookie=r.headers['Set-Cookie'].split(';')[0]
            req=Request(base+'/api/logout',b'{}',headers={'Cookie':cookie,'Content-Type':'application/json','X-POS-Request':'1'})
            with self.assertRaises(HTTPError) as e:urlopen(req)
            self.assertEqual(e.exception.code,409)
            with urlopen(Request(base+'/api/me',headers={'Cookie':cookie})) as r:
                self.assertEqual(json.load(r)['shift']['id'],sid)
            with self.assertRaises(HTTPError) as denied:
                urlopen(Request(base+'/api/sales/history',headers={'Cookie':cookie}))
            self.assertEqual(denied.exception.code,403)
            with urlopen(Request(base+'/api/products',headers={'Cookie':cookie})) as r:
                self.assertNotIn('cost_cents',json.load(r)[0])
            with urlopen(Request(base+f'/api/inventory/availability?ids={self.pid}',headers={'Cookie':cookie})) as r:
                self.assertEqual(json.load(r),[{'id':self.pid,'price_cents':1160,'stock':20,'promotion':None,'promo_price_cents':None}])
            with urlopen(Request(base+'/api/inventory/overview',headers={'Cookie':cookie})) as r:
                stock=json.load(r)
                self.assertEqual(stock['products'][0]['stock'],20)
                self.assertNotIn('cost_cents',stock['products'][0])
                self.assertNotIn('sales_cents',stock)
            with self.assertRaises(HTTPError) as e:urlopen(Request(base+f'/api/shifts/report?id={sid}',headers={'Cookie':cookie}))
            self.assertEqual(e.exception.code,403)
            admin_cookie=f'pos_session_{server.server_port}='+self.pos.login('admin','test-only-password')
            with urlopen(Request(base+'/api/sales/history',headers={'Cookie':admin_cookie})) as r:
                self.assertIn('profit_cents',json.load(r)['totals'])
            req=Request(base+'/api/shifts/open',json.dumps({'register_id':'Estoy en casa','opening_cents':0}).encode(),headers={'Cookie':admin_cookie,'Content-Type':'application/json','X-POS-Request':'1'})
            with self.assertRaises(HTTPError) as e:urlopen(req)
            self.assertEqual(e.exception.code,400)
            with urlopen(Request(base+'/api/products',headers={'Cookie':admin_cookie})) as r:
                product=json.load(r)[0]
                self.assertEqual(product['unit_margin_cents'],500)
                self.assertEqual(product['margin_bps'],5000)
            with urlopen(Request(base+'/api/reports/general?from_id=1&to_id=10',headers={'Cookie':admin_cookie})) as r:
                general=json.load(r)
                self.assertEqual(len(general['shifts']),2)
                self.assertEqual(general['net_sales_cents'],0)
            req=Request(base+'/api/shifts/close',json.dumps({'shift_id':sid,'counted_cents':1000}).encode(),headers={'Cookie':cookie,'Content-Type':'application/json'})
            with self.assertRaises(HTTPError) as e:urlopen(req)
            self.assertEqual(e.exception.code,403)
            self.pos.close_shift(uid,{'shift_id':sid,'counted_cents':1000})
            req=Request(base+'/api/logout',b'{}',headers={'Cookie':cookie,'Content-Type':'application/json','X-POS-Request':'1'})
            with urlopen(req) as r:self.assertTrue(json.load(r)['ok'])
            for n in range(5):
                with self.assertRaises(Error):self.pos.login('cashier','wrong')
            with self.assertRaises(Error) as e:self.pos.login('cashier','123456')
            self.assertEqual(e.exception.status,429)
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_direction_session_access_and_daily_totals(self):
        self.pos.save_user(1,dict(username='reporter',display_name='Informes',secret='123456',permissions=['sell','reports.view']))
        sale=self.pos.sale(1,self.body(qty=2))
        self.pos.return_sale(1,dict(sale_id=sale['id'],kind='void',reason='Prueba',request_key='void-direction'))
        self.pos.sale(1,self.body(key='remaining',qty=1))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.pos=self.pos
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def request(path,data=None,cookie=''):
            return urlopen(Request(base+path,json.dumps(data).encode() if data is not None else None,headers={'Cookie':cookie,'Content-Type':'application/json','X-POS-Request':'1'}))
        try:
            with request('/api/login',{'username':'admin','secret':'test-only-password'}) as r:pos_cookie=r.headers['Set-Cookie'].split(';')[0]
            with self.assertRaises(HTTPError) as e:request('/direccion/api/summary',cookie=pos_cookie)
            self.assertEqual(e.exception.code,401)
            with self.assertRaises(HTTPError) as e:request('/direccion/api/login',{'username':'reporter','secret':'123456'})
            self.assertEqual(e.exception.code,403)
            with request('/direccion/api/login',{'username':'admin','secret':'test-only-password'}) as r:
                self.assertIn('Path=/direccion',r.headers['Set-Cookie'])
                cookie=r.headers['Set-Cookie'].split(';')[0]
            with request('/direccion/api/summary',cookie=cookie) as r:
                result=json.load(r)
                self.assertEqual((result['sales_cents'],result['refunds_cents'],result['net_cents'],result['tickets']),(3480,2320,1160,2))
                self.assertEqual(result['profit_cents'],result['net_cents']-result['cost_cents'])
                with request('/direccion/api/history',cookie=cookie) as h:
                    totals=json.load(h)['totals']
                for field in ('sales_cents','refunds_cents','net_cents','cost_cents','profit_cents','tickets'):
                    self.assertEqual(result[field],totals[field])
                self.assertEqual(result['products'][0]['stock'],19)
                self.assertEqual(result['products'][0]['purchase_cost_cents'],500)
                self.assertEqual(result['products'][0]['price_cents'],1160)
                self.assertIsNone(result['shifts'][0]['difference_cents'])
                self.assertIsNone(result['shifts'][0]['counted_cents'])
                self.assertEqual(result['suppliers'][0]['business_name'],'Distribuidor')
            self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':11000})
            with request('/direccion/api/summary',cookie=cookie) as r:
                result=json.load(r)
                self.assertEqual(result['shifts'][0]['difference_cents'],-160)
            # Una devolución de hoy de una venta anterior afecta el neto de hoy,
            # pero no vuelve a contar aquella venta en los ingresos del día.
            with self.pos.db(True) as db:
                db.execute("UPDATE sales SET created_at=strftime('%Y-%m-%dT%H:%M:%fZ','now','-2 days') WHERE id=?",(sale['id'],))
            with request('/direccion/api/summary',cookie=cookie) as r:
                result=json.load(r)
                self.assertEqual((result['sales_cents'],result['refunds_cents'],result['net_cents'],result['tickets']),(1160,2320,-1160,1))
            with request('/direccion/api/logout',{},cookie):pass
            with self.assertRaises(HTTPError) as e:request('/direccion/api/summary',cookie=cookie)
            self.assertEqual(e.exception.code,401)
            with request('/api/me',cookie=pos_cookie) as r:self.assertEqual(json.load(r)['user']['id'],1)
        finally:server.shutdown();server.server_close();thread.join()

    def test_numbered_shift_keeps_register_and_validates_choice(self):
        self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':10000})
        with self.assertRaises(Error):self.pos.open_shift(1,{'shift_number':3,'opening_cents':0})
        sid=self.pos.open_shift(1,{'shift_number':2,'opening_cents':0})['id']
        self.assertEqual(self.scalar('SELECT register_id FROM cash_shifts WHERE id=?',(sid,)),'CAJA-1')
        details=json.loads(self.scalar("SELECT details FROM audit_log WHERE action='shift.open' AND entity_id=?",(sid,)))
        self.assertEqual(details['shift_number'],2)
        uid=self.pos.save_user(1,dict(username='second',display_name='Segundo',secret='123456',permissions=['sell']))['id']
        with self.assertRaises(Error):self.pos.open_shift(uid,{'shift_number':1,'opening_cents':0})

if __name__=='__main__':unittest.main(verbosity=2)
