import json, unittest
from urllib.error import HTTPError
import test_customer_http

class APIAuditTest(unittest.TestCase):
 setUp=test_customer_http.CustomerHTTPTest.setUp
 tearDown=test_customer_http.CustomerHTTPTest.tearDown
 receive=test_customer_http.CustomerHTTPTest.receive
 request=test_customer_http.CustomerHTTPTest.request
 def call(self,path,data=None):
  with self.request(path,data) as r:return json.load(r)
 def test_product_lifecycle_inventory_and_report_routes(self):
  data=dict(barcode='AUDIT',name='Medicamento de prueba',category_id=1,cost_cents=550,price_cents=1000,tax_bps=0)
  pid=self.call('/api/products/save',data)['id']
  bid=self.call('/api/inventory/receive',dict(product_id=pid,quantity=12,unit_cost_cents=550,reason='Factura de prueba'))['id']
  product=self.call('/api/products?q=AUDIT')[0]
  self.assertEqual((product['stock'],product['price_cents']),(12,1000))
  self.call('/api/products/save',dict(data,reason='Cambio de lista QA',id=pid,name='Medicamento editado',price_cents=1100))
  ticket=self.call('/api/sales',dict(request_key='http-sale',customer_id=1,items=[dict(product_id=pid,quantity=3)],payments=[dict(method='cash',amount_cents=2970,tendered_cents=5000)]))
  self.assertEqual((ticket['total_cents'],ticket['discount_cents'],ticket['change_cents']),(2970,330,2030))
  self.assertEqual(self.call('/api/inventory/availability?ids='+str(pid))[0]['stock'],9)
  self.assertEqual(self.call('/api/ticket?id='+str(ticket['id']))['id'],ticket['id'])
  self.assertEqual(self.call('/api/customers/history?id=1')[0]['total_cents'],2970)
  self.assertEqual(len(self.call('/api/inventory/batches?product_id='+str(pid))),1)
  self.assertEqual(len(self.call('/api/inventory/kardex?product_id='+str(pid))),2)
  self.assertTrue(any(r['id']==bid for r in self.call('/api/inventory/undated')))
  self.call('/api/inventory/batch/edit',dict(batch_id=bid,expires_on='2099-12-31',lot_number='LOTE',reason='Captura'))
  self.assertFalse(any(r['id']==bid for r in self.call('/api/inventory/undated')))
  self.assertIsInstance(self.call('/api/inventory/alerts'),list)
  self.assertIsInstance(self.call('/api/inventory/overview')['products'],list)
  self.assertIsInstance(self.call('/api/categories'),list)
  self.assertIsInstance(self.call('/api/users'),list)
  self.assertIsInstance(self.call('/api/promotions'),list)
  self.assertEqual(self.call('/api/reports/general')['net_sales_cents'],2970)
  sid=self.sid
  self.assertEqual(self.call('/api/shifts/report?id='+str(sid))['expected_cents'],12970)
  self.call('/api/shifts/close',dict(shift_id=sid,counted_cents=12970))
  self.assertEqual(self.call('/api/shifts/report?id='+str(sid))['difference_cents'],0)
  self.call('/api/products/deactivate',dict(id=pid))
  self.assertEqual(self.call('/api/products?q=AUDIT'),[])
  self.assertEqual(self.call('/api/ticket?id='+str(ticket['id']))['items'][0]['product_name'],'Medicamento editado')
  self.call('/api/logout',{})
  with self.assertRaises(HTTPError) as e:self.call('/api/me')
  self.assertEqual(e.exception.code,401)
 def test_supplier_save_edit_and_invalid_routes(self):
  sid=self.call('/api/suppliers/save',dict(business_name='Proveedor nuevo',phone='555',credit_days=15))['id']
  self.call('/api/suppliers/save',dict(id=sid,business_name='Proveedor editado',credit_days=30))
  row=next(r for r in self.call('/api/suppliers') if r['id']==sid)
  self.assertEqual((row['business_name'],row['credit_days']),('Proveedor editado',30))
  for path,data,status in [('/api/suppliers/save',dict(id=999,business_name='Desconocido'),404),('/api/products/deactivate',dict(id=999),404),('/api/reports/general?from_id=0',None,400),('/api/shifts/report?id=999',None,404),('/api/inventory/availability',None,400),('/api/no-existe',None,404)]:
   with self.assertRaises(HTTPError) as error:self.call(path,data)
   self.assertEqual(error.exception.code,status)
