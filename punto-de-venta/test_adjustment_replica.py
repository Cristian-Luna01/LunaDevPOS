import datetime as dt
import unittest,json
import test_pos,inventory_count,direction_replica
from branch_sync import BranchSync

class AdjustmentReplicaTest(unittest.TestCase):
    setUp=test_pos.POSTest.setUp
    tearDown=test_pos.POSTest.tearDown
    receive=test_pos.POSTest.receive

    def test_adjustment_only_day_syncs_counts_and_keeps_author_and_reason_local(self):
        today=dt.date.today().isoformat()
        with self.pos.db() as db:
            before=direction_replica.day_fingerprint(db,today)
        state=inventory_count.read(self.pos,1,{'id':str(self.pid)})
        counts=[{'id':b['id'],'quantity':b['quantity']-2 if i==0 else b['quantity']} for i,b in enumerate(state['batches'])]
        inventory_count.apply(self.pos,1,{'product_id':self.pid,'counted_quantity':18,'batch_counts':counts,'version':state['version'],'reason':'Conteo físico: faltan dos'})
        with self.pos.db() as db:
            current=direction_replica.current(self.pos,db)
            self.assertIn(today,current['history_days'])
            self.assertTrue(current['inventory_adjustments_supported'])
            after=direction_replica.day_fingerprint(db,today)
            self.assertNotEqual(before,after)
            self.assertEqual(after,current['history_fingerprints'][today])
            local=direction_replica.product_adjustments(db,today)[0]
            self.assertEqual(local['reason'],'Conteo físico: faltan dos')
        sync=BranchSync(self.pos);sync.configure({'url':'https://qa.workers.dev','name':'Centro','token':'c'*64});sent=[]
        def send(url,token,body):
            data=json.loads(body);sent.append(data);return {'ok':True,'revision':data['revision']}
        sync.once(send)
        report=next(p['report'] for p in sent if p.get('day')==today)
        a=report['inventory_adjustments'][0]
        self.assertEqual((a['before'],a['after'],a['difference']),(20,18,-2))
        self.assertEqual(a['reason'],'Consulta el motivo en el POS local')
        self.assertEqual(a['user_name'],'Operador')
        self.assertEqual(report['totals']['net_cents'],0)

    def test_price_change_requires_reason_and_records_exact_before_after(self):
        from core import Error
        with self.pos.db() as db:
            original=dict(db.execute('SELECT * FROM products WHERE id=?',(self.pid,)).fetchone())
        edit={**original,'price_cents':1500,'cost_cents':600}
        with self.assertRaises(Error):self.pos.save_product(1,edit)
        with self.pos.db() as db:
            self.assertEqual(db.execute('SELECT price_cents FROM products WHERE id=?',(self.pid,)).fetchone()[0],1160)
        self.pos.save_product(1,{**edit,'reason':'Nueva lista del proveedor'})
        with self.pos.db() as db:
            events=direction_replica.product_adjustments(db,dt.date.today().isoformat())
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['kind'],'price_change')
        self.assertEqual(events[0]['changes'],{'cost_cents':{'before':500,'after':600},'price_cents':{'before':1160,'after':1500}})
        self.assertEqual(events[0]['reason'],'Nueva lista del proveedor')
        self.pos.save_product(1,{**edit,'name':'Nombre actualizado'})
