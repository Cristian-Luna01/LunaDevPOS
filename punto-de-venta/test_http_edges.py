import base64, json, sqlite3, unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import test_customer_http, test_inventory_io
from core import Error

class HTTPEdgesTest(unittest.TestCase):
 setUp=test_customer_http.CustomerHTTPTest.setUp
 tearDown=test_customer_http.CustomerHTTPTest.tearDown
 receive=test_customer_http.CustomerHTTPTest.receive
 request=test_customer_http.CustomerHTTPTest.request
 def call(self,path,data=None):
  with self.request(path,data) as r:return json.load(r)
 def test_all_static_downloads_csv_and_import(self):
  for path in ['/','/app.js','/style.css','/inventory-ui.js','/direccion','/direccion/','/direccion/panel.js','/stock.js','/reports.js','/promotions-ui.js','/branding.js','/navigation.js','/favicon.svg','/business-settings']:
   with self.request(path) as r:self.assertTrue(r.read());self.assertEqual(r.status,200)
  with self.assertRaises(HTTPError) as e:self.request('/business-logo.png')
  self.assertEqual(e.exception.code,404)
  self.pos.sale(1,dict(request_key='sale',items=[dict(product_id=self.pid,quantity=1)],payments=[dict(method='cash',amount_cents=1160)]))
  for path in ['/api/sales/history.csv','/api/sales/history.csv?summary=1','/api/inventory/export?format=csv','/api/inventory/export?format=xls','/api/inventory/export?format=json','/api/backup/export']:
   with self.request(path) as r:self.assertTrue(r.read());self.assertIn('attachment',r.headers['Content-Disposition'])
  payload=test_inventory_io.upload(test_inventory_io.legacy([['HTTP','Desde archivo',1,2,0,5,0,'Otros']]))
  preview=self.call('/api/inventory/import/preview',payload)
  self.assertEqual(self.call('/api/inventory/import/confirm',dict(payload,revision=preview['revision'],request_key='http-import'))['units'],5)
  with self.request('/direccion/api/login',dict(username='admin',secret='test-only-password')) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  for path in ['/direccion/api/history.csv','/direccion/api/history.csv?summary=1']:
   with self.request(path) as r:self.assertTrue(r.read())
  with self.assertRaises(HTTPError) as e:self.request('/direccion/api/no-existe')
  self.assertEqual(e.exception.code,404)
  with self.assertRaises(HTTPError) as e:self.request('/direccion/api/summary',{})
  self.assertEqual(e.exception.code,404)
 def test_bad_requests_and_database_failures(self):
  def raw(data,headers):return urlopen(Request(self.base+'/api/login',data,headers={'Cookie':self.cookie,'X-POS-Request':'1',**headers}))
  for body,headers,status in [(b'{}',{'Host':'invalid','Content-Type':'application/json'},403),(b'{}',{'Content-Type':'text/plain'},415),(b'',{'Content-Type':'application/json'},413),(b'[]',{'Content-Type':'application/json'},400),(b'{',{'Content-Type':'application/json'},400),(b'{}',{'Content-Type':'application/json','Origin':'http://invalid'},403),(b' '*262145,{'Content-Type':'application/json'},413)]:
   with self.assertRaises(HTTPError) as e:raw(body,headers)
   self.assertEqual(e.exception.code,status)
  with self.assertRaises(HTTPError) as e:self.call('/api/products/save',dict(barcode='123',name='Duplicado',category_id=1,price_cents=1))
  self.assertEqual(e.exception.code,409)
  for error,status in [(sqlite3.OperationalError('database is locked'),503),(ValueError('invalid'),400),(RuntimeError('fallo controlado de prueba'),500)]:
   with patch.object(self.pos,'cash_movement',side_effect=error),patch('app.logging.exception'):
    with self.assertRaises(HTTPError) as e:self.call('/api/cash',{'request_key':'edge'})
    self.assertEqual(e.exception.code,status)
  with self.assertRaises(HTTPError) as e:self.call('/api/no-existe',{})
  self.assertEqual(e.exception.code,404)
 def test_user_without_reports_cannot_see_others_tickets(self):
  ticket=self.pos.sale(1,dict(request_key='sale',items=[dict(product_id=self.pid,quantity=1)],payments=[dict(method='cash',amount_cents=1160)]))
  self.pos.save_user(1,dict(username='restricted',display_name='Prueba',secret='test-password',permissions=[]))
  with self.request('/api/login',dict(username='restricted',secret='test-password')) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  for path in ['/api/ticket?id='+str(ticket['id']),'/api/sales/history']:
   with self.assertRaises(HTTPError) as e:self.call(path)
   self.assertEqual(e.exception.code,403)

 def test_settings_logo_promotions_credit_and_cost_visibility(self):
  import test_branding
  png=base64.b64encode(test_branding.sample_png()).decode()
  self.call('/api/settings',dict(name='Farmacia QA',receipt_footer='Prueba'))
  self.call('/api/branding',dict(png_base64=png))
  with self.request('/business-logo.png') as r:self.assertEqual(r.read(),test_branding.sample_png())
  self.call('/api/promotions/save',dict(product_id=self.pid,name='Oferta',price_cents=700,schedule_type='permanent'))
  self.call('/api/sales',dict(request_key='credit-http',customer_id=1,on_account=True,items=[dict(product_id=self.pid,quantity=1)],payments=[]))
  payment=self.call('/api/credit/payment',dict(request_key='payment-http',customer_id=1,amount_cents=700,method='cash',received_cents=1000));self.assertEqual(payment['change_cents'],300)
  with self.request('/direccion/api/login',dict(username='admin',secret='test-only-password')) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  self.call('/direccion/api/settings',dict(name='Farmacia Dirección',receipt_footer='Prueba'))
  self.call('/direccion/api/branding',dict(remove=True))
  self.pos.save_user(1,dict(username='manager-no-costs',display_name='QA',secret='test-password',permissions=['users.manage','reports.view']))
  with self.request('/direccion/api/login',dict(username='manager-no-costs',secret='test-password')) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  self.assertNotIn('purchase_cost_cents',self.call('/direccion/api/summary')['products'][0])
  with self.request('/api/login',dict(username='manager-no-costs',secret='test-password')) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  self.assertNotIn('unit_cost_cents',self.call('/api/inventory/batches?product_id='+str(self.pid))[0])
