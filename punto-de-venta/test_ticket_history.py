import datetime as dt
import json
import unittest
from urllib.error import HTTPError
import test_customer_http as fixture


class TicketHistoryTest(unittest.TestCase):
    setUp = fixture.CustomerHTTPTest.setUp
    tearDown = fixture.CustomerHTTPTest.tearDown
    receive = fixture.CustomerHTTPTest.receive
    request = fixture.CustomerHTTPTest.request

    def call(self, path, data=None):
        with self.request(path, data) as response:
            return json.load(response)

    def sale(self, key, quantity=1, **extra):
        return self.pos.sale(1, {'request_key': key,
            'items': [{'product_id': self.pid, 'quantity': quantity}],
            'payments': [{'method': 'cash', 'amount_cents': quantity*1160, 'tendered_cents': 5000}], **extra})

    def test_ui_script_is_served(self):
        with self.request('/tickets-ui.js') as response:
            self.assertEqual(response.status,200)
            self.assertIn(b'ticketHistoryDialog',response.read())

    def test_whole_purchases_names_received_change_and_historical_prices(self):
        first = self.sale('three', 3)
        second = self.sale('two', 2)
        rows = self.call('/api/tickets')['items']
        self.assertEqual([r['id'] for r in rows], [second['id'], first['id']])
        self.assertEqual([r['line_count'] for r in rows], [1, 1])
        with self.pos.db(True) as db:
            db.execute("UPDATE products SET name='Nuevo nombre',price_cents=9999 WHERE id=?", (self.pid,))
        detail = self.call('/api/ticket?id='+str(first['id']))
        self.assertEqual(detail['items'][0]['product_name'], 'Producto')
        self.assertEqual(detail['items'][0]['quantity'], 3)
        self.assertEqual(detail['total_cents'], 3480)
        self.assertEqual(detail['payments'][0]['tendered_cents'], 5000)
        self.assertEqual(detail['change_cents'], 1520)
        self.assertTrue(detail['seller_name'])

    def test_dates_and_bad_ranges(self):
        old = self.sale('old')
        recent = self.sale('today')
        yesterday = (dt.date.today()-dt.timedelta(days=1)).isoformat()
        with self.pos.db(True) as db:
            value=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=1)).isoformat()
            db.execute('UPDATE sales SET created_at=? WHERE id=?', (value, old['id']))
        self.assertEqual([r['id'] for r in self.call('/api/tickets')['items']], [recent['id']])
        self.assertEqual([r['id'] for r in self.call('/api/tickets?from='+yesterday+'&to='+yesterday)['items']], [old['id']])
        for q in ['from=bad','from=2026-02-30','from=2020-01-01&to=2025-01-01','from=1999-01-01','before=abc']:
            with self.assertRaises(HTTPError) as error:
                self.call('/api/tickets?'+q)
            self.assertEqual(error.exception.code, 400)

    def test_keyset_pagination_does_not_repeat_when_new_ticket_arrives(self):
        with self.pos.db(True) as db:
            for i in range(55):
                db.execute('INSERT INTO sales(request_key,request_hash,shift_id,user_id,total_cents,tax_cents,discount_cents) VALUES(?,?,?,1,0,0,0)', ('page'+str(i), 'qa', self.sid))
        first=self.call('/api/tickets')
        self.assertEqual(len(first['items']), 50)
        self.sale('new-during-query')
        second=self.call('/api/tickets?before='+str(first['next_before']))
        ids=[r['id'] for r in first['items']+second['items']]
        self.assertEqual(len(ids), 55)
        self.assertEqual(len(set(ids)), 55)
        self.assertIsNone(second['next_before'])

    def test_own_sales_scope_matches_existing_ticket_permission(self):
        other = self.sale('admin-sale')
        uid=self.pos.save_user(1, {'username':'cashier','display_name':'Cajero QA','secret':'test-password','permissions':['sell']})['id']
        with self.request('/api/login', {'username':'cashier','secret':'test-password'}) as r:
            self.cookie=r.headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.call('/api/tickets')['items'], [])
        with self.assertRaises(HTTPError) as error:
            self.call('/api/ticket?id='+str(other['id']))
        self.assertEqual(error.exception.code, 403)
        with self.assertRaises(HTTPError):
            self.call('/api/tickets?before='+str(other['id']))
        self.pos.open_shift(uid, {'register_id':'B','opening_cents':0})
        own=self.pos.sale(uid, {'request_key':'own','items':[{'product_id':self.pid,'quantity':1}], 'payments':[{'method':'cash','amount_cents':1160}]})
        self.assertEqual([r['id'] for r in self.call('/api/tickets')['items']], [own['id']])

    def test_credit_zero_total_and_returned_tickets_are_not_hidden(self):
        credit=self.pos.sale(1, {'request_key':'credit','customer_id':1,'on_account':True,
            'items':[{'product_id':self.pid,'quantity':1}], 'payments':[]})
        with self.pos.db(True) as db:
            db.execute('UPDATE customers SET discount_bps=10000 WHERE id=1')
        free=self.pos.sale(1, {'request_key':'free','customer_id':1,'items':[{'product_id':self.pid,'quantity':1}], 'payments':[]})
        paid=self.sale('paid')
        self.pos.return_sale(1, {'request_key':'void','sale_id':paid['id'],'kind':'void','reason':'Prueba'})
        rows={r['id']:r for r in self.call('/api/tickets')['items']}
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[credit['id']]['on_account'])
        self.assertEqual(rows[free['id']]['total_cents'], 0)
        self.assertEqual(rows[paid['id']]['status'], 'voided')
