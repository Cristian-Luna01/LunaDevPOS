import datetime as dt
import unittest
from unittest.mock import patch
import test_analytics
from pathlib import Path
from core import Error,POS,fingerprint
import promotions,inventory_io,json,base64

class PromotionRulesTest(unittest.TestCase):
    setUp=test_analytics.AnalyticsTest.setUp
    tearDown=test_analytics.AnalyticsTest.tearDown
    def offer(self,**kw):
        data=dict(product_id=self.pid,name='2 por 15',price_cents=1500,bundle_quantity=2,schedule_type='permanent')
        data.update(kw);promotions.save(self.pos,1,data)
    def test_packages_checkout_and_remainders(self):
        with self.pos.db(True) as db:db.execute('UPDATE products SET price_cents=1000 WHERE id=?',(self.pid,))
        self.pos.receive(1,dict(product_id=self.pid,lot_number='PAQ',quantity=20,unit_cost_cents=100,reason='Prueba'))
        self.offer()
        for qty,expected in [(1,1000),(2,1500),(3,2500),(4,3000),(5,4000)]:
            ticket=self.pos.sale(1,dict(request_key='pack'+str(qty),items=[dict(product_id=self.pid,quantity=qty)],payments=[dict(method='cash',amount_cents=expected)]))
            self.assertEqual(ticket['total_cents'],expected)
        with self.pos.db() as db:p=promotions.active(db)[self.pid]
        self.assertEqual(promotions.total(p,500,2),1000)
    def test_schedules_and_validation(self):
        self.offer(schedule_type='recurring',weekday_mask=1)
        with self.pos.db() as db:
            self.assertIn(self.pid,promotions.active(db,dt.date(2026,10,5)))
            self.assertNotIn(self.pid,promotions.active(db,dt.date(2026,10,6)))
        self.offer(schedule_type='recurring',weekday_mask=1,starts_on='2026-10-06',ends_on='2026-10-12')
        with self.pos.db() as db:
            self.assertNotIn(self.pid,promotions.active(db,dt.date(2026,10,5)))
            self.assertIn(self.pid,promotions.active(db,dt.date(2026,10,12)))
            self.assertNotIn(self.pid,promotions.active(db,dt.date(2026,10,19)))
        for kw in [dict(schedule_type='temporary'),dict(weekday_mask=0),dict(bundle_quantity=0),dict(schedule_type='invalid')]:
            with self.assertRaises(Error):self.offer(**kw)
    def test_upgrade_v3_and_restore_old_promotion(self):
        self.offer(bundle_quantity=1,schedule_type='temporary',starts_on=self.today.isoformat(),ends_on=self.today.isoformat())
        raw,_,_=inventory_io.backup(self.pos,1)
        old=json.loads(raw);old.pop('sha256');old['version']=3
        for row in old['tables']['promotions']:
            for key in promotions.EXTRA_COLUMNS:row.pop(key)
        old['sha256']=fingerprint(old)
        target=POS(Path(self.pos.path).parent/'old-restore.db');target.initialize('admin','test-password')
        inventory_io.restore(target,1,dict(file_base64=base64.b64encode(json.dumps(old).encode()).decode(),filename='old.json',confirmation='RESTAURAR'))
        with target.db(True) as db:
            for key in promotions.EXTRA_COLUMNS:db.execute('ALTER TABLE promotions DROP COLUMN '+key)
            db.execute('PRAGMA user_version=3')
        migrated=POS(target.path)
        with migrated.db() as db:
            p=promotions.active(db)[self.pid]
            self.assertEqual(p['bundle_quantity'],1)
            self.assertEqual(p['schedule_type'],'temporary')
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],11)
