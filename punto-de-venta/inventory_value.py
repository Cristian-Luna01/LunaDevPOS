"""Valor de existencias vendibles a costo histórico de cada lote, en centavos."""
def by_product(db, today):
    return {r[0]:r[1] for r in db.execute("""SELECT p.id,COALESCE(SUM(CASE
        WHEN b.expires_on IS NULL OR b.expires_on>? THEN b.quantity*b.unit_cost_cents ELSE 0 END),0)
        FROM products p LEFT JOIN batches b ON b.product_id=p.id
        WHERE p.active=1 GROUP BY p.id""",(today,))}
