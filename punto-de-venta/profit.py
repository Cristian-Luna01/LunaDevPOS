"""Margen sobre costos históricos de lotes; no es utilidad neta del negocio."""
def entries(db,start=None,end=None,shift_id=None,collection_entries=None):
    sale_filter='s.shift_id=?' if shift_id is not None else 's.created_at>=? AND s.created_at<?'
    return_filter='r.shift_id=?' if shift_id is not None else 'r.created_at>=? AND r.created_at<?'
    from time_ranges import utc_bounds
    args=(shift_id,) if shift_id is not None else utc_bounds(db,start,end)
    rows=db.execute(f'''SELECT i.id item_id,NULL return_id,i.total_cents amount,i.tax_cents tax_cents,
        COALESCE((SELECT SUM(a.quantity*a.unit_cost_cents) FROM sale_item_batches a WHERE a.sale_item_id=i.id),0) cost_cents,
        COALESCE((SELECT SUM(a.quantity) FROM sale_item_batches a WHERE a.sale_item_id=i.id AND a.unit_cost_cents=0),0) zero_cost_units
        FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE {sale_filter} AND NOT EXISTS(SELECT 1 FROM customer_ledger l WHERE l.sale_id=s.id)
        UNION ALL
        SELECT ri.sale_item_id,r.id,-ri.total_cents,-ri.tax_cents,
        CASE WHEN ri.disposition='restock' THEN -COALESCE((SELECT SUM(a.quantity*b.unit_cost_cents) FROM return_allocations a JOIN sale_item_batches b ON b.id=a.sale_item_batch_id WHERE a.return_item_id=ri.id),0) ELSE 0 END,
        COALESCE((SELECT SUM(a.quantity) FROM return_allocations a JOIN sale_item_batches b ON b.id=a.sale_item_batch_id WHERE a.return_item_id=ri.id AND b.unit_cost_cents=0),0)
        FROM return_items ri JOIN returns r ON r.id=ri.return_id WHERE {return_filter}''',(*args,*args))
    result=[]
    for row in rows:
        d=dict(row);d['profit_cents']=d['amount']-d['cost_cents'];result.append(d)
    from cash_basis import collections
    result.extend(collections(db,start,end,shift_id) if collection_entries is None else collection_entries)
    return result

def shift(db,sid):
    rows=entries(db,shift_id=sid)
    return {k:sum(r[k] for r in rows) for k in ('tax_cents','cost_cents','profit_cents','zero_cost_units')}

def add_history(db,result,collection_entries=None):
    details={(r['item_id'],r['return_id'],r.get('collection_id')):r for r in entries(db,result['from'],result['to'],collection_entries=collection_entries)}
    days={d['day']:d for d in result['daily']};products={p['id']:p for p in result['products']}
    keys=('tax_cents','cost_cents','profit_cents','zero_cost_units')
    for row in [result['totals'],*days.values(),*products.values()]:row.update({k:0 for k in keys})
    for e in result['events']:
        values=details.get((e['item_id'],e['return_id'],e.get('collection_id')),{k:0 for k in keys})
        for k in keys:
            e[k]=values[k]
            for target in (result['totals'],days[e['day']],products[e['product_id']]):target[k]+=values[k]
    return result
