import base64,contextlib,copy,json,sqlite3,struct,unittest,zlib
from pathlib import Path
from unittest.mock import patch,MagicMock
import test_pos,test_inventory_io as helper,test_branding
import branding,credit,promotions,inventory_io as transfer,cash_basis
from core import POS,Error,fingerprint
class RemainingBranchesTest(unittest.TestCase):
 setUp=test_pos.POSTest.setUp
 tearDown=test_pos.POSTest.tearDown
 receive=test_pos.POSTest.receive
 body=test_pos.POSTest.body
 def reject(self,fn,*args):
  with self.assertRaises(Error):fn(*args)
 def test_credit_invalid_inputs_and_request_conflict(self):
  self.reject(self.pos.sale,1,dict(self.body(),on_account=True,customer_id=1))
  self.reject(self.pos.sale,1,dict(self.body(),on_account=True,payments=[]))
  self.pos.sale(1,dict(self.body('credit'),on_account=True,customer_id=1,payments=[]))
  base=dict(request_key='abono',customer_id=1,amount_cents=100,method='cash')
  for change in [dict(method='invalid'),dict(customer_id=999),dict(method='debit',amount_cents=99999),dict(method='transfer',received_cents=200)]:self.reject(credit.payment,self.pos,1,dict(base,**change))
  credit.payment(self.pos,1,base);self.reject(credit.payment,self.pos,1,dict(base,amount_cents=200))
  self.reject(self.pos.edit_batch,1,dict(batch_id=999,reason='Prueba'))
  self.reject(self.pos.edit_batch,1,dict(batch_id=self.early,lot_number='x'*501,reason='Prueba'))
  for change in [dict(product_id=999),dict(schedule_type='bad'),dict(starts_on='2099-01-02',ends_on='2099-01-01')]:
   self.reject(promotions.save,self.pos,1,dict(dict(product_id=self.pid,name='Oferta',price_cents=100,starts_on='2099-01-01',ends_on='2099-01-02'),**change))
 def test_png_error_branches(self):
  self.reject(branding.save_settings,self.pos,1,dict(name='Farmacia',receipt_footer='x'*201))
  def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
  prefix=bytes.fromhex('89504e470d0a1a0a')
  raw=test_branding.sample_png();bad=bytearray(raw);bad[29]^=1
  samples=[prefix+struct.pack('>I',10000)+b'IHDR'+b'0'*20,raw[:-1],bytes(bad),prefix+chunk(b'BAD!',b'123'),prefix+chunk(b'IHDR',struct.pack('>IIBBBBB',5000,1,8,2,0,0,0))]
  for value in samples:self.reject(branding.validate,base64.b64encode(value).decode())
 def test_split_refunds_skip_exhausted_payment(self):
  ticket=self.pos.sale(1,dict(self.body(qty=2),payments=[dict(method='cash',amount_cents=1160),dict(method='debit',amount_cents=1160)]));iid=ticket['items'][0]['id']
  for n,method in enumerate(['cash','debit']):
   result=self.pos.return_sale(1,dict(request_key='ret%d'%n,sale_id=ticket['id'],reason='Prueba',items=[dict(sale_item_id=iid,quantity=1)]))
   self.assertEqual(result['refunds'],[dict(method=method,amount_cents=1160)])
 def test_cash_basis_outside_range_and_corrupt_ledger(self):
  pid=self.pos.save_product(1,dict(barcode='FREE',name='Regalo',category_id=1,price_cents=0))['id'];self.pos.receive(1,dict(product_id=pid,quantity=1,unit_cost_cents=100,reason='Prueba'))
  self.pos.sale(1,dict(request_key='free',customer_id=1,on_account=True,items=[dict(product_id=pid,quantity=1),dict(product_id=self.pid,quantity=1)],payments=[]))
  credit.payment(self.pos,1,dict(request_key='pay',customer_id=1,amount_cents=1044,method='cash'))
  with self.pos.db() as db:self.assertEqual(cash_basis.collections(db,start='2000-01-01',end='2000-01-01'),[])
  with self.pos.db(True) as db:db.execute("INSERT INTO customer_ledger(customer_id,shift_id,user_id,amount_cents,method) VALUES (1,?,1,-1,'cash')",(self.sid,))
  with self.pos.db() as db:
   with self.assertRaises(ValueError):cash_basis.collections(db)
 def test_import_selection_limits_and_invalid_revision(self):
  valid=helper.upload(helper.legacy([['NEW','Producto',1,2,0,1,0,'Otros']]))
  self.reject(transfer.parse_file,dict(valid,selection='bad'))
  self.reject(transfer.parse_file,helper.upload(json.dumps(dict(format='botica-inventory',version=1,products=None))))
  extra=helper.legacy([['NEW','Producto',1,2,0,1,0,'Otros','Sobra']]);_,summary=transfer.parse_file(helper.upload(extra));self.assertEqual(len(summary['issues']),1)
  for change in [dict(excluded_rows='bad'),dict(excluded_rows=[2]),dict(existing='bad'),dict(revision='bad')]:self.reject(transfer.import_inventory,self.pos,1,dict(valid,request_key='new',**change))
  preview=transfer.preview(self.pos,1,valid);data=dict(valid,request_key='new',revision=preview['revision']);transfer.import_inventory(self.pos,1,data)
  self.reject(transfer.import_inventory,self.pos,1,dict(data,existing='replace'))
  self.reject(transfer.export_inventory,self.pos,1,'bad')
  many=helper.legacy([['A','P',1,2,0,0,0,'Otros']]*50001);self.reject(transfer.parse_file,helper.upload(many))
  self.reject(transfer.parse_file,helper.upload(json.dumps(dict(format='botica-inventory',version=1,products=[dict(barcode='A',name='P')]*50001))))
 def test_zero_batch_inactive_export_and_backup_structure(self):
  native=dict(format='botica-inventory',version=1,products=[dict(barcode='ZERO',name='Zero',active=0,batches=[dict(quantity=0)])])
  data=helper.upload(json.dumps(native));preview=transfer.preview(self.pos,1,data);transfer.import_inventory(self.pos,1,dict(data,revision=preview['revision'],request_key='zero'))
  raw,_,_=transfer.export_inventory(self.pos,1,'csv');self.assertNotIn(b'ZERO',raw)
  raw,_,_=transfer.backup(self.pos,1);source=json.loads(raw)
  def upload(doc):
   doc=copy.deepcopy(doc);doc.pop('sha256',None);doc['sha256']=fingerprint(doc);return helper.upload(json.dumps(doc))
  for change in [dict(tables={}),dict(tables=dict(source['tables'],products='bad')),dict(tables=dict(source['tables'],business_branding=['bad']))]:self.reject(transfer.read_backup,upload(dict(source,**change)))
  old=copy.deepcopy(source);old['version']=3;old['tables']['promotions']=['bad'];self.assertEqual(transfer.read_backup(upload(old))['tables']['promotions'],['bad'])
  target=POS(self.pos.path+'.target');target.initialize('qa','test-password')
  self.reject(transfer.restore,target,1,upload(source))
  for values in [[{'id':1}], [dict(source['tables']['products'][0],name=[])], [dict(source['tables']['products'][0],category_id=999)]]:
   broken=copy.deepcopy(source);broken['tables']['products']=values
   self.reject(transfer.restore,target,1,dict(upload(broken),confirmation='RESTAURAR'))
  real_connect=sqlite3.connect
  class BadIntegrity(sqlite3.Connection):
   def execute(self,sql,*args):
    if sql=='PRAGMA integrity_check':
     result=MagicMock();result.fetchone.return_value=('corrupt',);return result
    return super().execute(sql,*args)
  def connect(path,*args,**kwargs):
   if str(path)==target.path:kwargs['factory']=BadIntegrity
   return real_connect(path,*args,**kwargs)
  with patch('core.sqlite3.connect',side_effect=connect):self.reject(transfer.restore,target,1,dict(upload(source),confirmation='RESTAURAR'))
