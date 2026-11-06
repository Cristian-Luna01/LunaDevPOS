"""Mediciones repetibles con datos ficticios; no usa la base del negocio."""
import argparse
import datetime as dt
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
SOURCE=Path(__file__).resolve().parents[1]/'punto-de-venta';sys.path.insert(0,str(SOURCE))
from core import POS
from app import Handler
from performance import utc_bounds
import analytics

def measure(fn,repeats=20):
    values=[]
    for _ in range(repeats):
        start=time.perf_counter();fn();values.append((time.perf_counter()-start)*1000)
    values.sort();return {'p50_ms':round(statistics.median(values),3),'p95_ms':round(values[max(0,int(len(values)*.95)-1)],3),'samples':repeats}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='lunadev-rendimiento-') as directory:
        pos=POS(Path(directory)/'test.sqlite3');pos.initialize('qa','benchmark-only-password');shift=pos.open_shift(1,{'register_id':'A','opening_cents':0})['id']
        count=20000;today=dt.date.today().isoformat()
        with pos.db(True) as db:
            db.executemany('INSERT INTO products(id,barcode,name,generic_name,category_id,cost_cents,price_cents,tax_bps) VALUES(?,?,?,?,1,500,1000,0)',[(i,str(7500000000000+i),'Producto '+str(i),'Sustancia '+str(i)) for i in range(1,count+1)])
            db.executemany("INSERT INTO batches(product_id,lot_number,quantity,unit_cost_cents) VALUES(?,'PRUEBA',20,500)",[(i,) for i in range(1,count+1) for _ in range(2)])
            db.executemany('INSERT INTO sales(id,request_key,request_hash,shift_id,user_id,total_cents,tax_cents,discount_cents,created_at) VALUES(?,?,?, ?,1,1000,0,0,?)',[(i,'benchmark-'+str(i),'hash',shift,(today if i>35000 else '2020-01-01')+'T18:00:00.000Z') for i in range(1,40001)])
            db.executemany("INSERT INTO sale_items(sale_id,product_id,category_id,product_name,quantity,unit_price_cents,tax_bps,discount_cents,total_cents,tax_cents) VALUES(?,1,1,'Producto 1',1,1000,0,0,1000,0)",[(i,) for i in range(1,40001)])
        handler=object.__new__(Handler);barcode=str(7500000000000+count)
        def old_search():
            with pos.db() as db:return list(db.execute('''SELECT p.id,COALESCE(b.stock,0) FROM products p LEFT JOIN
              (SELECT product_id,SUM(quantity) stock FROM batches GROUP BY product_id) b ON b.product_id=p.id
              WHERE p.active=1 AND (p.barcode=? OR p.name LIKE ? OR p.generic_name LIKE ?) ORDER BY (p.barcode=?) DESC,p.name LIMIT 40''',(barcode,'%'+barcode+'%','%'+barcode+'%',barcode)))
        lower,upper=utc_bounds(today,today)
        def date_query(old):
            with pos.db() as db:
                return db.execute("SELECT COUNT(*) FROM sales WHERE date(created_at,'localtime')=?" if old else 'SELECT COUNT(*) FROM sales WHERE created_at>=? AND created_at<?',(today,) if old else (lower,upper)).fetchone()[0]
        assert date_query(True)==date_query(False)==5000
        result={'catalog_products':count,'batches':count*2,'sales':40000,'recent_sales':5000,
                'barcode_before':measure(old_search),'barcode_after':measure(lambda:handler.read(pos,1,'/api/products',{'q':barcode})),
                'date_filter_before':measure(lambda:date_query(True)),'date_filter_after':measure(lambda:date_query(False)),
                'history_5000_lines':measure(lambda:history(pos,today),5)}
        with pos.db() as db:result['date_query_plan']=[tuple(r) for r in db.execute('EXPLAIN QUERY PLAN SELECT COUNT(*) FROM sales WHERE created_at>=? AND created_at<?',(lower,upper))]
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

def history(pos,day):
    with pos.db() as db:return analytics.history(db,{'from':day,'to':day},True)

if __name__=='__main__':main()
