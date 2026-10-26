"""Carga HTTP reproducible con importes ficticios y validación de invariantes."""
import argparse,concurrent.futures,json,statistics,sys,tempfile,threading,time
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
root=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(root/'punto-de-venta'))
from core import POS
from app import Handler,ThreadingHTTPServer

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        pos=POS(Path(directory)/'qa.sqlite3');pos.initialize('qa','test-only-load-password');sid=pos.open_shift(1,{'register_id':'QA','opening_cents':10000})['id']
        pid=pos.save_product(1,{'barcode':'QA','name':'Carga ficticia','category_id':1,'cost_cents':1000,'price_cents':2000,'tax_bps':0})['id']
        pos.restock(1,{'product_id':pid,'quantity':1000,'reason':'Carga aislada'})
        token=pos.login('qa','test-only-load-password');server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.pos=pos
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port);durations=[]
        def call(i):
            # El reenvío usa la misma clave: 96 operaciones únicas, 192 solicitudes.
            body={'request_key':'load-'+str(i%96),'items':[{'product_id':pid,'quantity':1}],'payments':[{'method':['cash','debit','transfer'][i%3],'amount_cents':2000}]}
            request=Request(base+'/api/sales',json.dumps(body).encode(),headers={'Cookie':f'pos_session_{server.server_port}={token}','Content-Type':'application/json','X-POS-Request':'1'})
            start=time.perf_counter()
            with build_opener(ProxyHandler({})).open(request,timeout=30) as response:ticket=json.load(response)
            return ticket['id'],(time.perf_counter()-start)*1000
        try:
            started=time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(call,range(192)))
            elapsed=time.perf_counter()-started;durations=sorted(t for _,t in results)
            with pos.db() as db:
                sales=db.execute('SELECT count(*),sum(total_cents) FROM sales').fetchone();stock=db.execute('SELECT sum(quantity) FROM batches WHERE product_id=?',(pid,)).fetchone()[0]
                assert tuple(sales)==(96,192000) and stock==904 and len({i for i,_ in results})==96
                assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                assert not db.execute('PRAGMA foreign_key_check').fetchall()
            report={'clients':8,'http_requests':192,'unique_sales':96,'received_cents':192000,'remaining_stock':904,'integrity':'ok','duplicate_sales':0,'elapsed_seconds':round(elapsed,3),'latency_ms':{'median':round(statistics.median(durations),3),'p95':round(durations[int(len(durations)*.95)-1],3),'max':round(max(durations),3)}}
            Path(args.output).write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':main()
