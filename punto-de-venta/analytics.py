"""Historial por fecha local y métricas derivadas de movimientos confirmados."""
import csv
import datetime as dt
import io
from core import Error


def dates(data):
    try:
        start=dt.date.fromisoformat(data.get('from',dt.date.today().isoformat()))
        end=dt.date.fromisoformat(data.get('to',start.isoformat()))
    except (ValueError,TypeError):
        raise Error('Selecciona fechas válidas')
    if start<dt.date(2000,1,1) or end<start or (end-start).days>365 or end>dt.date.today():
        raise Error('Selecciona hasta 366 días desde el año 2000, sin fechas futuras')
    return start,end


def history(db,data,include_profit=False):
    start,end=dates(data)
    args=(start.isoformat(),end.isoformat())
    # Una fila por partida, sin unir pagos ni lotes (evita multiplicar ventas).
    events=[dict(r) for r in db.execute('''SELECT date(s.created_at,'localtime') day,
        datetime(s.created_at,'localtime') happened_at,CASE WHEN EXISTS(SELECT 1 FROM customer_ledger l WHERE l.sale_id=s.id) THEN 'Crédito' ELSE 'Venta' END kind,s.id ticket_id,
        NULL return_id,i.id item_id,i.product_id,i.product_name name,p.barcode,
        i.quantity units,CASE WHEN EXISTS(SELECT 1 FROM customer_ledger l WHERE l.sale_id=s.id) THEN 0 ELSE i.total_cents END cents,s.status,
        CASE WHEN EXISTS(SELECT 1 FROM customer_ledger l WHERE l.sale_id=s.id) THEN i.total_cents ELSE 0 END credit_cents,NULL collection_id
        FROM sale_items i JOIN sales s ON s.id=i.sale_id JOIN products p ON p.id=i.product_id
        WHERE date(s.created_at,'localtime') BETWEEN ? AND ?
        UNION ALL
        SELECT date(r.created_at,'localtime'),datetime(r.created_at,'localtime'),
        CASE WHEN r.kind='void' THEN 'Anulación' ELSE 'Devolución' END,r.sale_id,r.id,i.id,
        i.product_id,i.product_name,p.barcode,-ri.quantity,-ri.total_cents,s.status,0,NULL
        FROM return_items ri JOIN returns r ON r.id=ri.return_id JOIN sale_items i ON i.id=ri.sale_item_id
        JOIN sales s ON s.id=r.sale_id JOIN products p ON p.id=i.product_id
        WHERE date(r.created_at,'localtime') BETWEEN ? AND ?
        ORDER BY happened_at,ticket_id,item_id''',(*args,*args))]
    from cash_basis import collections
    events.extend(collections(db,*args))
    events.sort(key=lambda e:(e['happened_at'],e['ticket_id'],e['item_id'],e['collection_id'] or 0))
    daily={}
    for n in range((end-start).days+1):
        day=(start+dt.timedelta(days=n)).isoformat()
        daily[day]={'day':day,'sales_cents':0,'refunds_cents':0,'net_cents':0,'sold_units':0,'returned_units':0,'tickets':0,'credit_cents':0}
    products={};tickets=set()
    for e in events:
        d=daily[e['day']]
        p=products.setdefault(e['product_id'],{'id':e['product_id'],'name':e['name'],'barcode':e['barcode'],'sold_units':0,'returned_units':0,'sales_cents':0,'refunds_cents':0,'net_cents':0,'credit_cents':0})
        is_sale=e['kind'] in ('Venta','Crédito','Abono')
        for row in (d,p):
            row['sales_cents' if is_sale else 'refunds_cents']+=abs(e['cents'])
            row['sold_units' if is_sale else 'returned_units']+=abs(e['units'])
            row['net_cents']+=e['cents']
            row['credit_cents']+=e['credit_cents']
        if e['kind'] in ('Venta','Crédito') and e['ticket_id'] not in tickets:
            tickets.add(e['ticket_id']);d['tickets']+=1
    # Cobros netos por medio: fechas de venta, abono y devolución respectivas.
    for row in daily.values():row['payments_by_method']={'cash':0,'card':0,'transfer':0}
    payment_rows=db.execute("""SELECT date(s.created_at,'localtime') day,p.method,p.amount_cents amount
        FROM sale_payments p JOIN sales s ON s.id=p.sale_id
        WHERE date(s.created_at,'localtime') BETWEEN ? AND ? AND NOT EXISTS(SELECT 1 FROM customer_ledger l WHERE l.sale_id=s.id)
        UNION ALL SELECT date(created_at,'localtime'),method,-amount_cents FROM customer_ledger
        WHERE amount_cents<0 AND date(created_at,'localtime') BETWEEN ? AND ?
        UNION ALL SELECT date(r.created_at,'localtime'),p.method,-p.amount_cents
        FROM return_payments p JOIN returns r ON r.id=p.return_id
        WHERE date(r.created_at,'localtime') BETWEEN ? AND ?""",(*args,*args,*args))
    for row in payment_rows:
        method='card' if row['method'] in ('debit','credit') else row['method']
        daily[row['day']]['payments_by_method'][method]+=row['amount']
    days=list(daily.values())
    totals={key:sum(d[key] for d in days) for key in ('sales_cents','refunds_cents','net_cents','sold_units','returned_units','tickets','credit_cents')}
    totals['payments_by_method']={method:sum(d['payments_by_method'][method] for d in days) for method in ('cash','card','transfer')}
    cash_movements=[dict(r) for r in db.execute('''SELECT m.id,m.shift_id,m.direction,m.category,m.amount_cents,m.concept,m.invoice_ref,
        datetime(m.created_at,'localtime') happened_at,u.display_name user_name,s.business_name supplier_name
        FROM cash_movements m JOIN users u ON u.id=m.user_id LEFT JOIN suppliers s ON s.id=m.supplier_id
        WHERE date(m.created_at,'localtime') BETWEEN ? AND ? ORDER BY m.created_at DESC,m.id DESC''',args)]
    cash_totals={direction:sum(m['amount_cents'] for m in cash_movements if m['direction']==direction) for direction in ('in','out')}
    result={'from':args[0],'to':args[1],'daily':days,'products':sorted(products.values(),key=lambda p:(-p['sold_units'],p['name'])),'events':events,'totals':totals,'cash_movements':cash_movements,'cash_totals':cash_totals}
    if include_profit:
        from profit import add_history
        add_history(db,result)
    from card_fees import add_history as add_fees
    add_fees(db,result)
    return result


def metrics(db,data,include_profit=False):
    result=history(db,data,include_profit)
    start,end=dates(data);count=(end-start).days+1
    previous_end=start-dt.timedelta(days=1);previous_start=previous_end-dt.timedelta(days=count-1)
    previous=history(db,{'from':max(dt.date(2000,1,1),previous_start).isoformat(),'to':previous_end.isoformat()}) if previous_end>=dt.date(2000,1,1) else {'totals':dict(sales_cents=0,refunds_cents=0,net_cents=0,sold_units=0,returned_units=0,tickets=0)}
    activity={p['id']:p for p in result['products']}
    for p in db.execute('SELECT id,name,barcode FROM products WHERE active=1'):
        activity.setdefault(p['id'],dict(p,sold_units=0,returned_units=0,sales_cents=0,refunds_cents=0,net_cents=0))
    available={r['product_id']:r['stock'] for r in db.execute('SELECT product_id,SUM(quantity) stock FROM batches WHERE expires_on IS NULL OR expires_on>? GROUP BY product_id',(dt.date.today().isoformat(),))}
    for p in activity.values():
        p['net_units']=p['sold_units']-p['returned_units']
        p['stock']=available.get(p['id'],0)
        p['daily_units']=round(max(0,p['net_units'])/count,4)
        p['coverage_days']=round(p['stock']*count/p['net_units'],1) if p['net_units']>0 else None
    result['products']=sorted(activity.values(),key=lambda p:(-p['net_units'],p['name']))
    result['previous']={'from':previous_start.isoformat(),'to':previous_end.isoformat(),'totals':previous['totals']}
    result['days']=count
    weekdays=[{'name':name,'days':0,'net_cents':0,'units':0} for name in ('Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo')]
    for day in result['daily']:
        group=weekdays[dt.date.fromisoformat(day['day']).weekday()]
        group['days']+=1;group['net_cents']+=day['net_cents'];group['units']+=day['sold_units']-day['returned_units']
    result['weekdays']=weekdays
    # El detalle de tickets vive en Historial, no se duplica en cada actualización de métricas.
    del result['events']
    return result


def export_history(result,summary=False):
    stream=io.StringIO(newline='');writer=csv.writer(stream)
    show_profit='profit_cents' in result['totals']
    extra_headers=['IVA venta neto MXN','Costo correspondiente a lo cobrado MXN','Ganancia real MXN'] if show_profit else []
    def extra(row):return [f"{row[k]/100:.2f}" for k in ('tax_cents','cost_cents','profit_cents')] if show_profit else []
    if summary:
        writer.writerow(['Fecha local','Cobros antes de devoluciones MXN','Devoluciones MXN','Ventas totales MXN','Unidades entregadas','Unidades devueltas','Tickets']+extra_headers+['Cobrado en efectivo MXN','Cobrado con tarjeta MXN','Cobrado por transferencia MXN'])
        for d in result['daily']:
            writer.writerow([d['day'],*[f"{d[k]/100:.2f}" for k in ('sales_cents','refunds_cents','net_cents')],d['sold_units'],d['returned_units'],d['tickets']]+extra(d)+[f"{d['payments_by_method'][method]/100:.2f}" for method in ('cash','card','transfer')])
        return stream.getvalue().encode('utf-8-sig')
    writer.writerow(['Fecha local','Hora local','Movimiento','Ticket original','Devolución','Partida','Código','Producto','Unidades (+venta/-devolución)','Importe MXN (+venta/-devolución)','Estado actual del ticket']+extra_headers)
    def safe(value):
        value=str(value)
        return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')) else value
    for e in result['events']:
        writer.writerow([e['day'],e['happened_at'],e['kind'],e['ticket_id'],e['return_id'] or '',e['item_id'],safe(e['barcode']),safe(e['name']),e['units'],f"{e['cents']/100:.2f}",e['status']]+extra(e))
    return stream.getvalue().encode('utf-8-sig')
