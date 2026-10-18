"""Comisiones estimadas del comercio, separadas del precio del cliente y la caja."""
import json
from core import Error,integer,rounded
TABLES=['card_fee_settings','card_fees']
SCHEMA=["CREATE TABLE IF NOT EXISTS card_fee_settings(id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL CHECK(enabled IN(0,1)),provider TEXT NOT NULL,rate_bps INTEGER NOT NULL CHECK(rate_bps BETWEEN 0 AND 10000),vat_bps INTEGER NOT NULL CHECK(vat_bps BETWEEN 0 AND 1600),fixed_cents INTEGER NOT NULL CHECK(fixed_cents>=0))",
"CREATE TABLE IF NOT EXISTS card_fees(id INTEGER PRIMARY KEY,source_kind TEXT NOT NULL CHECK(source_kind IN('sale','ledger')),source_id INTEGER NOT NULL,gross_cents INTEGER NOT NULL CHECK(gross_cents>0),fee_cents INTEGER NOT NULL CHECK(fee_cents BETWEEN 0 AND gross_cents),base_cents INTEGER NOT NULL CHECK(base_cents>=0),vat_cents INTEGER NOT NULL CHECK(vat_cents>=0),configured INTEGER NOT NULL CHECK(configured IN(0,1)),tariff_json TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(source_kind,source_id),CHECK(fee_cents=base_cents+vat_cents))"]
def install(db):
 for statement in SCHEMA:db.execute(statement)
def read(db):
 row=db.execute('SELECT * FROM card_fee_settings WHERE id=1').fetchone()
 return dict(row) if row else dict(enabled=0,provider='Sin configurar',rate_bps=0,vat_bps=1600,fixed_cents=0)
def settings(pos,uid,data=None):
 with pos.db(data is not None) as db:
  if data is None:
   if not pos.permissions(db,uid).intersection({'sell','users.manage','customers.manage'}):raise Error('Sin permiso',403)
  else:
   pos.require(db,uid,'users.manage')
   if type(data.get('enabled')) is not bool:raise Error('Confirma si se aplicará esta tarifa')
   provider=str(data.get('provider','')).strip()[:100]
   if not provider:raise Error('Indica el nombre del proveedor')
   rate=integer(data.get('rate_bps'),'Comisión',0,10000);vat=integer(data.get('vat_bps'),'IVA sobre comisión',0,1600);fixed=integer(data.get('fixed_cents',0),'Cargo fijo',0,1000000)
   db.execute('INSERT INTO card_fee_settings VALUES(1,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled,provider=excluded.provider,rate_bps=excluded.rate_bps,vat_bps=excluded.vat_bps,fixed_cents=excluded.fixed_cents',(int(data['enabled']),provider,rate,vat,fixed))
   pos.audit(db,uid,'cardfee.settings',None,{**data})
  return read(db)
def calculate(gross,cfg):
 if not cfg['enabled']:return {'base_cents':0,'vat_cents':0,'fee_cents':0,'net_cents':gross}
 numerator=gross*cfg['rate_bps']+cfg['fixed_cents']*10000
 total=rounded(numerator*(10000+cfg['vat_bps']),100000000);base=rounded(numerator,10000)
 if total>gross:raise Error('La comisión configurada supera el cobro. Revisa la tarifa antes de vender')
 return dict(base_cents=base,vat_cents=total-base,fee_cents=total,net_cents=gross-total)
def record(db,kind,source_id,gross):
 if gross<=0:return
 cfg=read(db);calc=calculate(gross,cfg);table='sales' if kind=='sale' else 'customer_ledger';created=db.execute('SELECT created_at FROM '+table+' WHERE id=?',(source_id,)).fetchone()[0]
 db.execute('INSERT INTO card_fees(source_kind,source_id,gross_cents,fee_cents,base_cents,vat_cents,configured,tariff_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(kind,source_id,gross,calc['fee_cents'],calc['base_cents'],calc['vat_cents'],int(cfg['enabled']),json.dumps(cfg),created))
def add_history(db,result):
 rows=[dict(r) for r in db.execute("SELECT *,datetime(created_at,'localtime') happened_at,date(created_at,'localtime') day FROM card_fees WHERE date(created_at,'localtime') BETWEEN ? AND ? ORDER BY created_at DESC,id DESC",(result['from'],result['to']))]
 for row in rows:row['tariff']=json.loads(row.pop('tariff_json'));row['net_cents']=row['gross_cents']-row['fee_cents']
 byday={d['day']:d for d in result['daily']}
 for d in byday.values():d.update(card_fee_cents=0,card_fee_unconfigured_cents=0,after_fees_cents=d['net_cents'])
 for row in rows:
  d=byday[row['day']];d['card_fee_cents']+=row['fee_cents'];d['card_fee_unconfigured_cents']+=row['gross_cents'] if not row['configured'] else 0
 # Las ventas anteriores a esta actualización no tienen comisión histórica:
 # se avisa, sin inventar una tarifa retroactiva.
 for row in db.execute("""SELECT date(s.created_at,'localtime') day,SUM(p.amount_cents) amount FROM sale_payments p JOIN sales s ON s.id=p.sale_id WHERE p.method IN('debit','credit') AND date(s.created_at,'localtime') BETWEEN ? AND ? AND NOT EXISTS(SELECT 1 FROM card_fees f WHERE f.source_kind='sale' AND f.source_id=s.id) GROUP BY 1
 UNION ALL SELECT date(l.created_at,'localtime'),-SUM(l.amount_cents) FROM customer_ledger l WHERE l.method='debit' AND l.amount_cents<0 AND date(l.created_at,'localtime') BETWEEN ? AND ? AND NOT EXISTS(SELECT 1 FROM card_fees f WHERE f.source_kind='ledger' AND f.source_id=l.id) GROUP BY 1""",(result['from'],result['to'],result['from'],result['to'])):
  byday[row['day']]['card_fee_unconfigured_cents']+=row['amount']
 for d in byday.values():
  d['after_fees_cents']=d['net_cents']-d['card_fee_cents']
  if 'profit_cents' in d:d['profit_after_fees_cents']=d['profit_cents']-d['card_fee_cents']
 t=result['totals'];t['card_fee_cents']=sum(d['card_fee_cents'] for d in byday.values());t['card_fee_unconfigured_cents']=sum(d['card_fee_unconfigured_cents'] for d in byday.values());t['after_fees_cents']=t['net_cents']-t['card_fee_cents']
 if 'profit_cents' in t:t['profit_after_fees_cents']=t['profit_cents']-t['card_fee_cents']
 result['card_fees']=rows
