"""Reglas del dominio. Importes enteros; una transacción por operación."""
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
import threading

ROOT = Path(__file__).resolve().parent
PERMISSIONS = {
 'sell': 'Realizar ventas y abrir/cerrar mi turno',
 'products.create': 'Crear productos', 'products.edit': 'Editar productos',
 'products.delete': 'Dar de baja productos', 'inventory.adjust': 'Ajustar inventario',
 'inventory.receive': 'Recibir mercancía', 'cash.out': 'Registrar salidas de caja',
 'cash.in': 'Registrar entradas de caja', 'sales.return': 'Procesar devoluciones',
 'sales.void': 'Anular tickets', 'costs.view': 'Ver costos y márgenes',
 'reports.view': 'Ver corte X y reportes financieros', 'users.manage': 'Administrar usuarios',
 'customers.manage': 'Administrar clientes', 'suppliers.manage': 'Administrar proveedores',
 'inventory.import': 'Importar catálogo y existencias', 'inventory.export': 'Exportar inventario con costos',
 'backup.manage': 'Respaldar y restaurar todos los datos',
 'billing.issue':'Crear y emitir facturas de prueba', 'billing.manage':'Configurar facturación y gestionar cancelaciones'}

ACCOUNT_ROLES = {'seller': 'Vendedor', 'supervisor': 'Supervisor', 'administrator': 'Administrador'}
ADMIN_PERMISSIONS = {'users.manage', 'backup.manage'}
SELLER_PERMISSIONS = {'sell', 'customers.manage'}

class Error(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

def integer(v, name, minimum=0, maximum=10**12):
    if type(v) is not int or not minimum <= v <= maximum:
        raise Error(f'{name}: se requiere entero entre {minimum} y {maximum}')
    return v

def required(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise Error(f'{key}: texto obligatorio (máximo 500 caracteres)')
    return value.strip()

def rounded(n, d):
    return (n + d // 2) // d

def credential(data):
    value=data.get('secret')
    if not isinstance(value,str) or not value or len(value)>500:
        raise Error('Contraseña inválida: utiliza entre 1 y 500 caracteres')
    return value

def password_hash(secret):
    credential({'secret':secret})
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', secret.encode(), salt.encode(), 310000).hex()
    return f'{salt}${digest}'

def password_matches(secret, encoded):
    salt, expected = encoded.split('$')
    digest = hashlib.pbkdf2_hmac('sha256', secret.encode(), salt.encode(), 310000).hex()
    return hmac.compare_digest(digest, expected)

def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def session_hash(token, audience='pos'):
    return hashlib.sha256((audience+'\0'+token).encode()).hexdigest()

class POS:
    def __init__(self, path=None):
        self.request_lock = threading.RLock()
        self.file_upload_slot = threading.BoundedSemaphore(1)
        self.path = str(path or ROOT / 'data' / 'pos.sqlite3')
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        if Path(self.path).exists():
            from migrations import upgrade
            upgrade(self.path, PERMISSIONS)
            from performance_indexes import install
            install(self.path)

    @contextlib.contextmanager
    def db(self, write=False):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA synchronous=FULL')
        try:
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self, username, secret):
        if len(secret) < 8:
            raise Error('La contraseña inicial debe tener al menos 8 caracteres')
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            db.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
            from billing_schema import install
            install(db)
        with self.db(True) as db:
            if db.execute('SELECT 1 FROM users').fetchone():
                raise Error('La base ya está inicializada')
            db.executemany('INSERT INTO permissions VALUES (?,?)', PERMISSIONS.items())
            db.execute("INSERT INTO roles(name) VALUES ('Administrador')")
            db.executemany('INSERT INTO role_permissions VALUES (1,?)', [(p,) for p in PERMISSIONS])
            uid = db.execute('INSERT INTO users(username,display_name,password_hash) VALUES (?,?,?)',
                             (username, 'Administrador', password_hash(secret))).lastrowid
            db.execute('INSERT INTO user_roles VALUES (?,1)', (uid,))
            db.executemany('INSERT INTO categories(name) VALUES (?)', [(s,) for s in
                ['Medicamentos', 'Cuidado Personal', 'Perfumería', 'Material de Curación']])

    def permissions(self, db, uid):
        result = {r[0] for r in db.execute('SELECT permission_code FROM role_permissions rp JOIN user_roles ur ON ur.role_id=rp.role_id WHERE ur.user_id=?', (uid,))}
        for row in db.execute('SELECT * FROM user_permissions WHERE user_id=?', (uid,)):
            (result.add if row['allowed'] else result.discard)(row['permission_code'])
        return result

    def require(self, db, uid, permission):
        user = db.execute('SELECT active FROM users WHERE id=?', (uid,)).fetchone()
        if not user or not user[0] or permission not in self.permissions(db, uid):
            raise Error('No tienes permiso para esta operación', 403)

    def account_role(self, db, uid, permissions=None):
        if permissions is None:
            permissions = self.permissions(db, uid)
        names = {r[0] for r in db.execute(
            'SELECT name FROM roles JOIN user_roles ON role_id=roles.id WHERE user_id=?', (uid,))}
        # Older accounts only stored permissions. Preserve their existing authority.
        if ACCOUNT_ROLES['administrator'] in names or ADMIN_PERMISSIONS & permissions:
            return 'administrator'
        if ACCOUNT_ROLES['supervisor'] in names:
            return 'supervisor'
        return 'seller'

    def account_access(self, db, uid):
        user = db.execute('SELECT active FROM users WHERE id=?', (uid,)).fetchone()
        if user and user['active']:
            permissions = self.permissions(db, uid)
            role = self.account_role(db, uid, permissions)
            if role == 'administrator' and 'users.manage' in permissions:
                return role, set(PERMISSIONS)
            if role == 'supervisor':
                return role, SELLER_PERMISSIONS & permissions
        raise Error('No tienes permiso para administrar cuentas', 403)

    def can_edit_account(self, db, uid, target, role, allowed, permissions):
        target_role = self.account_role(db, target, permissions)
        return target != uid and target_role != 'administrator' and (
            role == 'administrator' or (target_role == 'seller' and permissions <= allowed))

    def audit(self, db, uid, action, entity, details):
        db.execute('INSERT INTO audit_log(user_id,action,entity_id,details) VALUES (?,?,?,?)',
                   (uid, action, entity, json.dumps(details, ensure_ascii=False)))

    def login(self, username, secret, audience='pos'):
        if not isinstance(username,str) or '\0' in username or not 1<=len(username.strip())<=50:raise Error('Usuario inválido')
        credential({'secret':secret})
        username = username.strip().lower()
        attempt_key = username if audience=='pos' else 'direction\0'+username
        now = int(time.time())
        denied = False
        with self.db(True) as db:
            attempt = db.execute('SELECT * FROM login_attempts WHERE username=?', (attempt_key,)).fetchone()
            if attempt and attempt['blocked_until'] > now:
                raise Error('Demasiados intentos; espera 5 minutos', 429)
            user = db.execute('SELECT * FROM users WHERE username=? AND active=1', (username,)).fetchone()
            eligible = user and (audience=='pos' or {'users.manage','reports.view'} <= self.permissions(db,user['id']))
            if not user or not password_matches(secret, user['password_hash']):
                if eligible:
                    failures = (attempt['failures'] if attempt and attempt['blocked_until'] == 0 else 0) + 1
                    db.execute('INSERT OR REPLACE INTO login_attempts VALUES (?,?,?)',
                               (attempt_key, failures, now + 300 if failures >= 5 else 0))
                denied = True
            elif not eligible:
                raise Error('Acceso exclusivo de dirección',403)
            else:
                db.execute('DELETE FROM login_attempts WHERE username=?', (attempt_key,))
                db.execute('DELETE FROM sessions WHERE expires_at<?', (now,))
                token = secrets.token_urlsafe(32)
                db.execute('INSERT INTO sessions VALUES (?,?,?)',
                           (session_hash(token,audience), user['id'], now + 12*3600))
                self.audit(db, user['id'], 'login', user['id'], {})
        if denied:
            raise Error('Credenciales incorrectas', 401)
        return token

    def session_user(self, token, audience='pos'):
        with self.db() as db:
            row = db.execute('SELECT u.id FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1',
                             (session_hash(token,audience), int(time.time()))).fetchone()
            if not row:
                raise Error('Inicia sesión', 401)
            return row[0]

    def revoke_session(self, token, audience='pos'):
        with self.db(True) as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?',(session_hash(token,audience),))

    def shift(self, db, uid, shift_id=None):
        row = db.execute('SELECT * FROM cash_shifts WHERE user_id=? AND closed_at IS NULL', (uid,)).fetchone()
        if not row or (shift_id is not None and row['id'] != shift_id):
            raise Error('Abre tu turno antes de continuar', 409)
        return row

    def open_shift(self, uid, data):
        if 'shift_number' in data:
            number = integer(data['shift_number'], 'Turno', 1, 2)
            data = dict(data, shift_number=number, register_id='CAJA-1')
        with self.db(True) as db:
            self.require(db, uid, 'sell')
            register = required(data, 'register_id')
            existing = db.execute('SELECT id FROM cash_shifts WHERE user_id=? AND closed_at IS NULL',(uid,)).fetchone()
            if existing:
                raise Error('Ya tienes un turno abierto. Actualiza la página para continuar con ese turno.',409)
            occupied = db.execute('SELECT s.id,s.opened_at,u.display_name FROM cash_shifts s JOIN users u ON u.id=s.user_id WHERE s.register_id=? AND s.closed_at IS NULL',(register,)).fetchone()
            if occupied:
                raise Error(f'La caja tiene un turno pendiente de {occupied["display_name"]} desde {occupied["opened_at"][:10]}. Entra con esa cuenta y ciérralo en Caja y corte, indicando el efectivo contado, antes de iniciar otro turno.',409)
            sid = db.execute('INSERT INTO cash_shifts(user_id,register_id,opening_cents) VALUES (?,?,?)',
                             (uid, required(data, 'register_id'), integer(data.get('opening_cents'), 'Fondo inicial'))).lastrowid
            self.audit(db, uid, 'shift.open', sid, data)
            return {'id': sid}

    def cash_movement(self, uid, data):
        with self.db(True) as db:
            direction = data.get('direction')
            if direction not in ('in', 'out'):
                raise Error('Dirección inválida')
            self.require(db, uid, 'cash.' + direction)
            from operation_requests import previous,save
            old=previous(db,uid,'cash',data)
            if old is not None:return old
            sid = self.shift(db, uid)['id']
            mid = db.execute('INSERT INTO cash_movements(shift_id,user_id,direction,category,amount_cents,supplier_id,invoice_ref,concept) VALUES (?,?,?,?,?,?,?,?)',
                (sid, uid, direction, required(data, 'category'), integer(data.get('amount_cents'), 'Importe', 1),
                 data.get('supplier_id'), data.get('invoice_ref'), required(data, 'concept'))).lastrowid
            self.audit(db, uid, 'cash.movement', mid, data)
            return save(db,uid,'cash',data,{'id':mid})

    def report(self, db, sid):
        shift = db.execute('SELECT * FROM cash_shifts WHERE id=?', (sid,)).fetchone()
        if not shift:
            raise Error('Turno inexistente', 404)
        if shift['closed_at'] and shift['report_json']:
            try:
                saved=json.loads(shift['report_json'])
                if not isinstance(saved,dict) or saved.get('shift_id')!=sid:raise ValueError()
                return saved
            except (ValueError,TypeError):raise Error('La copia guardada del corte no es válida. Revisa el respaldo original.',409)
        payments = {m: 0 for m in ('cash','debit','credit','transfer')}
        refunds = payments.copy()
        for r in db.execute('SELECT p.method,SUM(p.amount_cents) amount FROM sale_payments p JOIN sales s ON s.id=p.sale_id WHERE s.shift_id=? GROUP BY p.method', (sid,)):
            payments[r['method']] = r['amount']
        for r in db.execute('SELECT p.method,SUM(p.amount_cents) amount FROM return_payments p JOIN returns r ON r.id=p.return_id WHERE r.shift_id=? GROUP BY p.method', (sid,)):
            refunds[r['method']] = r['amount']
        movements = [dict(r) for r in db.execute('SELECT m.*,s.business_name supplier_name FROM cash_movements m LEFT JOIN suppliers s ON s.id=m.supplier_id WHERE m.shift_id=? ORDER BY m.id', (sid,))]
        collections = {r["method"]:r["amount"] for r in db.execute("SELECT method,-SUM(amount_cents) amount FROM customer_ledger WHERE shift_id=? AND amount_cents<0 GROUP BY method",(sid,))}
        incoming = sum(m['amount_cents'] for m in movements if m['direction']=='in')
        outgoing = sum(m['amount_cents'] for m in movements if m['direction']=='out')
        departments = [dict(r) for r in db.execute('''SELECT c.id category_id,c.name,COALESCE(s.gross,0) sales_cents,COALESCE(r.refunds,0) refunds_cents,
             COALESCE(s.gross,0)-COALESCE(r.refunds,0) net_cents FROM categories c
             LEFT JOIN (SELECT i.category_id,SUM(i.total_cents) gross FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE s.shift_id=? AND NOT EXISTS(SELECT 1 FROM customer_ledger l WHERE l.sale_id=s.id) GROUP BY i.category_id) s ON s.category_id=c.id
             LEFT JOIN (SELECT i.category_id,SUM(ri.total_cents) refunds FROM return_items ri JOIN returns r ON r.id=ri.return_id JOIN sale_items i ON i.id=ri.sale_item_id WHERE r.shift_id=? GROUP BY i.category_id) r ON r.category_id=c.id''', (sid,sid))]
        from cash_basis import collections as collection_entries
        departments_by_id={r['category_id']:r for r in departments}
        for entry in collection_entries(db,shift_id=sid):
            row=departments_by_id[entry['category_id']];row['sales_cents']+=entry['cents'];row['net_cents']+=entry['cents']
        expected = shift['opening_cents'] + payments['cash'] - refunds['cash'] + incoming - outgoing + collections.get('cash',0)
        result = {'accounting_basis':'collected','shift_id': sid, 'opening_cents': shift['opening_cents'], 'sales_by_method': payments, 'collections_by_method': collections, 'on_account_cents': db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM customer_ledger WHERE shift_id=? AND amount_cents>0',(sid,)).fetchone()[0],
                'refunds_by_method': refunds, 'incoming_cents': incoming, 'outgoing_cents': outgoing,
                'expected_cents': expected, 'net_sales_cents': sum(payments.values()) + sum(collections.values()) - sum(refunds.values()),
                'departments': departments, 'movements': movements}
        if shift['closed_at']:
            result.update(type='Z',counted_cents=shift['counted_cents'],expected_cents=shift['expected_cents'],difference_cents=shift['counted_cents']-shift['expected_cents'])
        return result

    def close_shift(self, uid, data):
        counted = integer(data.get('counted_cents'), 'Efectivo contado')
        sid = integer(data.get('shift_id'), 'Turno', 1)
        with self.db(True) as db:
            self.require(db, uid, 'sell')
            from operation_journal import lookup
            for intent in db.execute('SELECT kind,request_key FROM operation_intents WHERE user_id=? AND acknowledged=0',(uid,)):
                if lookup(self,db,uid,intent['kind'],intent['request_key'])['state']=='not_found':raise Error('Comprueba o cancela la operación pendiente antes de cerrar el turno',409)
            existing = db.execute('SELECT * FROM cash_shifts WHERE id=? AND user_id=?', (sid,uid)).fetchone()
            if existing and existing['closed_at']:
                if existing['counted_cents'] != counted:
                    raise Error('Este turno ya fue cerrado con otro conteo',409)
                report = self.report(db,sid)
            else:
                self.shift(db,uid,sid)
                report = self.report(db, sid)
                import profit
                report.update(profit.shift(db,sid))
                report['report_version']=2
                report['user_name']=db.execute('SELECT display_name FROM users WHERE id=?',(uid,)).fetchone()[0]
                report.update(counted_cents=counted, difference_cents=counted-report['expected_cents'], type='Z')
                db.execute("UPDATE cash_shifts SET closed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),counted_cents=?,expected_cents=?,report_json=? WHERE id=? AND closed_at IS NULL",
                           (counted, report['expected_cents'], json.dumps(report), sid))
                self.audit(db,uid,'shift.close',sid,{'counted_cents':counted})
        from automatic_backup import after_shift
        report['automatic_backup'] = after_shift(self,sid)
        return report

    def sale(self, uid, data):
        key = required(data, 'request_key')
        digest = fingerprint(data)
        with self.db(True) as db:
            self.require(db,uid,'sell')
            cancelled=db.execute("SELECT 1 FROM operation_requests WHERE kind='sale' AND user_id=? AND request_key=?",(uid,key)).fetchone()
            if cancelled:raise Error('Esta operación fue cancelada. No se registró otra venta.',409)
            previous = db.execute('SELECT * FROM sales WHERE request_key=?', (key,)).fetchone()
            if previous:
                if previous['user_id'] != uid or previous['request_hash'] != digest:
                    raise Error('Clave de solicitud reutilizada con otros datos',409)
                return self.ticket(db, previous['id'])
            sid = self.shift(db, uid)['id']
            customer_id = data.get('customer_id') or None
            customer = db.execute('SELECT * FROM customers WHERE id=? AND active=1',(customer_id,)).fetchone() if customer_id else None
            if customer_id and not customer:
                raise Error('Cliente inexistente')
            discount_bps = customer['discount_bps'] if customer else 0
            cart = data.get('items')
            if not isinstance(cart,list) or not 1 <= len(cart) <= 200:
                raise Error('El carrito debe contener entre 1 y 200 productos')
            seen = set()
            lines = []
            today = dt.date.today().isoformat()
            from promotions import active as active_promotions, total as promotion_total
            promotions=active_promotions(db)
            for entry in cart:
                pid = integer(entry.get('product_id'),'Producto',1)
                qty = integer(entry.get('quantity'),'Cantidad',1,100000)
                if pid in seen:
                    raise Error('Agrupa las cantidades de cada producto')
                seen.add(pid)
                p = db.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
                if not p:
                    raise Error('Producto no disponible')
                if p['requires_prescription']:
                    rx = entry.get('prescription') or {}
                    for field in ('doctor_name','license_number','prescription_ref'):
                        required(rx,field)
                gross = p['price_cents'] * qty
                discount = rounded(gross * discount_bps,10000)
                if pid in promotions:
                    discount=max(discount,gross-promotion_total(promotions[pid],p['price_cents'],qty))
                total = gross - discount
                tax = rounded(total * p['tax_bps'],10000+p['tax_bps'])
                remaining, allocations = qty, []
                for batch in db.execute('SELECT * FROM batches WHERE product_id=? AND quantity>0 AND (expires_on IS NULL OR expires_on>?) ORDER BY (expires_on IS NULL),expires_on,received_at,id',(pid,today)):
                    take = min(remaining,batch['quantity'])
                    allocations.append((batch,take))
                    remaining -= take
                    if remaining == 0:
                        break
                if remaining:
                    raise Error(f'Stock vendible insuficiente: {p["name"]}',409)
                lines.append((p,qty,discount,total,tax,allocations,entry.get('prescription')))
            total = sum(l[3] for l in lines)
            payments = data.get('payments',[])
            if not isinstance(payments,list) or len(payments)>4:
                raise Error('Pagos inválidos')
            methods, paid, validated = set(),0,[]
            for p in payments:
                method = p.get('method')
                if method not in ('cash','debit','credit','transfer') or method in methods:
                    raise Error('Método inválido o repetido')
                methods.add(method)
                amount = integer(p.get('amount_cents'),'Pago',1)
                tendered = integer(p.get('tendered_cents',amount),'Recibido',amount)
                if method != 'cash' and tendered != amount:
                    raise Error('Solo el efectivo permite cambio')
                paid += amount
                validated.append((method,amount,tendered,str(p.get('reference',''))[:500]))
            on_account = data.get("on_account") is True
            if on_account:
                self.require(db,uid,"customers.manage")
                if not customer or payments or total<=0:
                    raise Error("Selecciona un cliente y no incluyas pagos al fiar")
            if not on_account and paid != total:
                raise Error(f'Los pagos deben sumar {total} centavos')
            sale_id = db.execute('INSERT INTO sales(request_key,request_hash,shift_id,user_id,customer_id,total_cents,tax_cents,discount_cents) VALUES (?,?,?,?,?,?,?,?)',
                (key,digest,sid,uid,customer_id,total,sum(l[4] for l in lines),sum(l[2] for l in lines))).lastrowid
            for p,qty,discount,line_total,tax,allocations,rx in lines:
                iid = db.execute('INSERT INTO sale_items(sale_id,product_id,category_id,product_name,quantity,unit_price_cents,tax_bps,discount_cents,total_cents,tax_cents) VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (sale_id,p['id'],p['category_id'],p['name'],qty,p['price_cents'],p['tax_bps'],discount,line_total,tax)).lastrowid
                for batch,take in allocations:
                    changed = db.execute('UPDATE batches SET quantity=quantity-? WHERE id=? AND quantity>=?',(take,batch['id'],take)).rowcount
                    if changed != 1:
                        raise Error('El inventario cambió; intenta de nuevo',409)
                    db.execute('INSERT INTO sale_item_batches(sale_item_id,batch_id,quantity,unit_cost_cents) VALUES (?,?,?,?)',(iid,batch['id'],take,batch['unit_cost_cents']))
                    db.execute("INSERT INTO inventory_movements(batch_id,user_id,quantity_delta,kind,reason,sale_item_id) VALUES (?,?,?,'sale','Venta',?)",(batch['id'],uid,-take,iid))
                if p['requires_prescription']:
                    db.execute('INSERT INTO prescriptions(sale_item_id,doctor_name,license_number,prescription_ref) VALUES (?,?,?,?)',(iid,rx['doctor_name'],rx['license_number'],rx['prescription_ref']))
            db.executemany('INSERT INTO sale_payments(sale_id,method,amount_cents,tendered_cents,reference) VALUES (?,?,?,?,?)',[(sale_id,*p) for p in validated])
            from card_fees import record
            record(db,'sale',sale_id,sum(p[1] for p in validated if p[0] in ('debit','credit')))
            if on_account:
                db.execute("INSERT INTO customer_ledger(customer_id,sale_id,shift_id,user_id,amount_cents) VALUES (?,?,?,?,?)",(customer_id,sale_id,sid,uid,total))
            self.audit(db,uid,'sale',sale_id,{'total_cents':total})
            return self.ticket(db,sale_id)

    def ticket(self, db, sale_id):
        row = db.execute('SELECT * FROM sales WHERE id=?',(sale_id,)).fetchone()
        if not row:
            raise Error('Ticket inexistente',404)
        result = {k:row[k] for k in ('id','user_id','shift_id','customer_id','total_cents','tax_cents','discount_cents','status','created_at')}
        result['items'] = [dict(r) for r in db.execute('SELECT * FROM sale_items WHERE sale_id=?',(sale_id,))]
        result['payments'] = [dict(r) for r in db.execute('SELECT method,amount_cents,tendered_cents,reference FROM sale_payments WHERE sale_id=?',(sale_id,))]
        result["on_account"] = bool(db.execute("SELECT 1 FROM customer_ledger WHERE sale_id=?",(sale_id,)).fetchone())
        result['change_cents'] = sum(p['tendered_cents']-p['amount_cents'] for p in result['payments'])
        return result

    def return_sale(self, uid, data):
        key, digest = required(data,'request_key'),fingerprint(data)
        kind = data.get('kind','return')
        if kind not in ('return','void'):
            raise Error('Tipo de devolución inválido')
        with self.db(True) as db:
            self.require(db,uid,'sales.void' if kind=='void' else 'sales.return')
            old = db.execute('SELECT * FROM returns WHERE request_key=?',(key,)).fetchone()
            if old:
                if old['user_id']!=uid or old['request_hash']!=digest:
                    raise Error('Clave reutilizada con otros datos',409)
                return {'id':old['id'],'total_cents':old['total_cents']}
            sid = self.shift(db,uid)['id']
            sale_id = integer(data.get('sale_id'),'Ticket',1)
            sale = db.execute('SELECT * FROM sales WHERE id=?',(sale_id,)).fetchone()
            if not sale or sale['status'] in ('returned','voided'):
                raise Error('Ticket no disponible para devolución',409)
            if db.execute("SELECT 1 FROM customer_ledger WHERE sale_id=?",(sale_id,)).fetchone():
                raise Error("No está disponible devolver tickets fiados; requieren conciliar la cartera")
            if kind=='void' and sale['status']!='completed':
                raise Error('Un ticket con devoluciones parciales no puede anularse')
            items = data.get('items')
            if kind=='void':
                items = [{'sale_item_id':r['id'],'quantity':r['quantity'],'disposition':'restock'} for r in db.execute('SELECT * FROM sale_items WHERE sale_id=?',(sale_id,))]
            if not isinstance(items,list) or not items or len(items)>200:
                raise Error('Selecciona partidas para devolver')
            lines, seen = [],set()
            for entry in items:
                iid = integer(entry.get('sale_item_id'),'Partida',1)
                qty = integer(entry.get('quantity'),'Cantidad',1)
                if iid in seen:
                    raise Error('Partida repetida')
                seen.add(iid)
                item = db.execute('SELECT * FROM sale_items WHERE id=? AND sale_id=?',(iid,sale_id)).fetchone()
                if not item:
                    raise Error('Partida ajena al ticket')
                previous = db.execute('SELECT COALESCE(SUM(quantity),0) FROM return_items WHERE sale_item_id=?',(iid,)).fetchone()[0]
                if previous+qty > item['quantity']:
                    raise Error('La devolución supera la cantidad vendida',409)
                disposition = entry.get('disposition','restock')
                if disposition not in ('restock','quarantine'):
                    raise Error('Destino inválido')
                # Diferencia de acumulados: conserva exactamente los centavos al devolver todo.
                amount = rounded(item['total_cents']*(previous+qty),item['quantity']) - rounded(item['total_cents']*previous,item['quantity'])
                tax = rounded(item['tax_cents']*(previous+qty),item['quantity']) - rounded(item['tax_cents']*previous,item['quantity'])
                lines.append((item,qty,amount,tax,disposition))
            total = sum(l[2] for l in lines)
            remaining_refund, refunds = total,[]
            # Se devuelve a los medios originales, en orden determinista, sin excederlos.
            for payment in db.execute('SELECT * FROM sale_payments WHERE sale_id=? ORDER BY CASE method WHEN \'cash\' THEN 0 ELSE 1 END,id',(sale_id,)):
                used = db.execute('SELECT COALESCE(SUM(p.amount_cents),0) FROM return_payments p JOIN returns r ON r.id=p.return_id WHERE r.sale_id=? AND p.method=?',(sale_id,payment['method'])).fetchone()[0]
                value = min(remaining_refund,payment['amount_cents']-used)
                if value:
                    refunds.append((payment['method'],value))
                    remaining_refund -= value
            if remaining_refund:
                raise Error('Reembolso inconsistente',409)
            reason = required(data,'reason')
            rid = db.execute('INSERT INTO returns(sale_id,shift_id,user_id,request_key,request_hash,reason,kind,total_cents) VALUES (?,?,?,?,?,?,?,?)',
                             (sale_id,sid,uid,key,digest,reason,kind,total)).lastrowid
            for item,qty,amount,tax,disposition in lines:
                ri = db.execute('INSERT INTO return_items(return_id,sale_item_id,quantity,total_cents,tax_cents,disposition) VALUES (?,?,?,?,?,?)',(rid,item['id'],qty,amount,tax,disposition)).lastrowid
                remaining = qty
                for allocation in db.execute('SELECT * FROM sale_item_batches WHERE sale_item_id=? ORDER BY id',(item['id'],)):
                    used = db.execute('SELECT COALESCE(SUM(quantity),0) FROM return_allocations WHERE sale_item_batch_id=?',(allocation['id'],)).fetchone()[0]
                    take = min(remaining,allocation['quantity']-used)
                    if not take:
                        continue
                    db.execute('INSERT INTO return_allocations(return_item_id,sale_item_batch_id,quantity) VALUES (?,?,?)',(ri,allocation['id'],take))
                    if disposition=='restock':
                        db.execute('UPDATE batches SET quantity=quantity+? WHERE id=?',(take,allocation['batch_id']))
                        db.execute("INSERT INTO inventory_movements(batch_id,user_id,quantity_delta,kind,reason,return_item_id) VALUES (?,?,?,'return',?,?)",(allocation['batch_id'],uid,take,reason,ri))
                    else:
                        db.execute('INSERT INTO quarantine(batch_id,return_item_id,quantity,reason) VALUES (?,?,?,?)',(allocation['batch_id'],ri,take,reason))
                    remaining -= take
                    if not remaining:
                        break
                if remaining:
                    raise Error('Trazabilidad de lote inconsistente',409)
            db.executemany('INSERT INTO return_payments(return_id,method,amount_cents) VALUES (?,?,?)',[(rid,*p) for p in refunds])
            sold = db.execute('SELECT SUM(quantity) FROM sale_items WHERE sale_id=?',(sale_id,)).fetchone()[0]
            returned = db.execute('SELECT SUM(ri.quantity) FROM return_items ri JOIN returns r ON r.id=ri.return_id WHERE r.sale_id=?',(sale_id,)).fetchone()[0]
            status = 'voided' if kind=='void' else ('returned' if sold==returned else 'partial_return')
            db.execute('UPDATE sales SET status=? WHERE id=?',(status,sale_id))
            self.audit(db,uid,'sale.'+kind,rid,{'sale_id':sale_id,'total_cents':total})
            return {'id':rid,'total_cents':total,'refunds':[{'method':m,'amount_cents':a} for m,a in refunds]}

    def restock(self, uid, data):
        """Entrada sencilla: conserva ficha y usa el último costo de recepción."""
        with self.db(True) as db:
            self.require(db,uid,'inventory.receive')
            from operation_requests import previous,save
            old=previous(db,uid,'restock',data)
            if old is not None:return old
            pid=integer(data.get('product_id'),'Producto',1)
            product=db.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
            if not product:raise Error('Producto inexistente o dado de baja',404)
            qty=integer(data.get('quantity'),'Cantidad',1,1000000)
            latest=db.execute('SELECT unit_cost_cents FROM batches WHERE product_id=? ORDER BY received_at DESC,id DESC LIMIT 1',(pid,)).fetchone()
            cost=latest['unit_cost_cents'] if latest else product['cost_cents']
            before=db.execute('SELECT COALESCE(SUM(quantity),0) FROM batches WHERE product_id=? AND (expires_on IS NULL OR expires_on>?)',(pid,dt.date.today().isoformat())).fetchone()[0]
            bid=db.execute('INSERT INTO batches(product_id,lot_number,quantity,unit_cost_cents) VALUES (?,?,?,?)',(pid,'SIN LOTE CAPTURADO',qty,cost)).lastrowid
            db.execute("INSERT INTO inventory_movements(batch_id,user_id,quantity_delta,kind,reason) VALUES (?,?,?,'receipt','Recepción de mercancía')",(bid,uid,qty))
            self.audit(db,uid,'inventory.receive',bid,{'product_id':pid,'quantity':qty,'unit_cost_cents':cost})
            return save(db,uid,'restock',data,{'id':bid,'stock_before':before,'stock_after':before+qty})

    def receive(self, uid, data):
        with self.db(True) as db:
            self.require(db,uid,'inventory.receive')
            from operation_requests import previous,save
            old=previous(db,uid,'receive',data)
            if old is not None:return old
            expiry = data.get('expires_on') or None
            try:
                if expiry is not None and dt.date.fromisoformat(expiry).isoformat()!=expiry:
                    raise ValueError()
            except ValueError:
                raise Error('Caducidad inválida: usa AAAA-MM-DD')
            qty = integer(data.get('quantity'),'Cantidad',1,1000000)
            if data.get('supplier_id') and not db.execute('SELECT 1 FROM suppliers WHERE id=? AND active=1',(integer(data['supplier_id'],'Proveedor',1),)).fetchone():raise Error('Proveedor inexistente o dado de baja')
            bid = db.execute('INSERT INTO batches(product_id,supplier_id,lot_number,expires_on,quantity,unit_cost_cents) VALUES (?,?,?,?,?,?)',
                (integer(data.get('product_id'),'Producto',1),integer(data['supplier_id'],'Proveedor',1) if data.get('supplier_id') else None,
                 str(data.get('lot_number') or 'SIN LOTE CAPTURADO').strip(),expiry,qty,integer(data.get('unit_cost_cents'),'Costo'))).lastrowid
            db.execute("INSERT INTO inventory_movements(batch_id,user_id,quantity_delta,kind,reason) VALUES (?,?,?,'receipt',?)",(bid,uid,qty,required(data,'reason')))
            self.audit(db,uid,'inventory.receive',bid,data)
            return save(db,uid,'receive',data,{'id':bid})

    def adjust(self, uid, data):
        with self.db(True) as db:
            self.require(db,uid,'inventory.adjust')
            bid = integer(data.get('batch_id'),'Lote',1)
            target = integer(data.get('counted_quantity'),'Conteo',0,1000000)
            expected = integer(data.get('expected_quantity'),'Existencia observada',0,1000000)
            row = db.execute('SELECT quantity FROM batches WHERE id=?',(bid,)).fetchone()
            if not row:
                raise Error('Lote inexistente',404)
            if row[0]!=expected:
                raise Error('El stock cambió durante el conteo. Actualiza y revisa.',409)
            delta = target-row[0]
            reason = required(data,'reason')
            if not delta:
                raise Error('El conteo no cambia la existencia')
            db.execute('UPDATE batches SET quantity=? WHERE id=?',(target,bid))
            db.execute("INSERT INTO inventory_movements(batch_id,user_id,quantity_delta,kind,reason) VALUES (?,?,?,'adjustment',?)",(bid,uid,delta,reason))
            self.audit(db,uid,'inventory.adjust',bid,data)
            return {'quantity':target}

    def edit_batch(self, uid, data):
        with self.db(True) as db:
            self.require(db,uid,'inventory.adjust')
            bid=integer(data.get('batch_id'),'Lote',1)
            old=db.execute('SELECT * FROM batches WHERE id=?',(bid,)).fetchone()
            if not old:
                raise Error('Lote inexistente',404)
            expiry=data.get('expires_on') or None
            try:
                if expiry is not None and dt.date.fromisoformat(expiry).isoformat()!=expiry:raise ValueError()
            except (TypeError,ValueError):raise Error('Caducidad inválida')
            lot=str(data.get('lot_number') or old['lot_number']).strip()
            if len(lot)>500:
                raise Error('Número de lote demasiado largo')
            reason=required(data,'reason')
            db.execute('UPDATE batches SET expires_on=?,lot_number=? WHERE id=?',(expiry,lot,bid))
            self.audit(db,uid,'batch.edit',bid,{'before':{'lot_number':old['lot_number'],'expires_on':old['expires_on']},
                'after':{'lot_number':lot,'expires_on':expiry},'reason':reason})
            return {'id':bid}

    def save_product(self, uid, data):
        pid = data.get('id')
        with self.db(True) as db:
            self.require(db,uid,'products.edit' if pid else 'products.create')
            fields = ['barcode','name','generic_name','category_id','cost_cents','price_cents','tax_bps','min_stock','max_stock','reorder_point','requires_prescription']
            values = [required(data,'barcode'),required(data,'name'),str(data.get('generic_name',''))[:500]]
            for field in fields[3:]:
                value = data.get(field,0)
                if field=='requires_prescription' and isinstance(value,bool):
                    value = int(value)
                values.append(integer(value,field,0,10000 if field=='tax_bps' else (1 if field=='requires_prescription' else 10**12)))
            if pid:
                old = db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
                if not old:
                    raise Error('Producto inexistente',404)
                if 'costs.view' not in self.permissions(db,uid):
                    values[4] = old['cost_cents']
                changes={field:{'before':old[field],'after':values[fields.index(field)]} for field in ('cost_cents','price_cents') if old[field]!=values[fields.index(field)]}
                if changes:
                    if not isinstance(data.get('reason'),str) or not data['reason'].strip():
                        raise Error('Escribe el motivo del cambio de precio o costo')
                    reason=required(data,'reason')
                    self.audit(db,uid,'product.price_change',pid,{'changes':changes,'reason':reason,'name':values[1],'barcode':values[0]})
                db.execute('UPDATE products SET '+','.join(f'{f}=?' for f in fields)+' WHERE id=?',(*values,pid))
            else:
                pid = db.execute('INSERT INTO products('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')',values).lastrowid
            self.audit(db,uid,'product.save',pid,{'name':data['name']})
            return {'id':pid}

    def save_user(self, uid, data):
        with self.db(True) as db:
            actor_role, allowed = self.account_access(db, uid)
            target = data.get('id')
            permissions = data.get('permissions',[])
            if not isinstance(permissions,list) or any(not isinstance(p,str) or p not in PERMISSIONS for p in permissions):
                raise Error('Permisos inválidos')
            permissions = set(permissions)
            old = None
            old_permissions = set()
            old_role = None
            if target is not None:
                target = integer(target, 'Usuario', 1)
                old = db.execute('SELECT username,display_name,active FROM users WHERE id=?',(target,)).fetchone()
                if old is None:
                    raise Error('Usuario inexistente',404)
                old_permissions = self.permissions(db, target)
                old_role = self.account_role(db, target, old_permissions)
                if not self.can_edit_account(db, uid, target, actor_role, allowed, old_permissions):
                    raise Error('No tienes permiso para modificar esta cuenta',403)
            role = data.get('role')
            if role is None:
                role = old_role or ('administrator' if permissions & ADMIN_PERMISSIONS else 'seller')
            if not isinstance(role, str) or role not in ACCOUNT_ROLES:
                raise Error('Puesto inválido')
            if (permissions - allowed or (actor_role == 'supervisor' and role != 'seller')
                    or (old and role == 'administrator')
                    or (role != 'administrator' and permissions & ADMIN_PERMISSIONS)):
                raise Error('No puedes asignar ese puesto o esos permisos',403)
            secret = data.get('secret','')
            if secret and not (len(secret)>=8 or (secret.isdigit() and len(secret)>=6)):
                raise Error('Usa contraseña de 8 caracteres o PIN de al menos 6 dígitos')
            display_name = required(data, 'display_name')
            active = integer(data.get('active', 1), 'Activo', 0, 1)
            if old:
                if not active and db.execute('SELECT 1 FROM cash_shifts WHERE user_id=? AND closed_at IS NULL',(target,)).fetchone():raise Error('Primero cierra el turno del usuario',409)
                username = old['username']
                db.execute('UPDATE users SET display_name=?,active=? WHERE id=?',(display_name,active,target))
                if secret:
                    db.execute('UPDATE users SET password_hash=? WHERE id=?',(password_hash(secret),target))
                db.execute('DELETE FROM sessions WHERE user_id=?',(target,))
                db.execute('DELETE FROM user_permissions WHERE user_id=?',(target,))
            else:
                if not secret:
                    raise Error('Contraseña o PIN obligatorio')
                username = required(data,'username').lower()
                if '\0' in username or len(username)>50:
                    raise Error('Usuario inválido')
                target = db.execute('INSERT INTO users(username,display_name,password_hash,active) VALUES (?,?,?,?)',(username,display_name,password_hash(secret),active)).lastrowid
            db.execute('INSERT OR IGNORE INTO roles(name) VALUES (?)', (ACCOUNT_ROLES[role],))
            db.execute('DELETE FROM user_roles WHERE user_id=?', (target,))
            db.execute('INSERT INTO user_roles SELECT ?,id FROM roles WHERE name=?', (target, ACCOUNT_ROLES[role]))
            db.executemany('INSERT INTO user_permissions VALUES (?,?,?)',[(target,p,int(p in permissions)) for p in PERMISSIONS])
            before = {'display_name':old['display_name'],'active':old['active'],
                      'role':old_role,'permissions':sorted(old_permissions)} if old else {}
            after = {'display_name':display_name,'active':active,'role':role,'permissions':sorted(permissions)}
            self.audit(db,uid,'user.update' if old else 'user.create',target,{
                'username':username,'actor_role':actor_role,'before':before,'after':after,
                'credential_reset':bool(old and secret)})
            return {'id':target}
