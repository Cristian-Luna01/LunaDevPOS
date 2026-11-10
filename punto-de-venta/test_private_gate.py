import json,time,unittest
from unittest.mock import patch
from urllib.error import HTTPError
from test_owner_access import OwnerAccessTest
from owner_gate import PrivateGate

class PrivateGateTest(unittest.TestCase):
 receive=OwnerAccessTest.receive;setUpBase=OwnerAccessTest.setUpBase;tearDownBase=OwnerAccessTest.tearDownBase;setUp=OwnerAccessTest.setUp;tearDown=OwnerAccessTest.tearDown;request=OwnerAccessTest.request
 def test_private_code_then_admin_required_and_routes_remain_readonly(self):
  self.manager.gate=PrivateGate();self.manager.mode='private_link'
  with self.request('/direccion/') as r:self.assertIn(b'/owner-gate.js',r.read())
  for path in ['/business-settings','/direccion/api/summary','/direccion/panel.js']:
   with self.assertRaises(HTTPError) as e:self.request(path)
   self.assertEqual(e.exception.code,401)
  with self.assertRaises(HTTPError):self.request('/owner-access/verify',{'code':'wrong'})
  with self.request('/owner-access/verify',{'code':self.manager.gate.key}) as r:
   cookie=r.headers['Set-Cookie'].split(';')[0];self.assertIn('HttpOnly',r.headers['Set-Cookie']);self.assertIn('Secure',r.headers['Set-Cookie'])
  with self.assertRaises(HTTPError) as e:self.request('/direccion/api/summary',cookie=cookie)
  self.assertEqual(e.exception.code,401)
  with self.request('/direccion/api/login',{'username':'admin','secret':'test-only-password'},cookie=cookie) as r:cookie+='; '+r.headers['Set-Cookie'].split(';')[0]
  with self.request('/direccion/api/summary',cookie=cookie) as r:self.assertIn('products',json.load(r))
  for path in ['/api/backup/export','/api/me']:
   with self.assertRaises(HTTPError) as e:self.request(path,cookie=cookie)
   self.assertEqual(e.exception.code,403)
  self.manager.gate=PrivateGate()
  with self.assertRaises(HTTPError) as e:self.request('/direccion/api/summary',cookie=cookie)
  self.assertEqual(e.exception.code,401)
 def test_code_expiry_rate_limit_no_unicode_crash(self):
  gate=PrivateGate()
  for code in (None,[], 'ñ', 'bad','bad'):self.assertEqual(gate.verify(code,'one')[0],403)
  self.assertEqual(gate.verify('bad','one')[0],429)
  self.assertEqual(gate.verify(gate.key,'one')[0],200)
  status,_,cookie=gate.verify(gate.key,'two');self.assertEqual(status,200);self.assertTrue(gate.authorized({'Cookie':cookie.split(';')[0]}))
  with patch('owner_gate.time.time',return_value=time.time()+43201):self.assertFalse(gate.authorized({'Cookie':cookie.split(';')[0]}))

if __name__=='__main__':unittest.main()
