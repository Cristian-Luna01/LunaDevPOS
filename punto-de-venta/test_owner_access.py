import io,json,threading,time,unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import test_pos
from app import Handler
from owner_access import OwnerAccess,BridgeHandler
from core import Error

class OwnerAccessTest(unittest.TestCase):
 setUpBase=test_pos.POSTest.setUp
 tearDownBase=test_pos.POSTest.tearDown
 receive=test_pos.POSTest.receive
 def setUp(self):
  self.setUpBase();self.backend=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.backend.pos=self.pos;self.backend.daemon_threads=True;self.backend.block_on_close=False;self.backend_thread=threading.Thread(target=self.backend.serve_forever,daemon=True);self.backend_thread.start();self.manager=OwnerAccess(self.backend);self.backend.owner_access=self.manager
  self.bridge=ThreadingHTTPServer(('127.0.0.1',0),BridgeHandler);self.bridge.manager=self.manager;self.bridge.daemon_threads=True;self.bridge.block_on_close=False;self.bridge_thread=threading.Thread(target=self.bridge.serve_forever,daemon=True);self.bridge_thread.start();self.manager.hostname='owner-test.trycloudflare.com';self.base=f'http://127.0.0.1:{self.bridge.server_port}'
 def tearDown(self):
  self.manager.stop();self.bridge.shutdown();self.bridge.server_close();self.bridge_thread.join();self.backend.shutdown();self.backend.server_close();self.backend_thread.join();self.tearDownBase()
 def request(self,path,data=None,cookie='',headers=None):
  h={'Host':'owner-test.trycloudflare.com','Cookie':cookie,'Content-Type':'application/json','X-POS-Request':'1','Origin':'https://owner-test.trycloudflare.com'};h.update(headers or {})
  return urlopen(Request(self.base+path,json.dumps(data).encode() if data is not None else None,headers=h))
 def test_owner_login_cookie_and_summary_readonly_page(self):
  with self.request('/direccion/api/login',{'username':'admin','secret':'test-only-password'}) as response:
   cookie=response.headers['Set-Cookie'];self.assertIn('Secure',cookie);self.assertIn('HttpOnly',cookie);cookie=cookie.split(';')[0]
  with self.request('/direccion/api/summary',cookie=cookie) as response:self.assertIn('products',json.load(response))
  with self.request('/direccion/') as response:self.assertIn(b'/owner-readonly.js',response.read())
  with self.request('/owner-readonly.js') as response:self.assertIn(b'ownerReadOnly=true',response.read())
  for path in ['/api/me','/api/backup/export','/api/owner-access/status']:
   with self.assertRaises(HTTPError) as error:self.request(path,cookie=cookie)
   self.assertEqual(error.exception.code,403)
  for path in ['/direccion/api/settings','/direccion/api/branding','/api/sales','/api/users/save']:
   with self.assertRaises(HTTPError) as error:self.request(path,{'name':'No cambiar'},cookie=cookie)
   self.assertEqual(error.exception.code,403)
 def test_anonymous_worker_origin_and_host_denied(self):
  with self.assertRaises(HTTPError) as error:self.request('/direccion/api/summary')
  self.assertEqual(error.exception.code,401)
  self.pos.save_user(1,{'username':'seller','display_name':'QA','secret':'abcdefgh','permissions':['sell']})
  with self.assertRaises(HTTPError) as error:self.request('/direccion/api/login',{'username':'seller','secret':'abcdefgh'})
  self.assertEqual(error.exception.code,403)
  for headers in [{'Origin':'https://evil.example'},{'X-POS-Request':'0'},{'Host':'evil.example'}]:
   with self.assertRaises(HTTPError) as error:self.request('/direccion/api/login',{'username':'admin','secret':'test-only-password'},headers=headers)
   self.assertEqual(error.exception.code,403)
 def test_single_email_and_protected_connector_lifecycle(self):
  for address in ['','*@example.com','one@example.com,two@example.com','bad\n@example.com']:
   with self.assertRaises(Error):self.manager.start(address)
  stopped=threading.Event();ready=threading.Event();commands=[]
  class Process:
   def __init__(self,command,**kwargs):commands.append((command,kwargs));self.stdout=self.output()
   def output(self):
    yield 'https://only-owner.trycloudflare.com\n';yield 'Registered tunnel connection\n';ready.set();stopped.wait(4)
   def poll(self):return 0 if stopped.is_set() else None
   def terminate(self):stopped.set()
   def wait(self,timeout=None):stopped.wait(timeout);return 0
   def kill(self):stopped.set()
  with patch('owner_access.subprocess.Popen',Process):
   self.manager.start('owner@example.com');self.assertTrue(ready.wait(2));state=self.manager.status();self.assertEqual(state['state'],'ready');self.assertEqual(state['url'],'https://only-owner.trycloudflare.com/direccion/');self.assertIn('--allowed-mail',commands[0][0]);self.assertEqual(commands[0][0][-1],'owner@example.com');self.assertNotIn('shell',commands[0][1]);self.manager.stop();self.assertEqual(self.manager.status()['state'],'off');self.assertIsNone(self.manager.process)
