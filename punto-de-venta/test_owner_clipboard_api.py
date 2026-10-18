import json,unittest
from types import SimpleNamespace
from urllib.error import HTTPError
from test_customer_http import CustomerHTTPTest

class OwnerClipboardAPITest(unittest.TestCase):
 receive=CustomerHTTPTest.receive;setUp=CustomerHTTPTest.setUp;tearDown=CustomerHTTPTest.tearDown;request=CustomerHTTPTest.request
 def configure(self):
  self.remote='https://qa-only.trycloudflare.com/direccion/#access=private-test-key'
  self.local='http://192.168.0.103:18786/direccion/'
  self.server.owner_access=SimpleNamespace(status=lambda:{'url':self.remote,'local_urls':[self.local]})
 def test_exact_complete_links_and_reject_stale_or_arbitrary_text(self):
  self.configure();copied=[]
  self.server.copy_owner_link=lambda text:copied.append(text) or True
  for kind,url in [('remote',self.remote),('local',self.local)]:
   with self.request('/api/owner-access/copy',{'kind':kind,'url':url}) as r:self.assertEqual(json.load(r),{'native':True,'copied':True})
  self.assertEqual(copied,[self.remote,self.local])
  for data in [{'kind':'remote','url':'https://old.trycloudflare.com/direccion/'},{'kind':'local','url':'https://evil.invalid/'},{'kind':'wrong','url':self.remote}]:
   with self.assertRaises(HTTPError) as e:self.request('/api/owner-access/copy',data)
   self.assertEqual(e.exception.code,400)
  self.assertEqual(len(copied),2)
 def test_browser_fallback_native_failure_and_permission_denial(self):
  self.configure()
  with self.request('/api/owner-access/copy',{'kind':'remote','url':self.remote}) as r:self.assertEqual(json.load(r),{'native':False,'copied':False})
  self.server.copy_owner_link=lambda text:False
  with self.assertRaises(HTTPError):self.request('/api/owner-access/copy',{'kind':'remote','url':self.remote})
  self.pos.save_user(1,{'username':'limited-copy','display_name':'Vendedor','secret':'abcdefgh','permissions':['sell']})
  with self.request('/api/login',{'username':'limited-copy','secret':'abcdefgh'}) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  with self.assertRaises(HTTPError) as e:self.request('/api/owner-access/copy',{'kind':'remote','url':self.remote})
  self.assertEqual(e.exception.code,403)

if __name__=='__main__':unittest.main()
