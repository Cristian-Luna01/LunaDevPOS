"""Pruebas adversarias aisladas; nunca usan cuentas ni datos del negocio."""
import json,socket,threading,time,unittest
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request,urlopen
import test_customer_http as fixture
from core import Error,password_hash
from http_limits import ThreadingHTTPServer
from billing_service import verify_xml

class SecurityControls(unittest.TestCase):
    setUp=fixture.CustomerHTTPTest.setUp
    tearDown=fixture.CustomerHTTPTest.tearDown
    request=fixture.CustomerHTTPTest.request
    receive=fixture.CustomerHTTPTest.receive
    def test_authentication_and_admin_routes_reject_anonymous(self):
        self.cookie=''
        for path in ['/api/me','/api/users','/api/backup/export','/api/sales/history','/direccion/api/summary']:
            with self.assertRaises(HTTPError) as e:self.request(path)
            self.assertIn(e.exception.code,(401,403));e.exception.close()
    def test_logout_revokes_copied_session(self):
        cookie=self.cookie
        self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':10000})
        with self.request('/api/logout',{}) as r:self.assertEqual(r.status,200)
        self.cookie=cookie
        with self.assertRaises(HTTPError) as e:self.request('/api/me')
        self.assertEqual(e.exception.code,401);e.exception.close()
    def test_expired_session_rejected(self):
        with self.pos.db(True) as db:db.execute('UPDATE sessions SET expires_at=0')
        with self.assertRaises(HTTPError) as e:self.request('/api/me')
        self.assertEqual(e.exception.code,401);e.exception.close()
    def test_password_whitespace_not_silently_changed(self):
        with self.pos.db(True) as db:db.execute('UPDATE users SET password_hash=? WHERE id=1',(password_hash(' space-password '),))
        with self.request('/api/login',{'username':'admin','secret':' space-password '}) as r:self.assertEqual(r.status,200)
        with self.assertRaises(HTTPError) as e:self.request('/api/login',{'username':'admin','secret':'space-password'})
        self.assertEqual(e.exception.code,401);e.exception.close()
    def test_injection_queries_do_not_execute_sql(self):
        for payload in ["' OR 1=1 --", "'; DROP TABLE users;--",'<script>alert(1)</script>','../../schema.sql','\x00']:
            with self.request('/api/products?q='+quote(payload,safe='')) as r:self.assertIsInstance(json.load(r),list)
        with self.pos.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],1)
    def test_post_without_csrf_header_is_rejected(self):
        request=Request(self.base+'/api/cash',b'{}',headers={'Cookie':self.cookie,'Content-Type':'application/json'})
        with self.assertRaises(HTTPError) as e:urlopen(request,timeout=3)
        self.assertEqual(e.exception.code,403);e.exception.close()
    def test_path_traversal_cannot_read_files(self):
        for path in ['/../schema.sql','/%2e%2e/schema.sql','/data/pos.sqlite3','/.env']:
            with self.assertRaises(HTTPError) as e:self.request(path)
            self.assertIn(e.exception.code,(401,403,404));e.exception.close()
    def test_utf16_xml_entity_is_rejected_before_processing(self):
        raw='<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY e "malicious">]><x>&e;</x>'.encode('utf-16')
        with self.assertRaises(Error):verify_xml(raw,{}, {})

class ConnectionCapacity(unittest.TestCase):
    def test_capacity_rejects_excess_then_recovers(self):
        from http.server import BaseHTTPRequestHandler
        entered=threading.Event();release=threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                entered.set();release.wait(3)
                self.send_response(200);self.end_headers();self.wfile.write(b'ok')
            def log_message(self,*args):pass
        class Server(ThreadingHTTPServer):max_connections=1
        server=Server(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        sock=socket.create_connection(server.server_address,timeout=2)
        try:
            sock.sendall(b'GET / HTTP/1.0\r\n\r\n');self.assertTrue(entered.wait(2))
            with socket.create_connection(server.server_address,timeout=2) as second:
                second.sendall(b'GET / HTTP/1.0\r\n\r\n');self.assertIn(b'503',second.recv(200))
            release.set();self.assertIn(b'200',sock.recv(200));sock.close()
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                if server.connection_slots.acquire(False):server.connection_slots.release();break
                time.sleep(.01)
            with urlopen('http://127.0.0.1:'+str(server.server_port),timeout=3) as r:self.assertEqual(r.read(),b'ok')
        finally:release.set();sock.close();server.shutdown();server.server_close();thread.join()
