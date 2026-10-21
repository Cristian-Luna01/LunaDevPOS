import csv,datetime as dt,io,json,unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from test_customer_http import CustomerHTTPTest
from core import Error

class OperationsReviewTest(unittest.TestCase):
 receive=CustomerHTTPTest.receive
 setUp=CustomerHTTPTest.setUp
 tearDown=CustomerHTTPTest.tearDown
 request=CustomerHTTPTest.request
 def history(self):
  day=dt.date.today().isoformat()
  with self.request('/api/sales/history?from='+day+'&to='+day) as r:return json.load(r)
 def test_customer_creation_has_no_money_or_stock_effect_and_free_sale_is_visible(self):
  with self.pos.db() as db:
   before={table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('sales','sale_items','customer_ledger','cash_movements')}
   stock=db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0]
  with self.request('/api/customers/save',{'name':'Descuento completo','discount_bps':10000}) as r:cid=json.load(r)['id']
  with self.pos.db() as db:
   self.assertEqual(before,{table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in before})
   self.assertEqual(stock,db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0])
  body={'request_key':'free-ticket','customer_id':cid,'items':[{'request_key':'forbidden','product_id':self.pid,'quantity':1}],'payments':[]}
  with self.request('/api/sales',body) as r:ticket=json.load(r)
  self.assertEqual(ticket['total_cents'],0)
  with self.request('/api/sales',body) as r:self.assertEqual(json.load(r)['id'],ticket['id'])
  h=self.history();self.assertEqual((h['totals']['net_cents'],h['totals']['tickets'],h['totals']['sold_units'],h['totals']['profit_cents']),(0,1,1,-500))
  self.assertEqual((h['events'][0]['ticket_id'],h['events'][0]['cents']),(ticket['id'],0))
  with self.pos.db() as db:self.assertEqual(db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0],stock-1)
  day=dt.date.today().isoformat()
  with self.request('/api/sales/history.csv?from='+day+'&to='+day) as r:rows=list(csv.DictReader(io.StringIO(r.read().decode('utf-8-sig'))))
  self.assertEqual(rows[0]['Importe MXN (+venta/-devolución)'],'0.00')
  with self.request('/api/customers/history?id='+str(cid)) as r:self.assertEqual(json.load(r)[0]['id'],ticket['id'])
  with self.request('/direccion/api/login',{'username':'admin','secret':'test-only-password'}) as r:cookie=r.headers['Set-Cookie'].split(';')[0]
  with urlopen(Request(self.base+'/direccion/api/history?from='+day+'&to='+day,headers={'Cookie':cookie})) as r:owner=json.load(r)
  self.assertEqual(owner['events'][0]['ticket_id'],ticket['id'])
 def test_cash_history_across_closed_shifts_excludes_sales_and_opening(self):
  self.pos.cash_movement(1,{'direction':'in','category':'change','amount_cents':3000,'concept':'Cambio para caja'})
  self.pos.cash_movement(1,{'direction':'out','category':'safekeeping','amount_cents':1200,'concept':'Retiro del dueño'})
  h=self.history();self.assertEqual(h['cash_totals'],{'in':3000,'out':1200});self.assertEqual(h['totals']['net_cents'],0)
  self.assertEqual([m['direction'] for m in h['cash_movements']],['out','in'])
  self.assertEqual(h['cash_movements'][0]['concept'],'Retiro del dueño')
  with self.pos.db() as db:
   report=self.pos.report(db,self.sid);self.assertEqual(report['expected_cents'],11800)
  self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':11800})
  self.assertEqual(len(self.history()['cash_movements']),2)
 def test_simple_restock_preserves_product_uses_latest_cost_and_rejects_invalid(self):
  with self.pos.db() as db:before=dict(db.execute('SELECT * FROM products WHERE id=?',(self.pid,)).fetchone())
  with self.request('/api/inventory/restock',{'request_key':'restock-20','product_id':self.pid,'quantity':20}) as r:result=json.load(r)
  self.assertEqual((result['stock_before'],result['stock_after']),(20,40))
  with self.pos.db() as db:
   self.assertEqual(before,dict(db.execute('SELECT * FROM products WHERE id=?',(self.pid,)).fetchone()))
   batch=db.execute('SELECT * FROM batches WHERE id=?',(result['id'],)).fetchone()
   self.assertEqual((batch['quantity'],batch['unit_cost_cents'],batch['expires_on']),(20,500,None))
  for qty in (0,-1,1.5,'20',1000001):
   with self.assertRaises(HTTPError):self.request('/api/inventory/restock',{'request_key':'invalid-'+str(qty),'product_id':self.pid,'quantity':qty})
  with self.assertRaises(HTTPError):self.request('/api/inventory/restock',{'request_key':'unknown','product_id':99999,'quantity':1})
  self.pos.save_user(1,{'username':'limited','display_name':'Limitado','secret':'abcdefgh','permissions':['sell']})
  with self.request('/api/login',{'username':'limited','secret':'abcdefgh'}) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  with self.assertRaises(HTTPError) as e:self.request('/api/inventory/restock',{'request_key':'forbidden','product_id':self.pid,'quantity':1})
  self.assertEqual(e.exception.code,403)

if __name__=='__main__':unittest.main()
