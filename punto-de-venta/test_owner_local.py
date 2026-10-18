import json,unittest,http.cookiejar
from unittest.mock import patch
from urllib.request import Request,build_opener,ProxyHandler,HTTPCookieProcessor
from urllib.error import HTTPError
from test_owner_access import OwnerAccessTest
from owner_access import private_address

class OwnerLocalTest(unittest.TestCase):
 setUpBase=OwnerAccessTest.setUpBase
 tearDownBase=OwnerAccessTest.tearDownBase
 receive=OwnerAccessTest.receive
 setUp=OwnerAccessTest.setUp
 tearDown=OwnerAccessTest.tearDown
 def test_local_browser_login_reports_and_write_restrictions(self):
  with patch('owner_access.local_addresses',return_value=['192.168.0.103']):state=self.manager.start_local()
  self.assertTrue(state['local_enabled']);self.assertIn('192.168.0.103',state['local_urls'][0])
  base='http://127.0.0.1:'+str(self.manager.local_bridge.server_port)
  jar=http.cookiejar.CookieJar();browser=build_opener(ProxyHandler({}),HTTPCookieProcessor(jar))
  def request(path,data=None,extra=None):
   headers={'Origin':base,'Content-Type':'application/json','X-POS-Request':'1'};headers.update(extra or {})
   return browser.open(Request(base+path,json.dumps(data).encode() if data is not None else None,headers=headers),timeout=5)
  with self.assertRaises(HTTPError) as e:request('/direccion/api/summary')
  self.assertEqual(e.exception.code,401)
  with request('/direccion/api/login',{'username':'admin','secret':'test-only-password'}) as r:
   self.assertIn('HttpOnly',r.headers['Set-Cookie']);self.assertNotIn('Secure',r.headers['Set-Cookie'])
  with request('/direccion/api/summary') as r:self.assertIn('products',json.load(r))
  with request('/direccion/') as r:self.assertIn(b'/owner-readonly.js',r.read())
  for path,data in [('/api/backup/export',None),('/api/sales',{}),('/direccion/api/settings',{}),('/api/owner-access/status',None)]:
   with self.assertRaises(HTTPError) as e:request(path,data)
   self.assertEqual(e.exception.code,403)
  for extra in [{'Host':'evil.example'},{'Origin':'https://evil.example'},{'X-POS-Request':'0'}]:
   with self.assertRaises(HTTPError) as e:request('/direccion/api/login',{'username':'admin','secret':'test-only-password'},extra)
   self.assertEqual(e.exception.code,403)
  self.manager.stop_local();self.assertFalse(self.manager.status()['local_enabled']);self.assertEqual(self.manager.status()['local_urls'],[])
 def test_public_addresses_rejected_and_worker_denied(self):
  for value in ('8.8.8.8','169.254.1.1','invalid','::1','100.64.0.1'):self.assertFalse(private_address(value))
  for value in ('127.0.0.1','192.168.0.103','10.20.0.1','172.16.0.1'):self.assertTrue(private_address(value))
  with patch('owner_access.local_addresses',return_value=['192.168.0.103']):self.manager.start_local()
  self.pos.save_user(1,{'username':'seller','display_name':'Vendedor','secret':'abcdefgh','permissions':['sell']})
  base='http://127.0.0.1:'+str(self.manager.local_bridge.server_port)
  opener=build_opener(ProxyHandler({}))
  with self.assertRaises(HTTPError) as e:opener.open(Request(base+'/direccion/api/login',json.dumps({'username':'seller','secret':'abcdefgh'}).encode(),headers={'Origin':base,'Content-Type':'application/json','X-POS-Request':'1'}))
  self.assertEqual(e.exception.code,403)

if __name__=='__main__':unittest.main()
