import datetime as dt
from core import Error,integer,required

TABLE='''CREATE TABLE IF NOT EXISTS promotions(
 id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL UNIQUE REFERENCES products(id),
 name TEXT NOT NULL,price_cents INTEGER NOT NULL CHECK(price_cents>=0),
 starts_on TEXT NOT NULL,ends_on TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)),
 CHECK(length(starts_on)=10 AND length(ends_on)=10 AND starts_on<=ends_on))'''

EXTRA_COLUMNS={
 'schedule_type':"TEXT NOT NULL DEFAULT 'temporary' CHECK(schedule_type IN ('temporary','permanent','recurring'))",
 'weekday_mask':'INTEGER NOT NULL DEFAULT 127 CHECK(weekday_mask BETWEEN 1 AND 127)',
 'bundle_quantity':'INTEGER NOT NULL DEFAULT 1 CHECK(bundle_quantity BETWEEN 1 AND 10000)'}

def is_current(p,today=None):
    today=today or dt.date.today()
    return bool(p['active'] and (p['schedule_type']=='permanent' or
        (p['starts_on']<=today.isoformat()<=p['ends_on'] and
         (p['schedule_type']!='recurring' or p['weekday_mask'] & (1<<today.weekday())))))

def active(db,today=None):
    return {r['product_id']:dict(r) for r in db.execute('SELECT * FROM promotions WHERE active=1') if is_current(r,today)}

def total(p,unit_price,quantity):
    groups,remainder=divmod(quantity,p['bundle_quantity'])
    return min(unit_price*quantity,groups*p['price_cents']+remainder*unit_price)

def decorate(product,p):
    product['promotion']=dict(price_cents=p['price_cents'],bundle_quantity=p['bundle_quantity']) if p else None
    product['promo_price_cents']=min(product['price_cents'],p['price_cents']) if p and p['bundle_quantity']==1 else None

def save(pos,uid,data):
    with pos.db(True) as db:
        pos.require(db,uid,'products.edit')
        pid=integer(data.get('product_id'),'Producto',1)
        product=db.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
        if not product:
            raise Error('Producto no disponible')
        if data.get('disable') is True:
            db.execute('UPDATE promotions SET active=0 WHERE product_id=?',(pid,))
            pos.audit(db,uid,'promotion.disable',pid,{})
            return {'ok':True}
        qty=integer(data.get('bundle_quantity',1),'Unidades del paquete',1,10000)
        price=integer(data.get('price_cents'),'Precio promocional',1,product['price_cents']*qty)
        schedule=data.get('schedule_type','temporary')
        if schedule not in ('temporary','permanent','recurring'):
            raise Error('Tipo de promoción inválido')
        mask=integer(data.get('weekday_mask',127),'Días de la semana',1,127)
        start_value=data.get('starts_on');end_value=data.get('ends_on')
        if schedule=='permanent':start_value,end_value='0001-01-01','9999-12-31'
        if schedule=='recurring':start_value,end_value=start_value or '0001-01-01',end_value or '9999-12-31'
        try:
            start=dt.date.fromisoformat(start_value);end=dt.date.fromisoformat(end_value)
        except (ValueError,TypeError):raise Error('Fechas de promoción inválidas')
        if end<start:
            raise Error('La fecha final debe ser igual o posterior al inicio')
        name=required(data,'name')
        db.execute('''INSERT INTO promotions(product_id,name,price_cents,starts_on,ends_on,active,schedule_type,weekday_mask,bundle_quantity) VALUES (?,?,?,?,?,1,?,?,?)
            ON CONFLICT(product_id) DO UPDATE SET name=excluded.name,price_cents=excluded.price_cents,starts_on=excluded.starts_on,ends_on=excluded.ends_on,active=1,schedule_type=excluded.schedule_type,weekday_mask=excluded.weekday_mask,bundle_quantity=excluded.bundle_quantity''',(pid,name,price,start.isoformat(),end.isoformat(),schedule,mask,qty))
        pos.audit(db,uid,'promotion.save',pid,dict(name=name,price_cents=price,starts_on=start.isoformat(),ends_on=end.isoformat(),schedule_type=schedule,weekday_mask=mask,bundle_quantity=qty))
        return {'ok':True}
