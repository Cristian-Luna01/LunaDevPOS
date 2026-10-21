"""Equivalencia de consultas e índices sobre una base aislada."""
import datetime as dt
import unittest
from unittest.mock import patch
import test_pos as fixture
import analytics,cash_basis,catalog_search,direction_replica
from core import POS
from performance_indexes import install

class PerformanceTest(unittest.TestCase):
 setUp=fixture.POSTest.setUp
 tearDown=fixture.POSTest.tearDown
 receive=fixture.POSTest.receive
 def test_search_matches_previous_query_with_expired_empty_and_pagination(self):
  today=dt.date.today().isoformat()
  with self.pos.db(True) as db:
   db.execute('UPDATE batches SET expires_on=? WHERE id=?',(today,self.early))
   db.executemany('INSERT INTO products(barcode,name,generic_name,category_id,cost_cents,price_cents,tax_bps) VALUES(?,?,?,1,500,1000,0)',[(str(900+i),'Producto '+str(i),'Genérico') for i in range(55)])
  with self.pos.db() as db:
   for include_costs in (False,True):
    columns='p.id,p.barcode,p.name,p.generic_name,p.category_id,p.price_cents,p.tax_bps,p.min_stock,p.max_stock,p.reorder_point,p.requires_prescription'+(',p.cost_cents' if include_costs else '')
    for q in ('123','Producto','Genérico','inexistente','%',''):
     for offset in (0,40,80):
      expected=[dict(r) for r in db.execute(f'''SELECT {columns},COALESCE(b.stock,0) stock,COALESCE(b.physical_stock,0) physical_stock FROM products p
       LEFT JOIN (SELECT product_id,SUM(CASE WHEN expires_on IS NULL OR expires_on>? THEN quantity ELSE 0 END) stock,SUM(quantity) physical_stock FROM batches GROUP BY product_id) b ON b.product_id=p.id
       WHERE p.active=1 AND (p.barcode=? OR p.name LIKE ? OR p.generic_name LIKE ?) ORDER BY (p.barcode=?) DESC,p.name LIMIT 40 OFFSET ?''',(today,q,'%'+q+'%','%'+q+'%',q,offset))]
      self.assertEqual(catalog_search.search(db,q,offset,include_costs,today),expected)
 def test_streamed_fingerprints_match_previous_single_day_hash(self):
  self.pos.sale(1,{'request_key':'qa','items':[{'product_id':self.pid,'quantity':1}],'payments':[{'method':'cash','amount_cents':1160}]})
  today=dt.date.today().isoformat()
  with self.pos.db(True) as db:
   self.pos.audit(db,1,'inventory.product_count',self.pid,{'before':20,'after':19,'reason':'Revisión ñ'})
  with self.pos.db() as db:
   days=[today,(dt.date.today()-dt.timedelta(days=1)).isoformat()]
   self.assertEqual(direction_replica.history_fingerprints(db,days),{d:direction_replica.day_fingerprint(db,d) for d in days})
 def test_report_reuses_collections_without_changing_profit(self):
  self.pos.sale(1,{'request_key':'credit','customer_id':1,'on_account':True,'items':[{'product_id':self.pid,'quantity':1}],'payments':[]})
  import credit
  credit.payment(self.pos,1,{'request_key':'pay','customer_id':1,'amount_cents':500,'method':'cash'})
  today=dt.date.today().isoformat()
  with self.pos.db() as db,patch('cash_basis.collections',wraps=cash_basis.collections) as calls:
   report=analytics.history(db,{'from':today,'to':today},True)
   self.assertEqual(calls.call_count,1)
   self.assertEqual(report['totals']['net_cents'],500)
   self.assertEqual(report['totals']['profit_cents'],report['totals']['net_cents']-report['totals']['cost_cents'])
 def test_existing_database_gets_indexes_without_changing_rows(self):
  with self.pos.db(True) as db:
   db.execute('DROP INDEX batches_product_received')
   original=list(db.iterdump())
  POS(self.pos.path)
  install(self.pos.path)
  with self.pos.db() as db:
   self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],11)
   self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
   self.assertIn('batches_product_received',{r[1] for r in db.execute('PRAGMA index_list(batches)')})
   self.assertEqual([r for r in db.iterdump() if not r.startswith('CREATE INDEX')],[r for r in original if not r.startswith('CREATE INDEX')])

if __name__=='__main__':unittest.main()
