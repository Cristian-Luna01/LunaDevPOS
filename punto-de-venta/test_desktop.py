import tempfile
from pathlib import Path
import unittest
from core import POS, Error
from desktop import create_account, initialized, can_stop
import branding
class DesktopTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'pos.sqlite3';self.pos=POS(self.path)
 def tearDown(self):self.temp.cleanup()
 def test_invalid_setup_preserves_empty_installation(self):
  for values in [('', 'admin','12345678','12345678'),('Farmacia','a b','12345678','12345678'),('Farmacia','admin','short','short'),('Farmacia','admin','12345678','87654321')]:
   with self.assertRaises(Error):create_account(self.pos,*values)
   self.assertFalse(self.path.exists())
 def test_setup_persists_empty_inventory_and_settings(self):
  self.assertFalse(initialized(self.path));create_account(self.pos,' Mi farmacia ',' JEFA ','12345678','12345678');self.assertTrue(initialized(self.path))
  reopened=POS(self.path);reopened.login('jefa','12345678');self.assertEqual(branding.settings(reopened)['name'],'Mi farmacia')
  with reopened.db() as db:
   for table in ['products','sales','customers','cash_shifts','customer_ledger']:self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
  with self.assertRaises(Error):create_account(reopened,'Otra','admin','12345678','12345678')
  self.assertEqual(branding.settings(reopened)['name'],'Mi farmacia')
 def test_close_requires_closed_shifts(self):
  create_account(self.pos,'Farmacia','admin','12345678','12345678');self.assertTrue(can_stop(self.pos));sid=self.pos.open_shift(1,{'register_id':'A','opening_cents':0})['id'];self.assertFalse(can_stop(self.pos));self.pos.close_shift(1,{'shift_id':sid,'counted_cents':0});self.assertTrue(can_stop(self.pos))
