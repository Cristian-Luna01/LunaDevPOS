"""Reconocimiento de abonos: compras/partidas antiguas primero, sin duplicar unidades."""
from collections import defaultdict,deque

def collections(db,start=None,end=None,shift_id=None):
    items=defaultdict(list)
    for r in db.execute("""SELECT l.id charge_id,s.id ticket_id,s.status,i.id item_id,i.product_id,i.category_id,i.product_name name,p.barcode,i.quantity,i.total_cents,i.tax_cents,
      COALESCE((SELECT SUM(a.quantity*a.unit_cost_cents) FROM sale_item_batches a WHERE a.sale_item_id=i.id),0) cost_cents,
      COALESCE((SELECT SUM(a.quantity) FROM sale_item_batches a WHERE a.sale_item_id=i.id AND a.unit_cost_cents=0),0) zero_units
      FROM customer_ledger l JOIN sales s ON s.id=l.sale_id JOIN sale_items i ON i.sale_id=s.id JOIN products p ON p.id=i.product_id
      WHERE l.amount_cents>0 ORDER BY l.id,i.id"""):
        item=dict(r);item['paid']=0;items[r['charge_id']].append(item)
    queues=defaultdict(deque);result=[]
    for row in db.execute("SELECT *,date(created_at,'localtime') day,datetime(created_at,'localtime') happened_at FROM customer_ledger ORDER BY id"):
        queue=queues[row['customer_id']]
        if row['amount_cents']>0:
            queue.extend(items[row['id']]);continue
        remaining=-row['amount_cents']
        selected=(shift_id is None or row['shift_id']==shift_id) and (start is None or start<=row['day']<=end)
        last_charge=None
        while queue and (remaining or (queue[0]['total_cents']==0 and queue[0]['charge_id']==last_charge)):
            item=queue[0];total=item['total_cents'];before=item['paid'];take=min(remaining,total-before)
            if take<=0:
                if total==0 and selected:
                    result.append({'day':row['day'],'happened_at':row['happened_at'],'kind':'Abono','ticket_id':item['ticket_id'],'return_id':None,'collection_id':row['id'],'item_id':item['item_id'],'product_id':item['product_id'],'category_id':item['category_id'],'name':item['name'],'barcode':item['barcode'],'units':0,'cents':0,'credit_cents':0,'status':item['status'],'amount':0,'tax_cents':item['tax_cents'],'cost_cents':item['cost_cents'],'profit_cents':-item['cost_cents'],'zero_cost_units':item['zero_units']})
                queue.popleft();continue
            last_charge=item['charge_id']
            after=before+take
            def share(value):return (value*after+total//2)//total-(value*before+total//2)//total
            cost=share(item['cost_cents']);tax=share(item['tax_cents'])
            if selected:
                result.append({'day':row['day'],'happened_at':row['happened_at'],'kind':'Abono','ticket_id':item['ticket_id'],'return_id':None,'collection_id':row['id'],'item_id':item['item_id'],'product_id':item['product_id'],'category_id':item['category_id'],'name':item['name'],'barcode':item['barcode'],'units':0,'cents':take,'credit_cents':0,'status':item['status'],'amount':take,'tax_cents':tax,'cost_cents':cost,'profit_cents':take-cost,'zero_cost_units':share(item['zero_units'])})
            item['paid']=after;remaining-=take
            if after==total:queue.popleft()
        if remaining:raise ValueError('Abono sin compras a crédito suficientes para conciliar')
    return result
