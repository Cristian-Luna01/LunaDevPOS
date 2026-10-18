import base64,json,unittest
import test_inventory_io as helper
import inventory_io as io
from core import Error, POS, fingerprint
class TransferEdgesTest(unittest.TestCase):
 setUp=helper.TransferTest.setUp
 tearDown=helper.TransferTest.tearDown
 def reject(self,fn,*args):
  with self.assertRaises(Error):fn(*args)
 def test_invalid_formats_and_numbers(self):
  for data in [dict(file_base64='!'),dict(file_base64='')]:self.reject(io.file_bytes,data)
  for raw in [b'PK'+bytes([3,4]),bytes.fromhex('d0cf11e0')]:self.reject(io.decoded,raw)
  for value in ['abc','NaN','Infinity','-1','1.001','100000000000000']:self.reject(io.decimal_value,value,'Importe',True)
  self.assertEqual(io.unescape("'=formula"),'=formula')
  self.assertEqual(io.unescape('texto'),'texto')
  p=dict(barcode='A',name='A')
  for change in [dict(min_stock=100,max_stock=1),dict(batches=None),dict(batches=[dict(quantity=1,expires_on='bad')]),dict(batches=[dict(quantity=1,received_at='bad')])]:self.reject(io.validate_product,dict(p,**change))
  for text in ['{broken','{"format":"invalid"}','Codigo,Nombre']:
   self.reject(io.parse_file,helper.upload(text))
  doc=dict(format='botica-inventory',version=1,products=[p,dict(p,barcode='B',batches=[dict(quantity=1)]),dict(name='No tiene código')])
  rows,summary=io.parse_file(helper.upload(json.dumps(doc),selection='positive'))
  self.assertEqual((len(rows),summary['skipped_zero'],len(summary['issues'])),(1,1,1))
 def test_native_suppliers_are_reused_and_restore_requires_admin(self):
  p=dict(barcode='A',name='A',batches=[dict(quantity=1,supplier='Proveedor',unit_cost_cents=100)])
  doc=dict(format='botica-inventory',version=1,products=[p,dict(p,barcode='B')])
  upload=helper.upload(json.dumps(doc));preview=io.preview(self.pos,1,upload)
  io.import_inventory(self.pos,1,dict(upload,revision=preview['revision'],request_key='native'))
  with self.pos.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM suppliers').fetchone()[0],1)
  for raw in [b'\xff','{}']:self.reject(io.restore_preview,self.pos,1,helper.upload(raw))
  raw,_,_=io.backup(self.pos,1);backup=json.loads(raw)
  backup['tables']['role_permissions']=[];backup['tables']['user_permissions']=[]
  backup.pop('sha256');backup['sha256']=fingerprint(backup)
  dest=POS(self.pos.path+'.restore');dest.initialize('qa','test-password')
  self.reject(io.restore,dest,1,dict(helper.upload(json.dumps(backup)),confirmation='RESTAURAR'))
  with dest.db() as db:self.assertEqual(db.execute('SELECT username FROM users').fetchone()[0],'qa')
