"""Regresiones: permisos, red lenta, cortes y reintentos de movimientos."""
import json
import socket
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from app import Handler
from core import Error
import test_pos


class ImprovementsTest(unittest.TestCase):
    setUp = test_pos.POSTest.setUp
    tearDown = test_pos.POSTest.tearDown
    receive = test_pos.POSTest.receive
    body = test_pos.POSTest.body

    def test_closed_report_preserves_supplier_and_department_names(self):
        self.pos.cash_movement(1,dict(direction='out',category='supplier',amount_cents=100,
                                     supplier_id=1,invoice_ref='A',concept='Pago'))
        original=self.pos.close_shift(1,dict(shift_id=self.sid,counted_cents=9900))
        original.pop('automatic_backup')
        with self.pos.db(True) as db:
            db.execute("UPDATE suppliers SET business_name='Nuevo nombre' WHERE id=1")
            db.execute("UPDATE categories SET name='Otro departamento' WHERE id=1")
        with self.pos.db() as db:
            self.assertEqual(self.pos.report(db,self.sid),original)

    def test_movement_retries_do_not_duplicate_and_conflicts_rollback(self):
        cash=dict(direction='in',category='change',amount_cents=100,concept='Cambio',request_key='cash-retry')
        first=self.pos.cash_movement(1,cash)
        self.assertEqual(self.pos.cash_movement(1,cash),first)
        with self.assertRaises(Error) as denied:
            self.pos.cash_movement(1,dict(cash,amount_cents=200))
        self.assertEqual(denied.exception.status,409)
        receipt=dict(product_id=self.pid,quantity=3,unit_cost_cents=500,reason='Factura',request_key='receipt-retry')
        first=self.pos.receive(1,receipt)
        self.assertEqual(self.pos.receive(1,receipt),first)
        with self.assertRaises(Error):self.pos.receive(1,dict(receipt,quantity=4))
        with self.pos.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM cash_movements').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0],23)

    def test_failed_movement_can_be_corrected_with_same_key(self):
        cash=dict(direction='in',category='change',amount_cents=-1,concept='Cambio',request_key='rollback')
        with self.assertRaises(Error):self.pos.cash_movement(1,cash)
        cash['amount_cents']=100
        first=self.pos.cash_movement(1,cash)
        self.assertEqual(self.pos.cash_movement(1,cash),first)

    def test_global_history_denies_cashier_and_keeps_own_tickets(self):
        ticket=self.pos.sale(1,self.body())
        uid=self.pos.save_user(1,dict(username='cashier',display_name='Caja',secret='test-password',permissions=['sell']))['id']
        token=self.pos.login('cashier','test-password')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.pos=self.pos
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            cookie=f'pos_session_{server.server_port}={token}'
            for suffix in ('','.csv','.xlsx'):
                with self.assertRaises(HTTPError) as denied:
                    urlopen(Request(base+'/api/sales/history'+suffix,headers={'Cookie':cookie}),timeout=3)
                self.assertEqual(denied.exception.code,403)
            with urlopen(Request(base+'/api/tickets',headers={'Cookie':cookie}),timeout=3) as response:
                self.assertEqual(json.load(response)['items'],[])
            admin=f'pos_session_{server.server_port}='+self.pos.login('admin','test-only-password')
            with urlopen(Request(base+'/api/sales/history',headers={'Cookie':admin}),timeout=3) as response:
                self.assertEqual(json.load(response)['events'][0]['ticket_id'],ticket['id'])
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_partial_body_does_not_block_other_requests(self):
        started=threading.Event()
        class ObservedHandler(Handler):
            def read_request(self,write):
                if write:started.set()
                return super().read_request(write)
        server=ThreadingHTTPServer(('127.0.0.1',0),ObservedHandler);server.pos=self.pos
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        slow=socket.create_connection(('127.0.0.1',server.server_port),timeout=3)
        try:
            port=server.server_port
            slow.sendall((f'POST /api/login HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\nX-POS-Request: 1\r\nContent-Length: 100\r\n\r\n{{').encode())
            self.assertTrue(started.wait(2))
            with urlopen(f'http://127.0.0.1:{port}/business-settings',timeout=2) as response:
                self.assertEqual(response.status,200)
        finally:
            slow.close();server.shutdown();server.server_close();thread.join()

    def test_response_is_sent_after_releasing_restore_lock(self):
        owner=[]
        class CheckedHandler(Handler):
            def send(self,*args,**kwargs):
                if not getattr(self,'_defer_response',False):owner.append(self.server.pos.request_lock._is_owned())
                return super().send(*args,**kwargs)
        server=ThreadingHTTPServer(('127.0.0.1',0),CheckedHandler);server.pos=self.pos
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}/business-settings',timeout=2) as response:response.read()
            self.assertEqual(owner,[False])
        finally:
            server.shutdown();server.server_close();thread.join()
