"""Busca primero los productos visibles; suma únicamente sus lotes."""
import datetime as dt

def search(db,q,offset,include_costs=False,today=None):
    columns='id,barcode,name,generic_name,category_id,price_cents,tax_bps,min_stock,max_stock,reorder_point,requires_prescription'
    if include_costs:columns+=',cost_cents'
    rows=[dict(r) for r in db.execute(f'''SELECT {columns} FROM products
        WHERE active=1 AND (barcode=? OR name LIKE ? OR generic_name LIKE ?)
        ORDER BY (barcode=?) DESC,name LIMIT 40 OFFSET ?''',(q,'%'+q+'%','%'+q+'%',q,offset))]
    stocks={}
    if rows:
        ids=[r['id'] for r in rows];marks=','.join('?' for _ in ids)
        stocks={r['product_id']:r for r in db.execute(f'''SELECT product_id,
            SUM(CASE WHEN expires_on IS NULL OR expires_on>? THEN quantity ELSE 0 END) stock,
            SUM(quantity) physical_stock FROM batches WHERE product_id IN ({marks}) GROUP BY product_id''',
            (today or dt.date.today().isoformat(),*ids))}
    for row in rows:
        stock=stocks.get(row['id'])
        row['stock']=stock['stock'] if stock else 0
        row['physical_stock']=stock['physical_stock'] if stock else 0
    return rows
