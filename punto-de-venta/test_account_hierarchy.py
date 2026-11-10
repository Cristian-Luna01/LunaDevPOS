import json
import base64
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from core import Error, POS
from inventory_io import empty_for_restore, read_backup, restore
import test_customer_http


class AccountHierarchyTest(unittest.TestCase):
    setUp = test_customer_http.CustomerHTTPTest.setUp
    tearDown = test_customer_http.CustomerHTTPTest.tearDown
    request = test_customer_http.CustomerHTTPTest.request
    receive = test_customer_http.CustomerHTTPTest.receive

    def call(self, path, data=None):
        with self.request('/api/' + path, data) as response:
            return json.load(response)

    def deny(self, path, data=None):
        with self.assertRaises(HTTPError) as caught:
            self.call(path, data)
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()

    def sign_in(self, username):
        self.cookie = ''
        with self.request('/api/login', {'username': username, 'secret': 'sample-password'}) as response:
            self.cookie = response.headers['Set-Cookie'].split(';')[0]

    def test_permissions_status_and_account_history(self):
        owner_cookie = self.cookie
        seller = {'role': 'seller', 'username': 'seller', 'display_name': 'Seller',
                  'secret': 'sample-password', 'permissions': ['sell']}
        peer = self.call('users/save', dict(seller, username='peer', role='administrator',
                                           permissions=['users.manage', 'backup.manage']))['id']
        supervisor = self.call('users/save', dict(seller, username='supervisor', role='supervisor'))['id']
        self.sign_in('peer')
        self.deny('users/save', dict(seller, id=1))
        self.cookie = owner_cookie
        self.deny('users/save', dict(seller, id=peer))
        self.deny('entities/users/status', {'id': peer, 'active': 0, 'reason': 'Test'})
        self.sign_in('supervisor')
        self.assertEqual(self.call('me')['account_management']['role'], 'supervisor')
        self.deny('users/save', dict(seller, role='supervisor'))
        self.deny('users/save', dict(seller, role='administrator'))
        self.deny('users/save', dict(seller, permissions=['backup.manage']))
        self.deny('users/save', dict(seller, id=peer))
        self.deny('users/save', dict(seller, id=supervisor))
        self.deny('users/history')
        self.deny('backup/preview', {})
        worker = self.call('users/save', seller)['id']
        self.assertEqual([row['id'] for row in self.call('users')], [worker])
        self.sign_in('seller')
        self.deny('users/save', dict(seller, username='other'))
        self.deny('users/history')
        self.sign_in('supervisor')
        self.call('users/save', dict(seller, id=worker, secret='new-secret-qa', permissions=[]))
        self.call('entities/users/status', {'id': worker, 'active': 0, 'reason': 'Test'})
        self.cookie = owner_cookie
        history = self.call('users/history')['rows']
        status, update = history[:2]
        self.assertEqual((status['action'], status['target'], status['details']['after']),
                         ('users.status', 'seller', 0))
        self.assertEqual((update['actor'], update['target'], update['entity_id']),
                         ('supervisor', 'seller', worker))
        self.assertTrue(update['created_at'])
        self.assertTrue(update['details']['credential_reset'])
        self.assertEqual(update['details']['before']['permissions'], ['sell'])
        self.assertEqual(update['details']['after']['permissions'], [])
        self.assertNotIn('new-secret-qa', json.dumps(history))
        self.assertEqual(self.call('users/history?before='+str(update['id']))['rows'][0]['action'],
                         'user.create')

    def test_restore_requires_a_fresh_installation_even_without_sales(self):
        with tempfile.TemporaryDirectory() as directory:
            pos = POS(Path(directory) / 'pos.sqlite3')
            pos.initialize('admin', 'sample-password')
            with pos.db() as db:
                self.assertTrue(empty_for_restore(db))
            pos.save_user(1, {'username': 'peer', 'display_name': 'Peer', 'role': 'administrator',
                              'secret': 'sample-password', 'permissions': ['users.manage']})
            with pos.db() as db:
                self.assertFalse(empty_for_restore(db))

    def test_direction_sessions_and_failed_logins_are_separate(self):
        owner_cookie = self.cookie
        with self.request('/direccion/api/login', {'username':'admin','secret':'test-only-password'}) as response:
            direction = response.headers['Set-Cookie'].split(';')[0]
        self.cookie = direction.replace('direction_session_', 'pos_session_', 1)
        with self.assertRaises(HTTPError) as denied:
            self.call('me')
        self.assertEqual(denied.exception.code,401)
        denied.exception.close()
        self.cookie = owner_cookie
        for _ in range(5):
            with self.assertRaises(HTTPError) as failure:
                self.request('/direccion/api/login', {'username':'admin','secret':'wrong-pass'})
            self.assertEqual(failure.exception.code,401)
            failure.exception.close()
        self.assertTrue(self.pos.login('admin','test-only-password'))

    def test_file_permissions_and_encrypted_portable_export(self):
        from backup_crypto import PORTABLE
        phrase = 'frase de prueba portátil'
        owner_cookie = self.cookie
        self.cookie = ''
        with self.assertRaises(HTTPError) as denied:
            self.call('backup/preview', {'file_base64':'incorrecto'})
        self.assertEqual(denied.exception.code,401)
        denied.exception.close()
        self.cookie = owner_cookie
        with self.request('/api/backup/export', {'passphrase':phrase}) as response:
            encrypted = response.read()
        self.assertTrue(encrypted.startswith(PORTABLE))
        self.assertNotIn(b'password_hash', encrypted)
        upload = {'file_base64':base64.b64encode(encrypted).decode(),'passphrase':phrase}
        self.assertEqual(read_backup(upload)['tables']['users'][0]['username'],'admin')
        fresh=POS(Path(self.temp.name)/'portable-restore.sqlite3')
        fresh.initialize('initial','sample-password')
        restore(fresh,1,dict(upload,confirmation='RESTAURAR'))
        self.assertTrue(fresh.login('admin','test-only-password'))
        with self.assertRaises(Error):
            read_backup(dict(upload,passphrase='frase equivocada de prueba'))
        corrupt = encrypted[:-1]+bytes([encrypted[-1]^1])
        with self.assertRaises(Error):
            read_backup(dict(upload,file_base64=base64.b64encode(corrupt).decode()))
        self.call('users/save', {'username':'seller','display_name':'Vendedor','role':'seller',
                                 'permissions':['sell'],'secret':'sample-password'})
        self.sign_in('seller')
        self.deny('inventory/import/preview', {'file_base64':'incorrecto'})
