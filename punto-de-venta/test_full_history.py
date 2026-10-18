import io,json,datetime as dt,unittest
from urllib.error import HTTPError
from openpyxl import load_workbook
from test_customer_http import CustomerHTTPTest

class FullHistoryTest(unittest.TestCase):
 receive=CustomerHTTPTest.receive;setUp=CustomerHTTPTest.setUp;tearDown=CustomerHTTPTest.tearDown;request=CustomerHTTPTest.request
 def test_all_four_sheets_exact_values_dates_cash_and_no_formula_injection(self):
  with self.pos.db(True) as db:
   db.execute("UPDATE customers SET discount_bps=10000 WHERE id=1")
   db.execute("UPDATE products SET name='=HYPERLINK(\"bad\")',barcode='00123' WHERE id=?",(self.pid,))
  self.pos.sale(1,{'request_key':'free-full','customer_id':1,'items':[{'product_id':self.pid,'quantity':1}],'payments':[]})
  self.pos.cash_movement(1,{'direction':'in','category':'change','amount_cents':3000,'concept':'Cambio'})
  self.pos.cash_movement(1,{'direction':'out','category':'safekeeping','amount_cents':1200,'concept':'Retiro'})
  day=dt.date.today().isoformat();path='/api/sales/history.xlsx?from='+day+'&to='+day
  with self.request(path) as r:
   raw=r.read();self.assertEqual(r.headers['Content-Type'],'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
   self.assertIn('-completo.xlsx',r.headers['Content-Disposition'])
  workbook=load_workbook(io.BytesIO(raw),data_only=True)
  self.assertEqual(workbook.sheetnames,['Por día','Por producto','Detalle de movimientos','Entradas y salidas','Comisiones tarjeta'])
  self.assertEqual(workbook['Por día']['D6'].value,0)
  self.assertEqual(workbook['Por día']['N6'].value,-5)
  self.assertIsInstance(workbook['Por día']['A6'].value,dt.datetime)
  self.assertEqual(workbook['Por producto']['B6'].value,'00123')
  self.assertEqual(workbook['Por producto']['A6'].value,'=HYPERLINK("bad")')
  formulas=load_workbook(io.BytesIO(raw),data_only=False)
  self.assertEqual(formulas['Por producto']['A6'].data_type,'s')
  self.assertEqual(formulas['Detalle de movimientos']['J6'].value,0)
  self.assertEqual(workbook['Entradas y salidas']['D9'].value,30)
  self.assertEqual(workbook['Entradas y salidas']['E9'].value,12)
  self.assertEqual(workbook['Entradas y salidas']['F9'].value,18)
  self.assertEqual(formulas['Entradas y salidas']['F9'].value,'=SUM(F6:F7)')
  self.assertEqual(formulas['Entradas y salidas'].freeze_panes,'A6')
  self.assertEqual(formulas['Entradas y salidas'].auto_filter.ref,'A5:L7')
 def test_empty_ranges_and_permissions_and_full_unlimited_detail(self):
  day=dt.date.today().isoformat();path='/api/sales/history.xlsx?from='+day+'&to='+day
  with self.request(path) as r:book=load_workbook(io.BytesIO(r.read()),data_only=True)
  self.assertEqual(book['Detalle de movimientos']['A6'].value,'Sin movimientos en estas fechas.')
  self.pos.save_user(1,{'username':'no-report','display_name':'Sin permiso','secret':'abcdefgh','permissions':['customers.manage']})
  with self.request('/api/login',{'username':'no-report','secret':'abcdefgh'}) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  with self.assertRaises(HTTPError) as e:self.request(path)
  self.assertEqual(e.exception.code,403)
 def test_more_than_screen_limit_and_costs_permission(self):
  self.receive(130,30)
  for n in range(125):self.pos.sale(1,{'request_key':'many-'+str(n),'items':[{'product_id':self.pid,'quantity':1}],'payments':[{'method':'cash','amount_cents':1160}]})
  self.pos.save_user(1,{'username':'seller-export','display_name':'Vendedor','secret':'abcdefgh','permissions':['sell']})
  with self.request('/api/login',{'username':'seller-export','secret':'abcdefgh'}) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  day=dt.date.today().isoformat()
  with self.request('/api/sales/history.xlsx?from='+day+'&to='+day) as r:book=load_workbook(io.BytesIO(r.read()),data_only=True)
  self.assertEqual(book['Detalle de movimientos'].max_row,132)
  self.assertEqual(book['Detalle de movimientos']['J132'].value,1450)
  self.assertEqual(book['Por día']['J6'].value,125)
  self.assertEqual(book['Detalle de movimientos'].max_column,12)
  self.assertNotIn('Costo correspondiente MXN',[c.value for c in book['Detalle de movimientos'][5]])

if __name__=='__main__':unittest.main()
