import base64
import hashlib
import json
import unittest
from urllib.error import HTTPError

from branch_sync import BranchSync, database
from core import fingerprint
import inventory_io
import test_customer_http


class PrivacyTest(unittest.TestCase):
    setUp = test_customer_http.CustomerHTTPTest.setUp
    tearDown = test_customer_http.CustomerHTTPTest.tearDown
    receive = test_customer_http.CustomerHTTPTest.receive
    request = test_customer_http.CustomerHTTPTest.request

    def test_notice_authentication_and_backup_compatibility(self):
        with self.request('/api/privacy-notice') as response:
            self.assertEqual(json.load(response)['full_notice'], '')
        data = dict(responsible='Comercio de prueba', address='Domicilio de prueba',
                    purposes='Registro de descuentos', contact='privacidad@example.test',
                    full_notice='Aviso de prueba\nSegunda línea.')
        with self.request('/api/privacy-notice', data) as response:
            self.assertTrue(json.load(response)['ok'])
        with self.request('/api/privacy-notice') as response:
            self.assertEqual(json.load(response), data)
        self.cookie = ''
        with self.assertRaises(HTTPError) as denied:
            self.request('/api/privacy-notice')
        self.assertEqual(denied.exception.code, 401)
        denied.exception.close()
        raw, _, _ = inventory_io.backup(self.pos, 1)
        saved = inventory_io.read_backup({'file_base64': base64.b64encode(raw).decode()})
        self.assertEqual(saved['tables']['privacy_notice'][0], {'id': 1, **data})
        saved.pop('sha256', None)
        saved['tables'].pop('privacy_notice')
        saved['version'] = 11
        saved['sha256'] = fingerprint(saved)
        encoded = base64.b64encode(json.dumps(saved).encode()).decode()
        self.assertEqual(inventory_io.read_backup({'file_base64': encoded})['tables']['privacy_notice'], [])

    def test_central_minimization_and_old_pending_payload(self):
        with self.pos.db(True) as db:
            db.execute("UPDATE users SET display_name='NOMBRE-OPERADOR'")
            db.execute("UPDATE suppliers SET contact='CONTACTO-PRIVADO',phone='TELEFONO-PRIVADO'")
        self.pos.cash_movement(1, dict(direction='in', category='change', amount_cents=125,
                                      concept='NOTA-PRIVADA', request_key='privacy-cash'))
        sync = BranchSync(self.pos)
        url, token = 'https://qa.workers.dev', 'e' * 64
        sync.configure(dict(url=url, name='Centro', token=token))
        with database(sync.path) as db:
            target = hashlib.sha256((url + '|' + token).encode()).hexdigest()
            db.execute('INSERT INTO outbox(target,route,body) VALUES(?,?,?)',
                       (target, 'snapshot', b'{"legacy":"NOTA-ANTERIOR"}'))
        sent = []

        def send(_url, _token, body):
            doc = json.loads(body)
            sent.append(doc)
            return {'ok': True, 'revision': doc['revision']}

        sync.once(send)
        serialized = json.dumps(sent)
        for secret in ('NOMBRE-OPERADOR', 'CONTACTO-PRIVADO', 'TELEFONO-PRIVADO', 'NOTA-PRIVADA', 'NOTA-ANTERIOR'):
            self.assertNotIn(secret, serialized)
        self.assertEqual(sent[0]['direction']['suppliers'][0]['business_name'], 'Distribuidor')
        self.assertEqual(sent[1]['report']['cash_movements'][0]['amount_cents'], 125)
        with self.pos.db() as db:
            self.assertEqual(db.execute('SELECT concept FROM cash_movements').fetchone()[0], 'NOTA-PRIVADA')
