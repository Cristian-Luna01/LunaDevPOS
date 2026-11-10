import unittest
from test_owner_access import OwnerAccessTest
from core import Error

class OwnerLocalTest(unittest.TestCase):
 setUpBase=OwnerAccessTest.setUpBase
 tearDownBase=OwnerAccessTest.tearDownBase
 receive=OwnerAccessTest.receive
 setUp=OwnerAccessTest.setUp
 tearDown=OwnerAccessTest.tearDown
 def test_local_http_cannot_be_enabled(self):
  with self.assertRaises(Error) as error:self.manager.start_local()
  self.assertEqual(error.exception.status,403)
  self.assertFalse(self.manager.status()['local_enabled'])
  self.assertEqual(self.manager.status()['local_urls'],[])
