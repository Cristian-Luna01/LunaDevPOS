import json,threading,unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import test_pos
from app import Handler
class CustomerHTTPTest(unittest.TestCase):
 receive=test_pos.POSTest.receive
 def setUp(self):
  test_pos.POSTest.setUp(self)
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.pos=self.pos
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.base='http://127.0.0.1:'+str(self.server.server_port)
  with self.request('/api/login',{'username':'admin','secret':'test-only-password'}) as response:self.cookie=response.headers['Set-Cookie'].split(';')[0]
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
 def request(self,path,data=None):
  return urlopen(Request(self.base+path,json.dumps(data).encode() if data is not None else None,headers={'Cookie':getattr(self,'cookie',''),'Content-Type':'application/json','X-POS-Request':'1'}))
 def test_create_customer_without_id_then_edit_and_query_wallet(self):
  with self.request('/api/customers/save',{'name':'Cliente nuevo','phone':'5550000000','discount_bps':0}) as response:cid=json.load(response)['id']
  self.assertEqual(cid,2)
  with self.request('/api/credit?q=Cliente+nuevo') as response:rows=json.load(response)
  self.assertEqual([(r['id'],r['balance_cents']) for r in rows],[(2,0)])
  with self.request('/api/customers/save',{'id':cid,'name':'Nombre editado','phone':'5550000000','discount_bps':500}) as response:self.assertEqual(json.load(response)['id'],cid)
  with self.request('/api/customers?q=Nombre+editado') as response:self.assertEqual(json.load(response)[0]['discount_bps'],500)
  with self.request('/api/credit?id='+str(cid)) as response:self.assertEqual(json.load(response),{'balance_cents':0,'movements':[]})
  with self.pos.db() as db:
   self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],1)
   self.assertEqual(db.execute('SELECT COUNT(*) FROM customers').fetchone()[0],2)
 def test_unknown_customer_update_rejected_without_creating_or_changing_users(self):
  with self.assertRaises(HTTPError) as error:self.request('/api/customers/save',{'id':999,'name':'No existe','discount_bps':0})
  self.assertEqual(error.exception.code,404)
  with self.pos.db() as db:
   self.assertEqual(db.execute('SELECT COUNT(*) FROM customers').fetchone()[0],1)
   self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],1)

 def test_full_customer_list_and_search_beyond_fifty(self):
  with self.pos.db() as db:
   db.executemany('INSERT INTO customers(name,phone,discount_bps) VALUES (?,?,0)', [('Cliente %03d'%i,'555%03d'%i) for i in range(100)])
  with self.request('/api/customers') as response:rows=json.load(response)
  self.assertEqual(len(rows),101)
  with self.request('/api/customers?q=Cliente+099') as response:found=json.load(response)
  self.assertEqual([r['name'] for r in found],['Cliente 099'])
  with self.request('/api/customers?q=555099') as response:found=json.load(response)
  self.assertEqual([r['name'] for r in found],['Cliente 099'])
