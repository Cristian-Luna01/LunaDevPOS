import json
import sqlite3
import unittest
from pathlib import Path
import test_pos
from branch_sync import BranchSync, snapshot, service_url, database
from core import Error
import credit

class BranchSyncTest(unittest.TestCase):
    setUp=test_pos.POSTest.setUp
    tearDown=test_pos.POSTest.tearDown
    receive=test_pos.POSTest.receive

    def test_cash_credit_collection_uses_same_historical_cost(self):
        self.pos.sale(1,dict(request_key='paid',items=[dict(product_id=self.pid,quantity=1)],payments=[dict(method='cash',amount_cents=1160,tendered_cents=1160)]))
        self.pos.sale(1,dict(request_key='credit',customer_id=1,on_account=True,items=[dict(product_id=self.pid,quantity=1)],payments=[]))
        before=snapshot(self.pos)
        self.assertEqual(before['daily'][-1]['net_cents'],1160)
        credit.payment(self.pos,1,dict(request_key='abono',customer_id=1,amount_cents=500,method='cash'))
        after=snapshot(self.pos)
        self.assertEqual(after['daily'][-1]['net_cents'],1660)
        self.assertEqual(after['daily'][-1]['payments_by_method']['cash'],1660)
        self.assertEqual(after['products'][0]['stock'],18)
        self.assertEqual(len(after['daily']),31)
        self.assertNotIn('customers',after)
        self.assertNotIn('users',after)

    def test_config_persists_encrypted_and_retries_without_duplicate_totals(self):
        sync=BranchSync(self.pos)
        data=dict(url='https://test.workers.dev',name='Centro',token='a'*64)
        sync.configure(data)
        with database(sync.path) as db:
            self.assertNotEqual(db.execute('SELECT token FROM link').fetchone()[0],data['token'])
        with self.assertRaises(OSError):
            sync.once(lambda *args: (_ for _ in ()).throw(OSError('Offline')))
        calls=[]
        def send(url,token,body):
            p=json.loads(body);calls.append(p)
            self.assertEqual(token,data['token'])
            return {'ok':True,'revision':p['revision']}
        sync.once(send)
        self.assertEqual(calls[0]['revision'],2)
        restarted=BranchSync(self.pos);restarted.once(send)
        snapshots=[p for p in calls if 'daily' in p]
        self.assertGreater(snapshots[1]['revision'],snapshots[0]['revision'])
        self.assertEqual(snapshots[0]['daily'],snapshots[1]['daily'])
        self.assertTrue(restarted.status()['last_ok'])
        self.assertNotIn('token',restarted.status())
        sync.disconnect();self.assertFalse(sync.status()['configured'])
        with self.pos.db() as db:self.assertEqual(db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0],20)

    def test_invalid_url_and_unconfirmed_ack(self):
        for url in ['http://test.workers.dev','https://test.workers.dev.evil.org','https://user:pass@test.workers.dev','https://test.workers.dev/path','https://test.workers.dev/#secret','https://127.0.0.1']:
            with self.assertRaises(Error):service_url(url)
        sync=BranchSync(self.pos);sync.configure(dict(url='https://test.workers.dev',name='Centro',token='b'*64))
        with self.assertRaises(Error):sync.once(lambda *args:{'ok':True,'revision':0})
        self.assertIsNone(sync.status()['last_ok'])

    def test_backfill_keeps_today_first_and_recent_sales_continue(self):
        import datetime as dt
        for n in range(1,10):
            sale=self.pos.sale(1,dict(request_key='old-'+str(n),items=[dict(product_id=self.pid,quantity=1)],payments=[dict(method='cash',amount_cents=1160)]))
            with self.pos.db(True) as db:db.execute('UPDATE sales SET created_at=? WHERE id=?',((dt.date.today()-dt.timedelta(days=n)).isoformat()+'T18:00:00Z',sale['id']))
        sync=BranchSync(self.pos);sync.configure(dict(url='https://qa.workers.dev',name='Centro',token='d'*64));calls=[]
        def send(url,token,body):
            p=json.loads(body);calls.append(p);return {'ok':True,'revision':p['revision']}
        sync.once(send)
        reports=[p for p in calls if 'report' in p];self.assertEqual(len(reports),8);self.assertEqual(reports[0]['day'],dt.date.today().isoformat());self.assertIn('faltan 2 fechas',sync.status()['message'])
        self.pos.sale(1,dict(request_key='new-today',items=[dict(product_id=self.pid,quantity=1)],payments=[dict(method='cash',amount_cents=1160)]))
        calls.clear();sync.once(send)
        self.assertEqual(calls[0]['direction']['net_cents'],1160)
        self.assertEqual(calls[1]['day'],dt.date.today().isoformat())
        self.assertNotIn('en proceso',sync.status()['message'])

    def test_reference_edits_update_existing_history_like_local_reports(self):
        self.pos.sale(1,dict(request_key='old-code',items=[dict(product_id=self.pid,quantity=1)],payments=[dict(method='cash',amount_cents=1160)]))
        sync=BranchSync(self.pos);sync.configure(dict(url='https://qa.workers.dev',name='Centro',token='e'*64));calls=[]
        def send(url,token,body):
            p=json.loads(body);calls.append(p);return {'ok':True,'revision':p['revision']}
        sync.once(send);calls.clear()
        with self.pos.db(True) as db:db.execute('UPDATE products SET barcode=? WHERE id=?',('000777',self.pid))
        sync.once(send);reports=[p for p in calls if 'report' in p];self.assertEqual(len(reports),1)
        self.assertEqual(reports[0]['report']['events'][0]['barcode'],'000777')

if __name__=='__main__':unittest.main()
