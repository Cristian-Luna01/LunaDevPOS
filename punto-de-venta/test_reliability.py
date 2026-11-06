import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from core import POS,Error
import test_pos
import pending_operations as pending
from external_backup import BackupService,save_settings,restore_test
from performance import product_search

class ReliabilityTest(unittest.TestCase):
    setUp=test_pos.POSTest.setUp
    tearDown=test_pos.POSTest.tearDown
    receive=test_pos.POSTest.receive
    body=test_pos.POSTest.body

    def test_committed_sale_after_restart_is_recovered_once(self):
        body=self.body('durable-sale')
        pending.prepare(self.pos,1,{'path':'/sales','payload':body})
        original=pending.recover(self.pos,1,{'request_key':body['request_key']})
        restarted=POS(self.pos.path)
        self.assertEqual(len(pending.listing(restarted,1)['items']),1)
        recovered=pending.recover(restarted,1,{'request_key':body['request_key']})
        self.assertEqual(recovered['id'],original['id'])
        with restarted.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sales').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0],19)
        with self.assertRaises(Error):pending.finish(restarted,1,{'request_key':body['request_key']},cancel=True)
        pending.finish(restarted,1,{'request_key':body['request_key']})
        self.assertEqual(pending.listing(restarted,1)['items'],[])

    def test_pending_failure_cannot_be_acked_and_can_be_cancelled(self):
        body=self.body('failed',qty=10000)
        pending.prepare(self.pos,1,{'path':'/sales','payload':body})
        with self.assertRaises(Error):pending.recover(self.pos,1,{'request_key':'failed'})
        with self.assertRaises(Error):pending.finish(self.pos,1,{'request_key':'failed'})
        with self.assertRaises(Error):pending.prepare(self.pos,1,{'path':'/sales','payload':self.body('new')})
        pending.finish(self.pos,1,{'request_key':'failed'},cancel=True)

    def test_pending_identity_user_and_shift_are_enforced(self):
        pending.prepare(self.pos,1,{'path':'/sales','payload':self.body('old-shift')})
        uid=self.pos.save_user(1,{'username':'other','display_name':'Otro','secret':'test-password','permissions':['sell']})['id']
        self.assertEqual(pending.listing(self.pos,uid)['items'],[])
        with self.assertRaises(Error):pending.recover(self.pos,uid,{'request_key':'old-shift'})
        self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':10000})
        self.pos.open_shift(1,{'register_id':'A','opening_cents':0})
        with self.assertRaises(Error):pending.recover(self.pos,1,{'request_key':'old-shift'})

    def test_restock_retries_preserve_result_and_quantity(self):
        body={'product_id':self.pid,'quantity':5,'request_key':'restock'}
        pending.prepare(self.pos,1,{'path':'/inventory/restock','payload':body})
        first=pending.recover(self.pos,1,{'request_key':'restock'})
        self.assertEqual(first,pending.recover(self.pos,1,{'request_key':'restock'}))
        self.assertEqual(first['stock_after'],25)

    def test_external_backup_can_restore_and_detects_corruption(self):
        with tempfile.TemporaryDirectory() as external:
            save_settings(self.pos,1,{'directory':external})
            result=BackupService(self.pos).run(verify_restore=True)
            self.assertTrue(result['restore_test']['ok'])
            raw=Path(result['path']).read_bytes()
            with self.assertRaises(Error):restore_test(raw[:-1])
        with self.assertRaises(Error):save_settings(self.pos,1,{'directory':str(Path(self.pos.path).parent)})

    def test_search_updates_and_rebuild_after_restore(self):
        with self.pos.db() as db:
            condition,args=product_search(db,'duct')
            self.assertTrue(db.execute('SELECT p.id FROM products p WHERE '+condition,args).fetchone())
        self.pos.save_product(1,dict(id=self.pid,barcode='123',name='Renombrado',category_id=1,price_cents=1160,cost_cents=500))
        with self.pos.db() as db:
            condition,args=product_search(db,'nombr')
            self.assertEqual(db.execute('SELECT p.id FROM products p WHERE '+condition,args).fetchone()[0],self.pid)

    def test_killed_process_rolls_back_uncommitted_stock(self):
        code="""import sys,time
from core import POS
p=POS(sys.argv[1])
with p.db(True) as db:
 db.execute('UPDATE batches SET quantity=0')
 print('ready',flush=True)
 time.sleep(60)
"""
        process=subprocess.Popen([sys.executable,'-c',code,self.pos.path],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(),'ready')
            process.kill();process.communicate(timeout=5)
        finally:
            if process.poll() is None:process.kill();process.communicate(timeout=5)
        with self.pos.db() as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0],20)
