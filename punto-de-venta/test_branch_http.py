import unittest,json
from urllib.error import HTTPError
import test_customer_http
from branch_sync import BranchSync

class BranchHTTPTest(unittest.TestCase):
    receive=test_customer_http.CustomerHTTPTest.receive
    setUp=test_customer_http.CustomerHTTPTest.setUp
    tearDown=test_customer_http.CustomerHTTPTest.tearDown
    request=test_customer_http.CustomerHTTPTest.request
    def test_settings_only_for_administrator_no_token_disclosure(self):
        self.server.branch_sync=BranchSync(self.pos)
        with self.request('/api/branch-sync/configure',dict(url='https://qa.workers.dev',token='c'*64,name='Centro')) as response:
            data=json.load(response);self.assertTrue(data['configured']);self.assertNotIn('token',data)
        with self.request('/api/branch-sync/status') as response:self.assertNotIn('c'*64,response.read().decode())
        self.pos.save_user(1,dict(username='qa-vendedor',display_name='QA',secret='abcdefgh',permissions=['sell']))
        with self.request('/api/login',dict(username='qa-vendedor',secret='abcdefgh')) as response:self.cookie=response.headers['Set-Cookie'].split(';')[0]
        for path,data in [('/api/branch-sync/status',None),('/api/branch-sync/disconnect',{})]:
            with self.assertRaises(HTTPError) as error:self.request(path,data)
            self.assertEqual(error.exception.code,403)
        self.assertTrue(self.server.branch_sync.status()['configured'])
