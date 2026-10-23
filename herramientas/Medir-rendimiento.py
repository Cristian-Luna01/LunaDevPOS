"""Comparación reproducible sobre datos ficticios; nunca usa la instalación real."""
import textwrap
import argparse,datetime as dt,hashlib,json,statistics,sys,tempfile,time,tracemalloc
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args()
sys.path.insert(0,str(Path(a.source).resolve()))
from core import POS
from branch_sync import snapshot
import direction_replica
with tempfile.TemporaryDirectory() as folder:
 pos=POS(Path(folder)/'qa.sqlite3');pos.initialize('qa','test-password-only');pos.open_shift(1,{'register_id':'QA','opening_cents':10000})
 today=dt.date.today()
 with pos.db(True) as db:
  db.executemany('INSERT INTO products(id,barcode,name,generic_name,category_id,cost_cents,price_cents,tax_bps) VALUES(?,?,?,?,1,500,1000,0)',[(i,str(7500000000000+i),'Producto QA '+str(i),'Sustancia QA') for i in range(1,2001)])
  db.executemany('INSERT INTO batches(product_id,lot_number,expires_on,quantity,unit_cost_cents,received_at) VALUES(?,?,NULL,100,500,?)',[(i,'QA-'+str(j),'2026-01-%02dT12:00:00Z'%(j+1)) for i in range(1,2001) for j in range(5)])
  db.executemany('INSERT INTO audit_log(user_id,action,entity_id,details,created_at) VALUES(1,\'inventory.product_count\',1,?,?)',[(json.dumps({'before':100,'after':100,'reason':'Conteo QA '+str(n)}),(today-dt.timedelta(days=n%180)).isoformat()+'T12:00:00Z') for n in range(12000)])
 for i in range(180):
  sale=pos.sale(1,{'request_key':'qa-'+str(i),'items':[{'product_id':i+1,'quantity':1}],'payments':[{'method':'cash','amount_cents':1000}]})
  with pos.db(True) as db:db.execute('UPDATE sales SET created_at=? WHERE id=?',((today-dt.timedelta(days=i)).isoformat()+'T18:00:00Z',sale['id']))
 def measure(fn):
  elapsed=[]
  for _ in range(3):
   start=time.perf_counter();value=fn();elapsed.append((time.perf_counter()-start)*1000)
  return {'median_ms':round(statistics.median(elapsed),3)},value
 result,snap=measure(lambda:snapshot(pos));snap.pop('generated_at');
 with pos.db() as db:
  days=snap['direction']['history_days']
  fingerprints,_=measure(lambda:direction_replica.history_fingerprints(db,days))
  tracemalloc.start();direction_replica.history_fingerprints(db,days);_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
 with pos.db() as db:
  source=(Path(a.source)/'app.py').read_text(encoding='utf-8')
  start=source.index("                q = data.get('q','')[:100]")
  query=compile(textwrap.dedent(source[start:source.index('                active=promotions.active(db)',start)]),'search-query','exec')
  def lookup():
   state={'db':db,'dt':dt,'data':{'q':'7500000001000'},'permissions':{'costs.view'}}
   exec(query,state);return state['result']
  search_result,search_rows=measure(lookup)
 result={'search':search_result,'search_sha256':hashlib.sha256(json.dumps(search_rows,sort_keys=True).encode()).hexdigest(),'fixture':{'products':2000,'batches':10000,'sales':180,'audit_rows':12000},'snapshot':result,'fingerprints':{**fingerprints,'peak_bytes':peak},'result_sha256':hashlib.sha256(json.dumps(snap,sort_keys=True).encode()).hexdigest()}
 Path(a.output).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
