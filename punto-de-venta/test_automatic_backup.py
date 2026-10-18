import base64
import datetime as dt
import json
from pathlib import Path
from unittest.mock import patch
import unittest
import inventory_io
import test_pos
from core import POS


class AutomaticBackupTest(unittest.TestCase):
    setUp = test_pos.POSTest.setUp
    tearDown = test_pos.POSTest.tearDown
    receive = test_pos.POSTest.receive

    def test_closed_shift_backup_restores_and_retains_only_recent_automatic_files(self):
        directory = Path(self.pos.path).parent / 'respaldos-automaticos'
        directory.mkdir()
        old = directory / ('turno-99-' + (dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=31)).strftime('%Y%m%dT%H%M%S%fZ') + '.botica.json')
        old.write_text('old')
        manual = directory / 'mi-respaldo.botica.json'
        manual.write_text('manual')
        result = self.pos.close_shift(1, {'shift_id':self.sid, 'counted_cents':10000})
        self.assertTrue(result['automatic_backup']['ok'])
        raw = Path(result['automatic_backup']['path']).read_bytes()
        self.assertFalse(old.exists())
        self.assertTrue(manual.exists())
        document = json.loads(raw)
        self.assertIsNotNone(document['tables']['cash_shifts'][0]['closed_at'])
        fresh = POS(Path(self.temp.name)/'restore.db')
        fresh.initialize('temp', 'temporary-password')
        inventory_io.restore(fresh, 1, {'file_base64':base64.b64encode(raw).decode(), 'filename':'auto.botica.json', 'confirmation':'RESTAURAR'})
        self.assertTrue(fresh.login('admin','test-only-password'))
        with fresh.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM customers').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM products').fetchone()[0],1)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_backup_failure_does_not_undo_close_or_delete_existing_backups(self):
        with patch('automatic_backup.os.replace',side_effect=OSError('disk full')):
            report = self.pos.close_shift(1, {'shift_id':self.sid,'counted_cents':10000})
        self.assertFalse(report['automatic_backup']['ok'])
        with self.pos.db() as db:
            self.assertIsNotNone(db.execute('SELECT closed_at FROM cash_shifts WHERE id=?',(self.sid,)).fetchone()[0])
        retry = self.pos.close_shift(1, {'shift_id':self.sid,'counted_cents':10000})
        self.assertTrue(retry['automatic_backup']['ok'])

    def test_seller_closing_shift_gets_backup_without_manual_backup_permission(self):
        uid = self.pos.save_user(1, {'username':'sellerqa','display_name':'Seller','secret':'seller-password','permissions':['sell']})['id']
        self.pos.close_shift(1, {'shift_id':self.sid,'counted_cents':10000})
        sid = self.pos.open_shift(uid, {'register_id':'A','opening_cents':0})['id']
        result = self.pos.close_shift(uid, {'shift_id':sid,'counted_cents':0})
        self.assertTrue(result['automatic_backup']['ok'])

    def test_each_file_expires_by_own_creation_date(self):
        from automatic_backup import cleanup
        now=dt.datetime.now(dt.timezone.utc)
        directory=Path(self.pos.path).parent/'respaldos-automaticos'
        directory.mkdir()
        paths=[]
        for age in (31,29,1):
            path=directory/f"turno-{age}-{(now-dt.timedelta(days=age)):%Y%m%dT%H%M%S%fZ}.botica.json"
            path.write_text('copy');paths.append(path)
        manual=directory/'respaldo-manual.botica.json';manual.write_text('manual')
        cleanup(self.pos)
        self.assertEqual([p.exists() for p in paths],[False,True,True])
        self.assertTrue(manual.exists())
