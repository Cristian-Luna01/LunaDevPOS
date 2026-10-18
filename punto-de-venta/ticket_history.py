"""Consulta paginada de ventas originales, independiente de los cobros por fecha."""
import datetime as dt
from core import Error, integer


def period(data):
    try:
        start = dt.date.fromisoformat(data.get('from', dt.date.today().isoformat()))
        end = dt.date.fromisoformat(data.get('to', start.isoformat()))
    except (ValueError, TypeError):
        raise Error('Selecciona fechas válidas')
    if start < dt.date(2000,1,1) or end < start or end > dt.date.today() or (end-start).days > 365:
        raise Error('Selecciona un periodo de hasta 366 días, en orden')
    return start.isoformat(), end.isoformat()


def listing(db, uid, permissions, data):
    start, end = period(data)
    all_users = bool(permissions.intersection({'reports.view', 'sales.return', 'sales.void'}))
    where = ["date(s.created_at,'localtime') BETWEEN ? AND ?"]
    args = [start, end]
    if not all_users:
        where.append('s.user_id=?')
        args.append(uid)
    if data.get('before'):
        try:
            before = integer(int(data['before']), 'Ticket anterior', 1)
        except (ValueError, TypeError):
            raise Error('Ticket anterior inválido')
        anchor = db.execute('SELECT created_at,user_id FROM sales WHERE id=?', (before,)).fetchone()
        if not anchor or (not all_users and anchor['user_id'] != uid):
            raise Error('Ticket anterior inválido')
        where.append('(s.created_at,s.id)<(?,?)')
        args.extend((anchor['created_at'], before))
    rows = [dict(r) for r in db.execute('''SELECT s.id,s.created_at,s.total_cents,s.status,
        u.display_name seller_name,c.name customer_name,
        EXISTS(SELECT 1 FROM customer_ledger l WHERE l.sale_id=s.id) on_account,
        (SELECT COUNT(*) FROM sale_items i WHERE i.sale_id=s.id) line_count
        FROM sales s JOIN users u ON u.id=s.user_id LEFT JOIN customers c ON c.id=s.customer_id
        WHERE '''+' AND '.join(where)+' ORDER BY s.created_at DESC,s.id DESC LIMIT 51', args)]
    return {'from': start, 'to': end, 'items': rows[:50],
            'next_before': rows[49]['id'] if len(rows) > 50 else None,
            'scope': 'all' if all_users else 'own'}


def describe(db, ticket):
    names = db.execute('''SELECT u.display_name seller_name,c.name customer_name
        FROM sales s JOIN users u ON u.id=s.user_id LEFT JOIN customers c ON c.id=s.customer_id
        WHERE s.id=?''', (ticket['id'],)).fetchone()
    return {**ticket, **dict(names)}
