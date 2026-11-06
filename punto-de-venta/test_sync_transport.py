import gzip
import json
import random
import string
import unittest
from unittest.mock import patch
from core import Error
from sync_transport import send

class TransportTest(unittest.TestCase):
    def test_large_update_is_split_and_reassembled_without_loss(self):
        rng=random.Random(17)
        payload={'revision':4,'instance_id':'a'*32,'catalog':''.join(rng.choices(string.ascii_letters+string.digits,k=1800000))}
        received=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return json.dumps({'ok':True,'revision':4,'complete':len(received)==received[-1]['parts']}).encode()
        class Opener:
            def open(self,request,timeout):
                selftest.assertEqual(request.full_url,'https://qa.workers.dev/api/upload-part')
                selftest.assertLess(len(request.data),900000)
                received.append(json.loads(request.data));return Response()
        selftest=self
        with patch('sync_transport.build_opener',return_value=Opener()):result=send('https://qa.workers.dev','b'*64,'/api/snapshot',payload)
        self.assertTrue(result['complete']);self.assertGreater(len(received),1)
        import base64,hashlib
        packed=b''.join(base64.b64decode(p['data']) for p in received)
        self.assertEqual(hashlib.sha256(packed).hexdigest(),received[0]['sha256'])
        self.assertEqual(json.loads(gzip.decompress(packed)),payload)

    def test_missing_confirmation_keeps_operation_unconfirmed(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return b'{"ok":true,"revision":3}'
        class Opener:
            def open(self,*args,**kwargs):return Response()
        with patch('sync_transport.build_opener',return_value=Opener()),self.assertRaises(Error):
            send('https://qa.workers.dev','b'*64,'/api/history-day',{'revision':3,'instance_id':'a'*32,'text':'x'*1000000})
