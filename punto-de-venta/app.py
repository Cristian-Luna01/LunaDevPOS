"""Servidor local sin dependencias externas. Python 3.11+."""
import argparse
import contextlib
import datetime as dt
import getpass
import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from http_limits import ThreadingHTTPServer
import json
import logging
import socket
import time
import os
import sqlite3
from urllib.parse import urlparse, parse_qs
from core import POS, Error, PERMISSIONS, ROOT, required, credential, integer, rounded
import inventory_io
import analytics
import profit
import promotions
import credit
import branding

class Handler(BaseHTTPRequestHandler):
    server_version = 'FarmaciaPOS/1.0'

    def log_message(self, fmt, *args):
        # Evita registrar nombres, teléfonos, búsquedas y credenciales.
        logging.info('%s %s', self.command, urlparse(self.path).path)

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def send(self, status, body, mime='application/json; charset=utf-8', cookie=None, filename=None):
        if getattr(self,'_defer_response',False):
            self._response=(status,body,mime,cookie,filename)
            return
        if callable(body):body=body()
        if not isinstance(body,bytes):
            body = json.dumps(body,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
        if filename:
            self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        if cookie:
            self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.handle_request(False)

    def do_POST(self):
        self.handle_request(True)

    def handle_request(self, write):
        # La espera de red nunca retiene el bloqueo de identidad/restauración.
        try:
            self._request_data=None
            host=self.headers.get('Host','')
            if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
                raise Error('Host no permitido',403)
            if write:
                if self.headers.get('Origin') not in (None,f'http://{host}') or self.headers.get('X-POS-Request')!='1':raise Error('Origen de solicitud no permitido',403)
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise Error('Usa application/json',415)
                if self.headers.get('Transfer-Encoding'):raise Error('Transferencia no admitida',400)
                path=urlparse(self.path).path
                file_route=path in ('/api/branding','/direccion/api/branding','/api/inventory/import/preview','/api/inventory/import/confirm','/api/backup/preview','/api/backup/restore')
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=(90*1024*1024 if file_route else 262144):raise Error('Tamaño de solicitud inválido',413)
                deadline=time.monotonic()+30;remaining=length;parts=[]
                while remaining:
                    seconds=deadline-time.monotonic()
                    if seconds<=0:raise TimeoutError()
                    self.connection.settimeout(min(10,seconds))
                    chunk=self.rfile.read1(min(65536,remaining))
                    if not chunk:raise Error('Solicitud incompleta',400)
                    parts.append(chunk);remaining-=len(chunk)
                self._request_data=json.loads(b''.join(parts))
                if not isinstance(self._request_data,dict):raise Error('Objeto JSON requerido')
            self.connection.settimeout(10)
            if write and urlparse(self.path).path=='/api/backup/external/choose':
                pos=self.server.pos
                cookies=SimpleCookie(self.headers.get('Cookie',''));name=f'pos_session_{self.server.server_port}'
                token=cookies[name].value if name in cookies else ''
                with pos.request_lock:
                    uid=pos.session_user(token)
                    with pos.db() as db:pos.require(db,uid,'backup.manage')
                picker=getattr(self.server,'choose_backup_directory',None)
                if not picker:raise Error('El selector está disponible en la aplicación de escritorio. También puedes escribir la ruta.',503)
                directory=picker()
                with pos.request_lock:pos.session_user(token)
                return self.send(200,{'directory':directory})
            self._defer_response=True;self._response=None
            lock=self.server.pos.request_lock
            if not lock.acquire(timeout=10):raise Error('Operación ocupada. Vuelve a consultar antes de repetir un cobro.',503)
            try:self.handle_locked_request(write)
            finally:lock.release()
            self._defer_response=False
            if self._response:self.send(*self._response)
        except (TimeoutError,socket.timeout):
            self._defer_response=False;self.close_connection=True
            try:self.send(408,{'error':'Tiempo de solicitud agotado. Consulta el registro antes de reintentar.'})
            except OSError:pass
        except (BrokenPipeError,ConnectionResetError):self.close_connection=True
        except (Error,ValueError) as e:
            self._defer_response=False;self.close_connection=True
            try:self.send(e.status if isinstance(e,Error) else 400,{'error':str(e) if isinstance(e,Error) else 'Solicitud inválida'})
            except OSError:pass

    def handle_locked_request(self, write):
        try:
            host = self.headers.get('Host','')
            if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
                raise Error('Host no permitido',403)
            path = urlparse(self.path).path
            if write:
                if self.headers.get('Origin') not in (None,f'http://{host}') or self.headers.get('X-POS-Request')!='1':
                    raise Error('Origen de solicitud no permitido',403)
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    raise Error('Usa application/json',415)
                length = int(self.headers.get('Content-Length','0'))
                file_route=path in ('/api/branding','/direccion/api/branding','/api/inventory/import/preview','/api/inventory/import/confirm','/api/backup/preview','/api/backup/restore')
                if not 0<length<=(90*1024*1024 if file_route else 262144):
                    raise Error('Tamaño de solicitud inválido',413)
                data = self._request_data
                if not isinstance(data,dict):
                    raise Error('Objeto JSON requerido')
            else:
                data = {k:v[0] for k,v in parse_qs(urlparse(self.path).query).items()}
            if not write and path in ('/','/backup-external-ui.js','/pending-operations.js','/tickets-ui.js','/entities-ui.js','/card-fees-ui.js','/billing-ui.js','/login-hints.js','/live-view.js','/owner-access-ui.js','/metric-help.js','/app.js','/style.css','/inventory-ui.js','/direccion','/direccion/','/direccion/panel.js','/stock.js','/reports.js','/promotions-ui.js','/branding.js','/navigation.js'):
                filename,mime = {'/backup-external-ui.js':('backup-external-ui.js','text/javascript'),'/pending-operations.js':('pending-operations.js','text/javascript'),'/tickets-ui.js':('tickets-ui.js','text/javascript'),'/entities-ui.js':('entities-ui.js','text/javascript'),'/card-fees-ui.js':('card-fees-ui.js','text/javascript'),'/billing-ui.js':('billing-ui.js','text/javascript'),'/login-hints.js':('login-hints.js','text/javascript'),'/live-view.js':('live-view.js','text/javascript'),'/owner-access-ui.js':('owner-access-ui.js','text/javascript'),'/metric-help.js':('metric-help.js','text/javascript'),'/navigation.js':('navigation.js','text/javascript'),'/branding.js':('branding.js','text/javascript'),'/':('index.html','text/html'),'/app.js':('app.js','text/javascript'),'/inventory-ui.js':('inventory-ui.js','text/javascript'),'/direccion':('direction.html','text/html'),'/direccion/':('direction.html','text/html'),'/direccion/panel.js':('direction.js','text/javascript'),'/promotions-ui.js':('promotions-ui.js','text/javascript'),'/reports.js':('reports.js','text/javascript'),'/stock.js':('stock.js','text/javascript'),'/style.css':('style.css','text/css')}[path]
                return self.send(200,(ROOT/'static'/filename).read_bytes(),mime+'; charset=utf-8')
            pos = self.server.pos
            if not write and path=='/favicon.svg':return self.send(200,(ROOT/'static'/'favicon.svg').read_bytes(),'image/svg+xml')
            if not write and path=='/business-settings':return self.send(200,branding.settings(pos))
            if not write and path=='/business-logo.png':
                raw=branding.read(pos)
                return self.send(200,raw,'image/png') if raw else self.send(404,{'error':'Sin logotipo'})
            if path.startswith('/direccion/api/'):
                return self.direction(pos,path,data,write)
            cookie_name=f'pos_session_{self.server.server_port}'
            if write and path=='/api/login':
                token = pos.login(required(data,'username'),credential(data))
                return self.send(200,{'ok':True},cookie=f'{cookie_name}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200')
            cookies = SimpleCookie(self.headers.get('Cookie',''))
            token = cookies[cookie_name].value if cookie_name in cookies else ''
            uid = pos.session_user(token)
            if path=='/api/card-fees/settings':
                import card_fees
                return self.send(200,card_fees.settings(pos,uid,data if write else None))
            if path.startswith('/api/billing/'):
                from billing_http import handle
                return handle(self,pos,uid,path,data,write)
            if path.startswith('/api/branch-sync/'):
                with pos.db() as db:
                    pos.require(db,uid,'users.manage');pos.require(db,uid,'reports.view')
                manager=getattr(self.server,'branch_sync',None)
                if not manager:raise Error('Actualiza la versión de escritorio para vincular sucursales',503)
                if path=='/api/branch-sync/status' and not write:return self.send(200,manager.status())
                if path=='/api/branch-sync/configure' and write:return self.send(200,manager.configure(data))
                if path=='/api/branch-sync/disconnect' and write:return self.send(200,manager.disconnect())
                raise Error('Ruta inexistente',404)
            if path in ('/api/owner-access/status','/api/owner-access/start','/api/owner-access/stop','/api/owner-access/local/start','/api/owner-access/local/stop','/api/owner-access/copy'):
                with pos.db() as db:
                    pos.require(db,uid,'users.manage');pos.require(db,uid,'reports.view')
                manager=getattr(self.server,'owner_access',None)
                if not manager:return self.send(200,{'available':False,'state':'off','url':''})
                if path=='/api/owner-access/copy' and write:
                    state=manager.status();url=data.get('url','');kind=data.get('kind')
                    allowed=[state.get('url','')] if kind=='remote' else state.get('local_urls',[]) if kind=='local' else []
                    if not isinstance(url,str) or not url or url not in allowed:raise Error('El enlace cambió o no está activo. Actualiza la configuración antes de copiar.')
                    copier=getattr(self.server,'copy_owner_link',None)
                    if copier and not copier(url):raise Error('No se pudo copiar al portapapeles. Vuelve a intentarlo.')
                    return self.send(200,{'native':bool(copier),'copied':bool(copier)})
                if path=='/api/owner-access/status' and not write:return self.send(200,manager.status())
                if path=='/api/owner-access/start' and write:return self.send(200,manager.start(data.get('email',''),data.get('mode','email')))
                if path=='/api/owner-access/stop' and write:manager.stop_remote();return self.send(200,manager.status())
                if path=='/api/owner-access/local/start' and write:return self.send(200,manager.start_local())
                if path=='/api/owner-access/local/stop' and write:manager.stop_local();return self.send(200,manager.status())
                raise Error('Ruta inexistente',404)
            if path.startswith('/api/entities/'):
                from entity_management import listing,status
                parts=path.split('/')
                if len(parts)==4 and parts[3] in ('customers','suppliers') and not write:return self.send(200,listing(pos,uid,parts[3]))
                if len(parts)==5 and parts[4]=='status' and parts[3] in ('customers','suppliers','users') and write:return self.send(200,status(pos,uid,parts[3],data))
                raise Error('Ruta inexistente',404)
            if path=='/api/inventory/product' and not write:
                from inventory_count import read
                return self.send(200,read(pos,uid,data))
            if path=='/api/inventory/count' and write:
                from inventory_count import apply
                return self.send(200,apply(pos,uid,data))
            if path=='/api/backup/external':
                from external_backup import settings,configure
                with pos.db() as db:pos.require(db,uid,'backup.manage')
                return self.send(200,configure(pos,data.get('directory','')) if write else settings(pos))
            if path=='/api/backup/external/copy' and write:
                from external_backup import write_copy
                with pos.db() as db:
                    pos.require(db,uid,'backup.manage')
                    closed=db.execute('SELECT id FROM cash_shifts WHERE closed_at IS NOT NULL ORDER BY id DESC LIMIT 1').fetchone()
                if not closed:raise Error('Primero cierra un turno para crear y comprobar su respaldo automático')
                from automatic_backup import after_shift
                result=after_shift(pos,closed[0]);return self.send(200,result)
            if path.startswith('/api/operations/'):
                from operation_journal import handle
                return self.send(200,handle(pos,uid,path.rsplit('/',1)[-1],data,write))
            if path=='/api/credit' and not write:return self.send(200,credit.read(pos,uid,data))
            if path=='/api/credit/payment' and write:return self.send(200,credit.payment(pos,uid,data))
            if write and path=='/api/settings':return self.send(200,branding.save_settings(pos,uid,data))
            if write and path=='/api/branding':return self.send(200,branding.save(pos,uid,data))
            if write and path=='/api/promotions/save':return self.send(200,promotions.save(pos,uid,data))
            if not write and path in ('/api/sales/history','/api/sales/history.csv','/api/sales/history.xlsx'):
                with pos.db() as db:
                    pos.require(db,uid,'reports.view')
                    result=analytics.history(db,data,'costs.view' in pos.permissions(db,uid))
                if path.endswith('.xlsx'):
                    from history_xlsx import export_history_xlsx
                    return self.send(200,lambda:export_history_xlsx(result),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',filename=f"historial-{result['from']}-{result['to']}-completo.xlsx")
                if path.endswith('.csv'):
                    return self.send(200,lambda:analytics.export_history(result,data.get('summary')=='1'),'text/csv; charset=utf-8',filename=f"ventas-{result['from']}-{result['to']}{'-resumen' if data.get('summary')=='1' else '-detalle'}.csv")
                return self.send(200,result)
            if not write and path=='/api/inventory/export':
                body,filename,mime=inventory_io.export_inventory(pos,uid,data.get('format','json'))
                return self.send(200,body,mime,filename=filename)
            if not write and path=='/api/backup/export':
                body,filename,mime=inventory_io.backup(pos,uid)
                return self.send(200,body,mime,filename=filename)
            file_operations={'/api/inventory/import/preview':inventory_io.preview,
                '/api/inventory/import/confirm':inventory_io.import_inventory,
                '/api/backup/preview':inventory_io.restore_preview,'/api/backup/restore':inventory_io.restore}
            if write and path in file_operations:
                result=file_operations[path](pos,uid,data)
                if path=='/api/backup/restore' and getattr(self.server,'owner_access',None):self.server.owner_access.stop()
                return self.send(200,result)
            if write and path=='/api/logout':
                with pos.db(True) as db:
                    if db.execute('SELECT 1 FROM cash_shifts WHERE user_id=? AND closed_at IS NULL',(uid,)).fetchone():
                        raise Error('Cuenta el efectivo y cierra tu turno antes de cerrar sesión.',409)
                    db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
                return self.send(200,{'ok':True},cookie=f'{cookie_name}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            operations = {'/api/shifts/open':pos.open_shift,'/api/shifts/close':pos.close_shift,
              '/api/cash':pos.cash_movement,'/api/sales':pos.sale,'/api/returns':pos.return_sale,
              '/api/inventory/receive':pos.receive,'/api/inventory/restock':pos.restock,'/api/inventory/adjust':pos.adjust,'/api/inventory/batch/edit':pos.edit_batch,
              '/api/products/save':pos.save_product,'/api/users/save':pos.save_user}
            if write and path in operations:
                if path=='/api/shifts/open':
                    integer(data.get('shift_number'), 'Turno', 1, 2)
                if path in ('/api/cash','/api/inventory/receive','/api/inventory/restock'):required(data,'request_key')
                kinds={'/api/sales':'sale','/api/cash':'cash','/api/inventory/restock':'restock','/api/inventory/receive':'receive'}
                if path in kinds:
                    from operation_journal import lookup
                    from core import fingerprint
                    with pos.db() as db:
                        other=db.execute('SELECT 1 FROM operation_intents WHERE user_id=? AND acknowledged=0 AND NOT(kind=? AND request_key=?)',(uid,kinds[path],data.get('request_key',''))).fetchone()
                        if other:raise Error('Comprueba la operación pendiente antes de iniciar otra',409)
                        intent=db.execute('SELECT body_json,shift_id FROM operation_intents WHERE kind=? AND user_id=? AND request_key=?',(kinds[path],uid,data.get('request_key',''))).fetchone()
                        if intent:
                            if fingerprint(json.loads(intent['body_json']))!=fingerprint(data):raise Error('La operación pendiente tiene otros datos',409)
                            if kinds[path] in ('sale','cash') and lookup(pos,db,uid,kinds[path],data['request_key'])['state']=='not_found':
                                current=db.execute('SELECT id FROM cash_shifts WHERE user_id=? AND closed_at IS NULL',(uid,)).fetchone()
                                if not current or current[0]!=intent['shift_id']:raise Error('El turno original ya no está abierto. Cancela la operación pendiente; no se trasladará a otro turno.',409)
                result=operations[path](uid,data)
                if path=='/api/shifts/close':
                    with pos.db() as db:
                        if 'costs.view' not in pos.permissions(db,uid):
                            for key in ('tax_cents','cost_cents','profit_cents','zero_cost_units'):result.pop(key,None)
                return self.send(200,result)
            result = self.mutate(pos,uid,path,data) if write else self.read(pos,uid,path,data)
            self.send(200,result)
        except Error as e:
            self.send(e.status,{'error':str(e)})
        except sqlite3.IntegrityError:
            self.send(409,{'error':'Conflicto de datos: revisa duplicados, referencias y campos obligatorios'})
        except sqlite3.OperationalError:
            self.send(503,{'error':'Base de datos ocupada o no disponible. Reintenta la misma operación.'})
        except (ValueError,TypeError,KeyError,AttributeError):
            self.send(400,{'error':'Datos de solicitud inválidos'})
        except Exception:
            logging.exception('Error interno')
            self.send(500,{'error':'Error interno; la operación no se confirmó'})

    def direction(self,pos,path,data,write):
        """Sesión independiente: la cookie del mostrador no abre Dirección."""
        cookie_name=f'direction_session_{self.server.server_port}'
        if write and path=='/direccion/api/login':
            token=pos.login(required(data,'username'),credential(data))
            uid=pos.session_user(token)
            try:
                with pos.db() as db:
                    pos.require(db,uid,'users.manage')
                    pos.require(db,uid,'reports.view')
            except Error:
                with pos.db(True) as db:
                    db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
                raise Error('Acceso exclusivo de dirección. Se requieren permisos de administrar usuarios y consultar informes.',403)
            return self.send(200,{'ok':True},cookie=f'{cookie_name}={token}; HttpOnly; SameSite=Strict; Path=/direccion; Max-Age=43200')
        cookies=SimpleCookie(self.headers.get('Cookie',''))
        token=cookies[cookie_name].value if cookie_name in cookies else ''
        uid=pos.session_user(token)
        if write and path=='/direccion/api/logout':
            with pos.db(True) as db:
                db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
            return self.send(200,{'ok':True},cookie=f'{cookie_name}=; HttpOnly; SameSite=Strict; Path=/direccion; Max-Age=0')
        with pos.db() as db:
            pos.require(db,uid,'users.manage')
            pos.require(db,uid,'reports.view')
            if write and path=='/direccion/api/settings':
                return self.send(200,branding.save_settings(pos,uid,data))
            if write and path=='/direccion/api/branding':
                return self.send(200,branding.save(pos,uid,data))
            if not write and path in ('/direccion/api/history','/direccion/api/history.csv','/direccion/api/history.xlsx','/direccion/api/metrics'):
                include_profit='costs.view' in pos.permissions(db,uid)
                result=analytics.metrics(db,data,include_profit) if path.endswith('/metrics') else analytics.history(db,data,include_profit)
                if path.endswith('.xlsx'):
                    from history_xlsx import export_history_xlsx
                    return self.send(200,export_history_xlsx(result),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',filename=f"historial-{result['from']}-{result['to']}-completo.xlsx")
                if path.endswith('.csv'):
                    return self.send(200,analytics.export_history(result,data.get('summary')=='1'),'text/csv; charset=utf-8',filename=f"ventas-{result['from']}-{result['to']}{'-resumen' if data.get('summary')=='1' else '-detalle'}.csv")
                return self.send(200,result)
            if write or path!='/direccion/api/summary':
                raise Error('Ruta inexistente',404)
            user=db.execute('SELECT display_name FROM users WHERE id=?',(uid,)).fetchone()
            # Agrupar por el día local del equipo, no por el día UTC del ticket.
            sales=db.execute("SELECT COUNT(*) tickets,COALESCE(SUM(total_cents),0) total FROM sales WHERE date(created_at,'localtime')=date('now','localtime')").fetchone()
            refunds=db.execute("SELECT COALESCE(SUM(total_cents),0) FROM returns WHERE date(created_at,'localtime')=date('now','localtime')").fetchone()[0]
            rows=[dict(r) for r in db.execute('''SELECT p.id,p.barcode,p.name,p.reorder_point,p.max_stock,p.price_cents,
                COALESCE(SUM(CASE WHEN b.expires_on IS NULL OR b.expires_on>? THEN b.quantity ELSE 0 END),0) stock
                FROM products p LEFT JOIN batches b ON b.product_id=p.id WHERE p.active=1 GROUP BY p.id ORDER BY p.name''',(dt.date.today().isoformat(),))]
            if 'costs.view' in pos.permissions(db,uid):
                import inventory_value
                values=inventory_value.by_product(db,dt.date.today().isoformat())
                for row in rows:
                    row['inventory_value_cents']=values[row['id']]
                    cost=db.execute('SELECT unit_cost_cents FROM batches WHERE product_id=? ORDER BY received_at DESC,id DESC LIMIT 1',(row['id'],)).fetchone()
                    row['purchase_cost_cents']=cost[0] if cost else None
            shifts=[]
            for shift in db.execute("SELECT s.*,u.display_name FROM cash_shifts s JOIN users u ON u.id=s.user_id WHERE s.closed_at IS NULL OR date(s.closed_at,'localtime')=date('now','localtime') ORDER BY s.id DESC"):
                report=pos.report(db,shift['id'])
                shifts.append({'id':shift['id'],'user':shift['display_name'],'closed_at':shift['closed_at'],
                    'sales_cents':report['net_sales_cents'],'expected_cents':report['expected_cents'],
                    'counted_cents':shift['counted_cents'],'difference_cents':report.get('difference_cents'),
                    'payments_by_method':{name:sum(report['sales_by_method'].get(m,0)+report['collections_by_method'].get(m,0)-report['refunds_by_method'].get(m,0) for m in methods) for name,methods in [('cash',('cash',)),('card',('debit','credit')),('transfer',('transfer',))]}})
                if 'costs.view' in pos.permissions(db,uid):shifts[-1].update(profit.shift(db,shift['id']))
            today=dt.date.today().isoformat()
            day_totals=analytics.history(db,{'from':today,'to':today},'costs.view' in pos.permissions(db,uid))['totals']
            suppliers=[dict(r) for r in db.execute('SELECT business_name,contact,phone,credit_days FROM suppliers WHERE active=1 ORDER BY business_name')]
            return self.send(200,{**day_totals,'user':user['display_name'],'day':dt.date.today().isoformat(),'updated_at':dt.datetime.now().astimezone().isoformat(timespec='seconds'),
                'sales_cents':day_totals['sales_cents'],'refunds_cents':day_totals['refunds_cents'],'net_cents':day_totals['net_cents'],'tickets':day_totals['tickets'],'products':rows,'shifts':shifts,'suppliers':suppliers})

    def read(self,pos,uid,path,data):
        with pos.db() as db:
            permissions = pos.permissions(db,uid)
            if path=='/api/me':
                user = dict(db.execute('SELECT id,username,display_name FROM users WHERE id=?',(uid,)).fetchone())
                shift = db.execute('SELECT id,register_id,opened_at FROM cash_shifts WHERE user_id=? AND closed_at IS NULL',(uid,)).fetchone()
                if shift:
                    shift = dict(shift)
                    opened = db.execute("SELECT details FROM audit_log WHERE action='shift.open' AND entity_id=? ORDER BY id DESC LIMIT 1",(str(shift['id']),)).fetchone()
                    shift['shift_number'] = json.loads(opened['details']).get('shift_number') if opened else None
                return {'user':user,'permissions':sorted(permissions),'permission_labels':PERMISSIONS,'shift':dict(shift) if shift else None}
            if path=='/api/inventory/availability':
                ids = [int(x) for x in data.get('ids','').split(',') if x]
                if not ids or len(ids)>500:
                    raise Error('Selecciona entre 1 y 500 productos')
                marks=','.join('?' for _ in ids)
                rows=[dict(r) for r in db.execute(f'''SELECT p.id,p.price_cents,COALESCE(SUM(CASE WHEN b.expires_on IS NULL OR b.expires_on>? THEN b.quantity ELSE 0 END),0) stock
                    FROM products p LEFT JOIN batches b ON b.product_id=p.id WHERE p.active=1 AND p.id IN ({marks}) GROUP BY p.id''',(dt.date.today().isoformat(),*ids))]
                active=promotions.active(db)
                for p in rows:promotions.decorate(p,active.get(p['id']))
                return rows
            if path=='/api/promotions':
                return [dict(r,is_current=promotions.is_current(r)) for r in db.execute('SELECT pr.*,p.name product_name,p.barcode,p.price_cents regular_price FROM promotions pr JOIN products p ON p.id=pr.product_id WHERE p.active=1 ORDER BY pr.active DESC,pr.ends_on DESC')]
            if path=='/api/categories':
                return [dict(r) for r in db.execute('SELECT * FROM categories ORDER BY name')]
            if path=='/api/inventory/overview':
                # Consulta operativa para cualquier usuario autenticado, sin costos ni ventas.
                rows=[dict(r) for r in db.execute('''SELECT p.id,p.barcode,p.name,p.reorder_point,
                    COALESCE(SUM(CASE WHEN b.expires_on IS NULL OR b.expires_on>? THEN b.quantity ELSE 0 END),0) stock
                    FROM products p LEFT JOIN batches b ON b.product_id=p.id WHERE p.active=1 GROUP BY p.id ORDER BY p.name''',(dt.date.today().isoformat(),))]
                import inventory_value
                result={'products':rows}
                if 'costs.view' in permissions:
                    result['inventory_value_cents']=sum(inventory_value.by_product(db,dt.date.today().isoformat()).values())
                return result
            if path=='/api/products':
                q = data.get('q','')[:100]
                offset = max(0,int(data.get('offset','0')))
                from catalog_search import search
                result=search(db,q,offset,'costs.view' in permissions)
                active=promotions.active(db)
                for p in result:promotions.decorate(p,active.get(p['id']))
                if 'costs.view' in permissions:
                    for p in result:
                        net = p['price_cents'] - rounded(p['price_cents']*p['tax_bps'],10000+p['tax_bps'])
                        p['unit_margin_cents'] = net-p['cost_cents']
                        p['margin_bps'] = rounded((net-p['cost_cents'])*10000,net) if net else None
                return result
            if path=='/api/customers':
                q = '%'+data.get('q','')[:100]+'%'
                return [dict(r) for r in db.execute('SELECT * FROM customers WHERE active=1 AND (name LIKE ? OR phone LIKE ?) ORDER BY name,id',(q,q))]
            if path=='/api/customers/history':
                pos.require(db,uid,'reports.view')
                return [dict(r) for r in db.execute('SELECT id,total_cents,status,created_at FROM sales WHERE customer_id=? ORDER BY id DESC LIMIT 100',(int(data['id']),))]
            if path=='/api/suppliers':
                return [dict(r) for r in db.execute('SELECT * FROM suppliers WHERE active=1 ORDER BY business_name LIMIT 200')]
            if path=='/api/users':
                pos.require(db,uid,'users.manage')
                return [dict(r,permissions=sorted(pos.permissions(db,r['id']))) for r in db.execute('SELECT id,username,display_name,active FROM users ORDER BY username')]
            if path=='/api/shifts/report':
                sid = int(data['id'])
                row = db.execute('SELECT * FROM cash_shifts WHERE id=?',(sid,)).fetchone()
                if not row:
                    raise Error('Turno inexistente',404)
                if row['closed_at'] and row['user_id']==uid:
                    result=pos.report(db,sid)
                    if 'costs.view' in permissions:
                        if 'profit_cents' not in result:result.update(profit.shift(db,sid))
                    else:
                        for key in ('tax_cents','cost_cents','profit_cents','zero_cost_units'):result.pop(key,None)
                    return result
                pos.require(db,uid,'reports.view')
                result=pos.report(db,sid) if row['closed_at'] else dict(pos.report(db,sid),type='X')
                if 'costs.view' in permissions:
                    if 'profit_cents' not in result:result.update(profit.shift(db,sid))
                else:
                    for key in ('tax_cents','cost_cents','profit_cents','zero_cost_units'):result.pop(key,None)
                return result
            if path=='/api/reports/general':
                pos.require(db,uid,'reports.view')
                first,last = int(data.get('from_id','1')),int(data.get('to_id','100'))
                if first<1 or last<first or last-first>365:
                    raise Error('Selecciona un rango de hasta 366 turnos')
                result=[]
                for shift in db.execute('SELECT * FROM cash_shifts WHERE id BETWEEN ? AND ? ORDER BY id',(first,last)):
                    report=pos.report(db,shift['id'])
                    result.append({'id':shift['id'],'register_id':shift['register_id'],'opened_at':shift['opened_at'],
                      'closed_at':shift['closed_at'],'net_sales_cents':report['net_sales_cents'],
                      'expected_cents':report['expected_cents'],'counted_cents':shift['counted_cents'],
                      'difference_cents':report.get('difference_cents')})
                return {'shifts':result,'net_sales_cents':sum(r['net_sales_cents'] for r in result)}
            if path=='/api/tickets':
                import ticket_history
                return ticket_history.listing(db,uid,permissions,data)
            if path=='/api/ticket':
                ticket = pos.ticket(db,int(data['id']))
                if ticket['user_id']!=uid and not permissions.intersection({'reports.view','sales.return','sales.void'}):
                    raise Error('Ticket ajeno',403)
                import ticket_history
                return ticket_history.describe(db,ticket)
            if path=='/api/inventory/batches':
                columns = 'b.id,b.product_id,b.lot_number,b.expires_on,b.quantity,b.supplier_id'
                if 'costs.view' in permissions:
                    columns += ',b.unit_cost_cents'
                return [dict(r) for r in db.execute(f'SELECT {columns} FROM batches b WHERE product_id=? ORDER BY expires_on,id LIMIT 200',(int(data['product_id']),))]
            if path=='/api/inventory/kardex':
                return [dict(r) for r in db.execute('SELECT m.*,b.lot_number,u.display_name FROM inventory_movements m JOIN batches b ON b.id=m.batch_id JOIN users u ON u.id=m.user_id WHERE b.product_id=? ORDER BY m.id DESC LIMIT 200',(int(data['product_id']),))]
            if path=='/api/inventory/alerts':
                today = dt.date.today()
                return [dict(r) for r in db.execute('SELECT b.id,p.name,b.lot_number,b.expires_on,b.quantity FROM batches b JOIN products p ON p.id=b.product_id WHERE b.quantity>0 AND b.expires_on<=? ORDER BY b.expires_on LIMIT 200',((today+dt.timedelta(days=90)).isoformat(),))]
            if path=='/api/inventory/undated':
                return [dict(r) for r in db.execute('SELECT b.id,p.name,b.lot_number,b.quantity FROM batches b JOIN products p ON p.id=b.product_id WHERE b.quantity>0 AND b.expires_on IS NULL ORDER BY p.name LIMIT 200')]
            raise Error('Ruta inexistente',404)

    def mutate(self,pos,uid,path,data):
        with pos.db(True) as db:
            if path=='/api/products/deactivate':
                pos.require(db,uid,'products.delete')
                pid = integer(data.get('id'),'Producto',1)
                if db.execute('UPDATE products SET active=0 WHERE id=?',(pid,)).rowcount!=1:
                    raise Error('Producto inexistente',404)
                pos.audit(db,uid,'product.deactivate',pid,{})
                return {'ok':True}
            if path=='/api/customers/save':
                pos.require(db,uid,'customers.manage')
                cid = data.get('id')
                values = (required(data,'name'),str(data.get('phone',''))[:50],integer(data.get('discount_bps',0),'Descuento',0,10000))
                if cid:
                    if db.execute('UPDATE customers SET name=?,phone=?,discount_bps=? WHERE id=?',(*values,cid)).rowcount!=1:
                        raise Error('Cliente inexistente',404)
                else:
                    cid = db.execute('INSERT INTO customers(name,phone,discount_bps) VALUES (?,?,?)',values).lastrowid
                pos.audit(db,uid,'customer.save',cid,{'discount_bps':values[2]})
                return {'id':cid}
            if path=='/api/suppliers/save':
                pos.require(db,uid,'suppliers.manage')
                sid = data.get('id')
                values = (required(data,'business_name'),str(data.get('contact',''))[:100],str(data.get('phone',''))[:50],integer(data.get('credit_days',0),'Días de crédito',0,3650))
                if sid:
                    if db.execute('UPDATE suppliers SET business_name=?,contact=?,phone=?,credit_days=? WHERE id=?',(*values,sid)).rowcount!=1:
                        raise Error('Proveedor inexistente',404)
                else:
                    sid = db.execute('INSERT INTO suppliers(business_name,contact,phone,credit_days) VALUES (?,?,?,?)',values).lastrowid
                pos.audit(db,uid,'supplier.save',sid,{})
                return {'id':sid}
            raise Error('Ruta inexistente',404)

def main():
    parser = argparse.ArgumentParser(description='POS local para farmacia')
    parser.add_argument('command',choices=['init','serve','backup'])
    parser.add_argument('--db',default=str(ROOT/'data'/'pos.sqlite3'))
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--username',default='admin')
    parser.add_argument('--destination',help='Ruta nueva de copia SQLite')
    args = parser.parse_args()
    pos = POS(args.db)
    if args.command=='init':
        pos.initialize(args.username,getpass.getpass('Contraseña inicial (mínimo 8 caracteres): '))
        print('Base inicializada. Ejecuta: python app.py serve')
    elif args.command=='backup':
        if not args.destination or os.path.exists(args.destination):
            parser.error('--destination debe ser una ruta nueva')
        with contextlib.closing(sqlite3.connect(pos.path)) as source, contextlib.closing(sqlite3.connect(args.destination)) as destination:
            source.backup(destination)
            if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise RuntimeError('Copia no verificada')
        print('Copia verificada:',args.destination)
    else:
        with pos.db() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='users'").fetchone():
                parser.error('Inicializa primero: python app.py init')
        server = ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
        server.pos = pos
        print(f'Abre http://127.0.0.1:{args.port} · Ctrl+C para detener')
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()

if __name__=='__main__':
    main()
