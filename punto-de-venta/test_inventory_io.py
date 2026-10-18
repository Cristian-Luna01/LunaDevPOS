import base64
import contextlib
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from core import POS, Error, ROOT, fingerprint
import inventory_io as transfer

def upload(raw,**options):
    if isinstance(raw,str):raw=raw.encode('utf-8')
    return {'file_base64':base64.b64encode(raw).decode(),'selection':'numeric',**options}

def legacy(rows):
    out=io.StringIO();writer=csv.writer(out,delimiter='\t');writer.writerow(transfer.HEADERS);writer.writerows(rows)
    return out.getvalue()

class TransferTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.pos=POS(Path(self.tmp.name)/'db.sqlite3')
        self.pos.initialize('admin','test-password')
        self.sample=legacy([['00123','Jabón','$10.50','$20.00','$0.00','5.00','2','Cuidado personal'],
           ['002','Pasta dental','5','10','0','0','0','Perfumería'],['003','Sin dato','4','6','0','N/A','0','Otros']])

    def tearDown(self):self.tmp.cleanup()

    def import_data(self,raw=None,**options):
        payload=upload(raw or self.sample,**options)
        p=transfer.preview(self.pos,1,payload)
        payload.update(revision=p['revision'],request_key=options.get('request_key','request-1'))
        return transfer.import_inventory(self.pos,1,payload),payload

    def scalar(self,sql):
        with self.pos.db() as db:return db.execute(sql).fetchone()[0]

    def test_legacy_positive_na_zero_codes_and_cp1252(self):
        payload=upload(self.sample.encode('cp1252'),selection='positive')
        p=transfer.preview(self.pos,1,payload)
        self.assertEqual((p['candidates'],p['skipped_na'],p['skipped_zero']),(1,1,1))
        self.assertEqual(p['products'][0]['barcode'],'00123')
        self.assertEqual(p['products'][0]['name'],'Jabón')
        r,_=self.import_data()
        self.assertEqual((r['created'],r['units']),(2,5))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM batches WHERE expires_on IS NULL'),1)

    def test_undated_sale_and_fefo(self):
        self.import_data()
        self.pos.receive(1,{'product_id':1,'quantity':1,'expires_on':'2090-01-01','unit_cost_cents':1000,'reason':'Compra'})
        self.pos.open_shift(1,{'register_id':'A','opening_cents':0})
        self.pos.sale(1,{'request_key':'s','items':[{'product_id':1,'quantity':2}], 'payments':[{'method':'cash','amount_cents':4000}]})
        self.assertEqual(self.scalar("SELECT quantity FROM batches WHERE expires_on='2090-01-01'"),0)
        self.assertEqual(self.scalar('SELECT quantity FROM batches WHERE expires_on IS NULL'),4)

    def test_add_expiry_later_updates_audit_and_sale_eligibility(self):
        self.import_data()
        self.pos.edit_batch(1,dict(batch_id=1,expires_on='2000-01-01',lot_number='REAL-123',reason='Captura de fecha real'))
        self.pos.open_shift(1,dict(register_id='A',opening_cents=0))
        with self.assertRaises(Error):self.pos.sale(1,dict(request_key='expired',items=[dict(product_id=1,quantity=1)],payments=[dict(method='cash',amount_cents=2000)]))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM audit_log WHERE action='batch.edit'"),1)

    def test_idempotency_skip_and_stale_preview(self):
        r,payload=self.import_data()
        self.assertEqual(transfer.import_inventory(self.pos,1,payload),r)
        r,_=self.import_data(request_key='again')
        self.assertEqual(r['skipped'],2)
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM batches'),5)
        payload=upload(self.sample);p=transfer.preview(self.pos,1,payload)
        self.pos.receive(1,{'product_id':1,'quantity':1,'unit_cost_cents':100,'reason':'Compra'})
        with self.assertRaises(Error):transfer.import_inventory(self.pos,1,dict(payload,revision=p['revision'],request_key='stale'))

    def test_replace_requires_closed_shifts_and_preserves_kardex(self):
        self.import_data()
        sid=self.pos.open_shift(1,{'register_id':'A','opening_cents':0})['id']
        with self.assertRaises(Error):self.import_data(request_key='replace',existing='replace')
        self.pos.close_shift(1,{'shift_id':sid,'counted_cents':0})
        with self.pos.db(True) as db:db.execute("UPDATE products SET requires_prescription=1,generic_name='Sustancia' WHERE id=1")
        r,_=self.import_data(request_key='replace',existing='replace')
        self.assertEqual(r['updated'],2)
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM batches'),5)
        self.assertEqual(self.scalar('SELECT requires_prescription FROM products WHERE id=1'),1)
        with self.pos.db() as db:
            for row in db.execute('SELECT b.quantity,SUM(m.quantity_delta) balance FROM batches b JOIN inventory_movements m ON m.batch_id=b.id GROUP BY b.id'):
                self.assertEqual(row['quantity'],row['balance'])

    def test_exclusions_invalid_and_duplicate_rows(self):
        source=legacy([['001','Valid','1','2','0',2,0,'A'],['001','Duplicate','1','2','0',5,0,'A'],['','Missing code','1','2','0',1,0,'A'],['004','Excluded','1','2','0',3,0,'A']])
        payload=upload(source);p=transfer.preview(self.pos,1,payload)
        self.assertEqual(len(p['issues']),2)
        with self.assertRaises(Error):transfer.import_inventory(self.pos,1,dict(payload,revision=p['revision'],request_key='bad'))
        r=transfer.import_inventory(self.pos,1,dict(payload,revision=p['revision'],request_key='filtered',skip_invalid=True,excluded_rows=[5]))
        self.assertEqual((r['created'],r['units']),(1,2))

    def test_native_inventory_round_trip_and_csv(self):
        self.import_data()
        self.pos.receive(1,{'product_id':1,'quantity':2,'unit_cost_cents':1000,'expires_on':'2080-04-30','lot_number':'ABC','reason':'Compra'})
        for kind in ('json','csv','xls'):
            raw,filename,mime=transfer.export_inventory(self.pos,1,kind)
            products,summary=transfer.parse_file(upload(raw))
            self.assertEqual(summary['issues'],[])
            self.assertEqual(len(products),2)
            self.assertEqual(products[0]['barcode'],'00123')
            self.assertEqual(sum(b['quantity'] for b in products[0]['batches']),7)
            if kind=='json':
                self.assertEqual(products[0]['batches'][1]['expires_on'],'2080-04-30')
                self.assertEqual(products[0]['batches'][1]['lot_number'],'ABC')

    def test_backup_restore_with_sale_and_session_revocation(self):
        self.import_data()
        self.pos.open_shift(1,{'register_id':'A','opening_cents':1000})
        self.pos.sale(1,{'request_key':'sale','items':[{'product_id':1,'quantity':1}], 'payments':[{'method':'cash','amount_cents':2000}]})
        raw,_,_=transfer.backup(self.pos,1)
        fresh=POS(Path(self.tmp.name)/'fresh.sqlite3');fresh.initialize('temporary','temporary-password')
        token=fresh.login('temporary','temporary-password')
        payload=upload(raw,confirmation='RESTAURAR')
        self.assertTrue(transfer.restore_preview(fresh,1,payload)['eligible'])
        result=transfer.restore(fresh,1,payload)
        self.assertEqual(result['sales'],1)
        with self.assertRaises(Error):fresh.session_user(token)
        self.assertTrue(fresh.login('admin','test-password'))
        with fresh.db() as db:
            self.assertEqual(db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0],4)
            self.assertEqual(db.execute('SELECT total_cents FROM sales').fetchone()[0],2000)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM inventory_movements').fetchone()[0],2)
            self.assertEqual(fresh.report(db,1)['expected_cents'],3000)
        with self.assertRaises(Error):transfer.restore(fresh,1,payload)

    def test_corrupted_backup_rejected_and_failed_restore_rolls_back(self):
        self.import_data()
        raw,_,_=transfer.backup(self.pos,1)
        doc=json.loads(raw);doc['tables']['products'][0]['category_id']=999999
        with self.assertRaises(Error):transfer.read_backup(upload(json.dumps(doc)))
        doc.pop('sha256');doc['sha256']=fingerprint(doc)
        fresh=POS(Path(self.tmp.name)/'fresh.sqlite3');fresh.initialize('temp','temporary-password')
        with self.assertRaises(Error):transfer.restore(fresh,1,upload(json.dumps(doc),confirmation='RESTAURAR'))
        self.assertTrue(fresh.login('temp','temporary-password'))
        with fresh.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM products').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0],8)

    def test_import_failure_is_atomic_and_permissions_enforced(self):
        with self.pos.db(True) as db:
            db.execute("CREATE TRIGGER reject_import BEFORE INSERT ON inventory_imports BEGIN SELECT RAISE(ABORT,'fault'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.import_data()
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM products'),0)
        uid=self.pos.save_user(1,dict(username='cashier',display_name='Caja',secret='123456',permissions=['sell']))['id']
        with self.assertRaises(Error):transfer.preview(self.pos,uid,upload(self.sample))
        with self.assertRaises(Error):transfer.export_inventory(self.pos,uid,'csv')
        with self.assertRaises(Error):transfer.backup(self.pos,uid)

    def test_legacy_schema_migration_preserves_relations(self):
        oldpath=Path(self.tmp.name)/'old.sqlite3'
        schema=(ROOT/'schema.sql').read_text(encoding='utf-8').replace('expires_on TEXT CHECK','expires_on TEXT NOT NULL CHECK')
        with contextlib.closing(sqlite3.connect(oldpath)) as db:db.executescript(schema)
        old=POS(oldpath);old.initialize('admin','test-password')
        pid=old.save_product(1,dict(barcode='OLD',name='Original',category_id=1,cost_cents=100,price_cents=200,max_stock=100))['id']
        old.receive(1,dict(product_id=pid,quantity=2,unit_cost_cents=100,expires_on='2090-01-01',reason='Original'))
        old.open_shift(1,dict(register_id='A',opening_cents=0))
        old.sale(1,dict(request_key='original-sale',items=[dict(product_id=pid,quantity=1)],payments=[dict(method='cash',amount_cents=200)]))
        with contextlib.closing(sqlite3.connect(oldpath)) as db:db.execute('PRAGMA user_version=0')
        migrated=POS(oldpath)
        self.assertTrue(list(Path(self.tmp.name).glob('old.sqlite3.antes-v2-*.sqlite3')))
        migrated.receive(1,dict(product_id=pid,quantity=3,unit_cost_cents=100,reason='Sin fecha'))
        with migrated.db() as db:
            self.assertIsNone(db.execute('PRAGMA foreign_key_check').fetchone())
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sale_item_batches').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0],4)
            self.assertIn('backup.manage',migrated.permissions(db,1))

if __name__=='__main__':unittest.main(verbosity=2)
