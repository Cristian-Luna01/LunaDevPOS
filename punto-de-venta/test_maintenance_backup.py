import base64,json,unittest
from pathlib import Path
import test_pos,credit,inventory_io
from core import POS,Error
class MaintenanceBackupTest(unittest.TestCase):
 setUp=test_pos.POSTest.setUp
 tearDown=test_pos.POSTest.tearDown
 receive=test_pos.POSTest.receive
 def test_complete_restore_preserves_debt_workers_credentials_and_permissions(self):
  worker=self.pos.save_user(1,{'username':'cajeroqa','display_name':'Cajero QA','secret':'123456','permissions':['sell','customers.manage']})['id']
  self.pos.sale(1,{'request_key':'credit-maintenance','customer_id':1,'on_account':True,'items':[{'product_id':self.pid,'quantity':3}],'payments':[]})
  credit.payment(self.pos,1,{'request_key':'payment-maintenance','customer_id':1,'amount_cents':1000,'method':'cash'})
  with self.pos.db() as db:
   balance=credit.read(self.pos,1,{'id':'1'})['balance_cents'];ledger=[dict(row) for row in db.execute('SELECT * FROM customer_ledger ORDER BY id')];secret_hash=db.execute('SELECT password_hash FROM users WHERE id=?',(worker,)).fetchone()[0]
  self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':11000})
  raw,filename,_=inventory_io.backup(self.pos,1);self.assertTrue(filename.endswith('.botica.json'));self.assertNotEqual(secret_hash,'123456')
  fresh=POS(Path(self.temp.name)/'restored.sqlite3');fresh.initialize('temporal','clave-temporal-2026');token=fresh.login('temporal','clave-temporal-2026')
  payload={'filename':filename,'file_base64':base64.b64encode(raw).decode(),'confirmation':'RESTAURAR'}
  preview=inventory_io.restore_preview(fresh,1,payload);self.assertEqual(preview['counts']['customers'],1);self.assertEqual(preview['counts']['customer_ledger'],2)
  inventory_io.restore(fresh,1,payload)
  self.assertTrue(fresh.login('admin','test-only-password'));self.assertTrue(fresh.login('cajeroqa','123456'))
  with self.assertRaises(Error):fresh.session_user(token)
  self.assertEqual(credit.read(fresh,1,{'id':'1'})['balance_cents'],balance)
  with fresh.db() as db:
   self.assertEqual([dict(row) for row in db.execute('SELECT * FROM customer_ledger ORDER BY id')],ledger);self.assertEqual(fresh.permissions(db,worker),{'sell','customers.manage'});self.assertEqual(db.execute('SELECT password_hash FROM users WHERE id=?',(worker,)).fetchone()[0],secret_hash);self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
