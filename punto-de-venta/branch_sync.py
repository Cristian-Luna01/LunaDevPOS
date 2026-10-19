"""Réplica de consulta: nunca modifica inventario, caja ni credenciales del POS."""
from contextlib import contextmanager, closing
import datetime as dt
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.parse import urlsplit
import analytics
import direction_replica
from local_secret import protect, reveal
from core import Error


@contextmanager
def database(path):
    with closing(sqlite3.connect(path)) as db:
        with db:
            yield db


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def retained_history(report, day, today=None):
    cutoff=(today or dt.date.today())-dt.timedelta(days=29)
    if day>=cutoff.isoformat():
        return report
    movements=report['cash_movements']
    return {'from':report['from'],'to':report['to'],'totals':report['totals'],'products':report['products'],
            'cash_totals':report.get('cash_totals',{'in':sum(m['amount_cents'] for m in movements if m['direction']=='in'),
                                                'out':sum(m['amount_cents'] for m in movements if m['direction']=='out')}),
            'events':[],'cash_movements':[],'card_fees':[],'inventory_adjustments':[],'inventory_adjustment_count':len(report.get('inventory_adjustments',[])),'inventory_adjustments_available':report.get('inventory_adjustments_available',False),'history_storage':'summary'}


def service_url(value):
    if not isinstance(value, str):
        raise Error('Introduce el enlace central del dueño')
    p = urlsplit(value.strip())
    if p.scheme != 'https' or not p.hostname or not p.hostname.endswith('.workers.dev') or p.username or p.password or p.port or p.query or p.fragment or p.path not in ('', '/'):
        raise Error('Usa el enlace HTTPS workers.dev de la página central, sin rutas ni códigos')
    return 'https://' + p.hostname


def snapshot(pos):
    today = dt.date.today()
    with pos.request_lock, pos.db() as db:
        report = analytics.history(db, {'from': (today-dt.timedelta(days=30)).isoformat(), 'to': today.isoformat()}, True)
        direction=direction_replica.current(pos,db)
        # Reutiliza el mismo catálogo ya calculado, conservando el formato público.
        fields=('id','barcode','name','price_cents','cost_cents','reorder_point','stock','physical_stock')
        products=[{key:p[key] for key in fields} for p in sorted(direction['products'],key=lambda p:p['id'])]
    return {'version': 2, 'currency': 'MXN', 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'today': today.isoformat(), 'daily': report['daily'], 'products': products,'direction':direction}


class BranchSync:
    def __init__(self, pos):
        self.pos = pos
        self.path = Path(pos.path).parent / 'conexion-sucursal.sqlite3'
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.closed = threading.Event()
        self.thread = None
        self.cached = None
        self.signature = None
        self.message = 'Sin vincular a una cuenta del dueño.'
        with database(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS link(id INTEGER PRIMARY KEY CHECK(id=1),url TEXT NOT NULL,token TEXT NOT NULL,name TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0,last_ok TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS installation(id INTEGER PRIMARY KEY CHECK(id=1),identity TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO installation VALUES(1,?)',(uuid.uuid4().hex,))
            self.identity=db.execute('SELECT identity FROM installation').fetchone()[0]
            db.execute('CREATE TABLE IF NOT EXISTS sent_days(day TEXT PRIMARY KEY,fingerprint TEXT NOT NULL)')

    def status(self):
        with self.lock, database(self.path) as db:
            r = db.execute('SELECT url,name,last_ok FROM link WHERE id=1').fetchone()
        return {'configured': bool(r), 'url': r[0] if r else '', 'name': r[1] if r else '', 'last_ok': r[2] if r else None, 'message': self.message}

    def configure(self, data):
        url = service_url(data.get('url'))
        token = data.get('token', '')
        name = data.get('name', '').strip()
        if not isinstance(token, str) or len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
            raise Error('Pega la clave de sucursal creada en la página del dueño')
        if not name or len(name) > 100:
            raise Error('Indica un nombre de local de hasta 100 caracteres')
        with self.lock, database(self.path) as db:
            old = db.execute('SELECT url,token FROM link WHERE id=1').fetchone()
            if old and (old[0] != url or reveal(old[1]) != token):
                raise Error('Desvincula primero esta computadora antes de cambiar de sucursal')
            db.execute('INSERT INTO link(id,url,token,name) VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name', (url, protect(token), name))
        self.message = 'Vinculación guardada. Comprobando conexión…'
        self.wake.set()
        return self.status()

    def disconnect(self):
        with self.lock, database(self.path) as db:
            db.execute('DELETE FROM link')
            db.execute('DELETE FROM sent_days')
        self.message = 'Desvinculado. Las ventas y el inventario permanecen en esta computadora.'
        return self.status()

    def once(self, sender=None):
        # Bloqueo independiente: la red nunca retiene request_lock del mostrador.
        with self.lock, database(self.path) as db:
            row = db.execute('SELECT url,token,name,revision FROM link WHERE id=1').fetchone()
            if not row:
                return
            revision = row[3]+1
            db.execute('UPDATE link SET revision=? WHERE id=1', (revision,))
        signature=[dt.date.today().isoformat()]
        for path in (Path(self.pos.path),Path(self.pos.path+'-wal')):
            try:
                stat=path.stat();signature.append((stat.st_mtime_ns,stat.st_size))
            except FileNotFoundError:signature.append(None)
        if self.cached is None or signature!=self.signature:
            self.cached=snapshot(self.pos);self.signature=signature
        payload = dict(self.cached)
        # El panel completo ya contiene el catálogo: no duplicarlo en el envío.
        payload.pop('products',None)
        payload['generated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        payload.update(revision=revision, name=row[2],instance_id=self.identity)
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
        if len(body) > 900_000:
            raise Error('El catálogo supera el tamaño admitido por esta primera versión de conexión. No se envió un catálogo incompleto.')
        if sender:
            result = sender(row[0], reveal(row[1]), body)
        else:
            request = Request(row[0]+'/api/snapshot', data=body, headers={'Content-Type':'application/json', 'Authorization':'Bearer '+reveal(row[1]),'User-Agent':'NuvariaPOS/1.0 (Windows; branch reporting)'}, method='POST')
            with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=10) as response:
                result = json.loads(response.read(4096))
        if result.get('revision') != revision or result.get('ok') is not True:
            raise Error('La página central no confirmó esta actualización')
        with self.lock, database(self.path) as db:
            db.execute('UPDATE link SET last_ok=? WHERE id=1 AND url=? AND token=?', (payload['generated_at'],row[0],row[1]))
        self.message = 'Conectado. Actualizando el historial completo…'
        remaining=self.sync_days(row,sender)
        self.message = f'Conectado. Historial en proceso: faltan {remaining} fechas.' if remaining else 'Conectado. Panel e historial enviados a la página del dueño.'

    def sync_days(self,link,sender=None):
        days=sorted(self.cached['direction']['history_days'],reverse=True)
        with database(self.path) as store:sent=dict(store.execute('SELECT day,fingerprint FROM sent_days'))
        pending=[day for day in days if sent.get(day)!=self.cached['direction']['history_fingerprints'][day]]
        # El archivo histórico se envía por lotes cortos; no retrasa las siguientes
        # actualizaciones del mostrador cuando el negocio ya tiene años de ventas.
        for day in pending[:8]:
            expected=self.cached['direction']['history_fingerprints'][day]
            if sent.get(day)==expected:continue
            with self.pos.request_lock,self.pos.db() as db:
                fingerprint=direction_replica.day_fingerprint(db,day)
                report=analytics.history(db,{'from':day,'to':day},True)
                report['inventory_adjustments']=direction_replica.product_adjustments(db,day)
                report['inventory_adjustments_available']=True
                report=retained_history(report,day)
            with self.lock,database(self.path) as store:
                active=store.execute('SELECT url,token,revision FROM link WHERE id=1').fetchone()
                if not active or active[:2]!=link[:2]:return len(pending)
                revision=active[2]+1;store.execute('UPDATE link SET revision=? WHERE id=1',(revision,))
            payload={'version':2,'instance_id':self.identity,'revision':revision,'day':day,'fingerprint':fingerprint,'report':report}
            body=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
            if len(body)>900_000:raise Error('El detalle de un día supera el tamaño de envío. No se envió información parcial.')
            if sender:
                result=sender(link[0],reveal(link[1]),body)
            else:
                request=Request(link[0]+'/api/history-day',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+reveal(link[1]),'User-Agent':'NuvariaPOS/1.0 (Windows; branch reporting)'},method='POST')
                with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=10) as response:result=json.loads(response.read(4096))
            if result.get('ok') is not True or result.get('revision')!=revision:raise Error('El historial no confirmó la actualización')
            with self.lock,database(self.path) as store:
                active=store.execute('SELECT url,token FROM link WHERE id=1').fetchone()
                if active!=link[:2]:return len(pending)
                store.execute('INSERT INTO sent_days VALUES(?,?) ON CONFLICT(day) DO UPDATE SET fingerprint=excluded.fingerprint',(day,fingerprint))
        return max(0,len(pending)-8)

    def start(self):
        if self.thread:
            return
        def run():
            while not self.closed.is_set():
                try:
                    self.once()
                except Exception:
                    self.message = 'No se pudo sincronizar. El mostrador sigue funcionando; se reintentará automáticamente.'
                self.wake.wait(15)
                self.wake.clear()
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        self.closed.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=12)
            if not self.thread.is_alive():
                try:self.once()
                except Exception:pass
