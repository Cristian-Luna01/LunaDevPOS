"""Datos de consulta de Dirección; comparte el mismo criterio del panel local."""
import datetime as dt
import json
import analytics
import profit

def current(pos,db):
    today=dt.date.today().isoformat()
    products=[dict(r) for r in db.execute('''SELECT p.id,p.barcode,p.name,p.reorder_point,p.max_stock,p.price_cents,p.cost_cents,
        COALESCE(SUM(CASE WHEN b.expires_on IS NULL OR b.expires_on>? THEN b.quantity ELSE 0 END),0) stock,
        COALESCE(SUM(b.quantity),0) physical_stock,
        (SELECT unit_cost_cents FROM batches WHERE product_id=p.id ORDER BY received_at DESC,id DESC LIMIT 1) purchase_cost_cents
        FROM products p LEFT JOIN batches b ON b.product_id=p.id WHERE p.active=1 GROUP BY p.id ORDER BY p.name''',(today,))]
    import inventory_value
    values=inventory_value.by_product(db,today)
    for product in products:product["inventory_value_cents"]=values[product["id"]]
    shifts=[]
    for s in db.execute("SELECT s.*,u.display_name FROM cash_shifts s JOIN users u ON u.id=s.user_id WHERE s.closed_at IS NULL OR date(s.closed_at,'localtime')=? ORDER BY s.id DESC",(today,)):
        r=pos.report(db,s['id'])
        shifts.append({'id':s['id'],'user':r.get('user_name',s['display_name']),'closed_at':s['closed_at'],'sales_cents':r['net_sales_cents'],
            'expected_cents':r['expected_cents'],'counted_cents':s['counted_cents'],'difference_cents':r.get('difference_cents'),
            'payments_by_method':{name:sum(r['sales_by_method'].get(m,0)+r['collections_by_method'].get(m,0)-r['refunds_by_method'].get(m,0) for m in methods) for name,methods in [('cash',('cash',)),('card',('debit','credit')),('transfer',('transfer',))]},**profit.shift(db,s['id'])})
    totals=analytics.history(db,{'from':today,'to':today},True)['totals']
    suppliers=[dict(r) for r in db.execute('SELECT id,business_name,contact,phone,credit_days FROM suppliers WHERE active=1 ORDER BY business_name')]
    settings=db.execute('SELECT name,receipt_footer FROM business_settings WHERE id=1').fetchone()
    settings=dict(settings or {'name':'Punto de venta','receipt_footer':'Gracias por tu compra.'})
    logo=db.execute('SELECT png_base64 FROM business_branding WHERE id=1').fetchone()
    settings['has_logo']=bool(logo)
    if logo:
        encoded=logo[0]
        if len(encoded)>400000:
            import base64
            from PySide6.QtCore import QByteArray,QBuffer,QIODevice,Qt
            from PySide6.QtGui import QImage
            image=QImage.fromData(base64.b64decode(encoded))
            image=image.scaled(256,256,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            output=QByteArray();buffer=QBuffer(output);buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG')
            encoded=base64.b64encode(bytes(output)).decode()
        settings['logo_base64']=encoded
    days=[r[0] for r in db.execute("""SELECT date(created_at,'localtime') FROM sales UNION SELECT date(created_at,'localtime') FROM returns
        UNION SELECT date(created_at,'localtime') FROM customer_ledger UNION SELECT date(created_at,'localtime') FROM cash_movements UNION SELECT date(created_at,'localtime') FROM audit_log WHERE action IN ('inventory.product_count','product.price_change') ORDER BY 1""")]
    if today not in days:days.append(today)
    return {**totals,'day':today,'products':products,'shifts':shifts,'suppliers':suppliers,'settings':settings,'inventory_adjustments_supported':True,'history_days':sorted(days),
            'history_fingerprints':history_fingerprints(db,days),
            'metric_stock':{str(r[0]):r[1] for r in db.execute('SELECT product_id,SUM(quantity) FROM batches WHERE expires_on IS NULL OR expires_on>? GROUP BY product_id',(today,))}}

def day_fingerprint(db,day):
    import hashlib
    values=[]
    for table in ('sales','returns','customer_ledger','cash_movements','card_fees','audit_log'):
        condition=" AND action IN ('inventory.product_count','product.price_change')" if table=='audit_log' else ''
        rows=[dict(r) for r in db.execute(f"SELECT * FROM {table} WHERE date(created_at,'localtime')=?{condition} ORDER BY id",(day,))]
        values.append(rows)
    # Los nombres de operadores/proveedores se presentan con sus datos actuales.
    values.append(reference_fingerprint(db))
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()

def history_fingerprints(db,days):
    """Mismas huellas, sin retener todas las filas del histórico en memoria."""
    import hashlib
    references=reference_fingerprint(db)
    hashes={day:hashlib.sha256(b'[') for day in days}
    for table in ('sales','returns','customer_ledger','cash_movements','card_fees','audit_log'):
        for digest in hashes.values():digest.update(b'[')
        populated=set()
        condition=" WHERE action IN ('inventory.product_count','product.price_change')" if table=='audit_log' else ''
        for row in db.execute(f"SELECT *,date(created_at,'localtime') AS fingerprint_day FROM {table}{condition} ORDER BY id"):
            data=dict(row);day=data.pop('fingerprint_day')
            digest=hashes.get(day)
            if digest is None:continue
            if day in populated:digest.update(b', ')
            populated.add(day)
            digest.update(json.dumps(data,sort_keys=True).encode())
        for digest in hashes.values():digest.update(b'], ')
    for digest in hashes.values():digest.update(json.dumps(references).encode()+b']')
    return {day:digest.hexdigest() for day,digest in hashes.items()}


def reference_fingerprint(db):
    import hashlib
    values=[[tuple(r) for r in db.execute(query)] for query in (
        'SELECT id,display_name FROM users ORDER BY id','SELECT id,business_name FROM suppliers ORDER BY id',
        'SELECT id,barcode FROM products ORDER BY id')]
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


def product_adjustments(db,day):
    result=[]
    for row in db.execute("""SELECT a.id,a.action,a.entity_id,a.details,datetime(a.created_at,'localtime') happened_at,
        p.name,p.barcode,u.display_name FROM audit_log a JOIN products p ON p.id=a.entity_id
        LEFT JOIN users u ON u.id=a.user_id WHERE a.action IN ('inventory.product_count','product.price_change')
        AND date(a.created_at,'localtime')=? ORDER BY a.id DESC""",(day,)):
        details=json.loads(row['details'])
        common={'id':row['id'],'product_id':row['entity_id'],'name':details.get('name',row['name']),'barcode':details.get('barcode',row['barcode']),
                'user_name':row['display_name'] or 'Usuario no disponible','happened_at':row['happened_at'],'reason':details['reason']}
        if row['action']=='product.price_change':
            result.append({**common,'kind':'price_change','changes':details['changes']})
        else:
            result.append({**common,'kind':'stock_adjustment','before':details['before'],'after':details['after'],'difference':details['after']-details['before']})
    return result
