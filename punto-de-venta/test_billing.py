import base64,json,tempfile,unittest
from pathlib import Path
from decimal import Decimal
from core import POS,Error
import billing
from billing_service import BillingService,verify_xml
from billing_math import dump,load

class BillingTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.pos=POS(Path(self.temp.name)/'pos.db');self.pos.initialize('admin','test-only-password')
  self.pos.open_shift(1,{'register_id':'A','opening_cents':0})
  with self.pos.db(True) as db:db.execute("INSERT INTO suppliers(business_name) VALUES('QA')")
  self.pid=self.pos.save_product(1,dict(barcode='QA',name='QA',category_id=1,cost_cents=500,price_cents=1160,tax_bps=1600,max_stock=100))['id']
  self.pos.receive(1,dict(product_id=self.pid,supplier_id=1,quantity=10,unit_cost_cents=500,reason='QA'))
  self.cfg=dict(issuer_rfc='EKU9003173C9',issuer_name='ESCUELA KEMPER URGATE',fiscal_regime='601',postal_code='42501',username='fake-test-only',password='fake-test-only')
  billing.save_settings(self.pos,1,self.cfg)
  billing.save_product(self.pos,1,dict(product_id=self.pid,product_code='01010101',unit_code='H87',tax_object='02',tax_factor='Tasa',tax_bps=1600,reviewed=True))
  self.sale=self.pos.sale(1,dict(request_key='sale',items=[dict(product_id=self.pid,quantity=1)],payments=[dict(method='cash',amount_cents=1160)]))
  self.req=dict(request_key='invoice',sale_id=self.sale['id'],receiver=dict(Rfc='AAA010101AAA',Name='RECEPTOR QA',FiscalRegime='601',TaxZipCode='42501',CfdiUse='G03'))
 def tearDown(self):self.temp.cleanup()
 def draft(self):return billing.draft_income(self.pos,1,self.req)['id']
 def test_idempotency_money_and_duplicate_ticket(self):
  did=self.draft();self.assertEqual(did,self.draft());d=billing.detail(self.pos,1,did)
  self.assertEqual(d['expected_cents'],1160);self.assertEqual(d['payload']['Items'][0]['Taxes'][0]['Total'],160/100)
  with self.assertRaises(Error):billing.draft_income(self.pos,1,{**self.req,'request_key':'other'})
  billing.abandon(self.pos,1,did);self.assertNotEqual(did,billing.draft_income(self.pos,1,{**self.req,'request_key':'other'})['id'])
 def test_production_disabled_permissions_and_mapping(self):
  with self.assertRaises(Error):billing.save_settings(self.pos,1,{**self.cfg,'mode':'production'})
  with self.pos.db(True) as db:db.execute("INSERT INTO users(username,display_name,password_hash) SELECT 'seller','Seller',password_hash FROM users WHERE id=1")
  with self.assertRaises(Error):billing.list_documents(self.pos,2)
  with self.assertRaises(Error):billing.save_product(self.pos,1,dict(product_id=self.pid,product_code='01010101',unit_code='H87',tax_object='02',tax_factor='Tasa',tax_bps=0,reviewed=True))
 def test_timeout_never_automatically_resends(self):
  did=self.draft();billing.enqueue(self.pos,1,did)
  class Client:
   calls=0
   def create(self,body):Client.calls+=1;raise TimeoutError()
  service=BillingService(self.pos,lambda credentials:Client());service.once();service.once()
  self.assertEqual(Client.calls,1);self.assertEqual(billing.detail(self.pos,1,did)['state'],'unknown')
  with self.assertRaises(Error):billing.enqueue(self.pos,1,did)
  BillingService(self.pos);self.assertEqual(billing.detail(self.pos,1,did)['state'],'unknown')
 def test_restart_and_configuration_protection(self):
  did=self.draft();billing.enqueue(self.pos,1,did)
  with self.assertRaises(Error):billing.save_settings(self.pos,1,{**self.cfg,'series':'NEW'})
  with self.pos.db(True) as db:db.execute("UPDATE fiscal_documents SET state='sending' WHERE id=?",(did,))
  BillingService(self.pos);self.assertEqual(billing.detail(self.pos,1,did)['state'],'unknown')
 def test_bad_xml_remains_uncertain(self):
  did=self.draft();billing.enqueue(self.pos,1,did)
  class Client:
   def create(self,p):return {'Id':'qa-id'}
   def download(self,*a):return b'<incorrect/>'
  service=BillingService(self.pos,lambda c:Client());service.once()
  self.assertEqual(billing.detail(self.pos,1,did)['state'],'unknown')
  with self.pos.db() as db:self.assertEqual(db.execute('SELECT provider_id FROM fiscal_documents WHERE id=?',(did,)).fetchone()[0],'qa-id')
 def test_decimal_json(self):self.assertIn('0.16',dump({'x':Decimal('0.16')}));self.assertEqual(load(dump({'x':Decimal('0.16')}))['x'],Decimal('0.16'))
 def xml(self,did):
  import xml.etree.ElementTree as E
  from billing_service import CFDI,TFD
  d=billing.detail(self.pos,1,did);p=d['payload'];root=E.Element(CFDI+'Comprobante',Version='4.0',TipoDeComprobante=d['kind'],Folio=p['Folio'],Serie=p['Serie'],LugarExpedicion=p['ExpeditionPlace'],Total=str(Decimal(d['expected_cents'])/100),Moneda='MXN',MetodoPago=p['PaymentMethod'],FormaPago=p['PaymentForm'],Fecha=p['Date'])
  E.SubElement(root,CFDI+'Emisor',Rfc=self.cfg['issuer_rfc'],Nombre=self.cfg['issuer_name'],RegimenFiscal=self.cfg['fiscal_regime'])
  r=p['Receiver'];E.SubElement(root,CFDI+'Receptor',Rfc=r['Rfc'],Nombre=r['Name'],RegimenFiscalReceptor=r['FiscalRegime'],DomicilioFiscalReceptor=r['TaxZipCode'],UsoCFDI=r['CfdiUse'])
  E.SubElement(E.SubElement(root,CFDI+'Complemento'),TFD+'TimbreFiscalDigital',Version='1.1',UUID='11111111-2222-3333-4444-555555555555',SelloSAT='fixture-only',SelloCFD='fixture-only',NoCertificadoSAT='fixture-only',FechaTimbrado=p['Date'],RfcProvCertif='AAA010101AAA')
  return E.tostring(root)
 def test_xml_retained_even_when_pdf_unavailable(self):
  did=self.draft();raw=self.xml(did);billing.enqueue(self.pos,1,did)
  class Client:
   calls=0
   def create(self,p):Client.calls+=1;return {'Id':'qa-id'}
   def download(self,pid,kind):
    if kind=='pdf':raise TimeoutError()
    return raw
  service=BillingService(self.pos,lambda c:Client());service.once();service.once()
  self.assertEqual(billing.detail(self.pos,1,did)['state'],'issued');self.assertEqual(Client.calls,1)
  with self.pos.db() as db:self.assertEqual(base64.b64decode(db.execute('SELECT xml_base64 FROM fiscal_documents WHERE id=?',(did,)).fetchone()[0]),raw)
 def test_cancellation_pending_does_not_release_ticket(self):
  did=self.draft();raw=self.xml(did)
  with self.pos.db(True) as db:doc=dict(db.execute('SELECT * FROM fiscal_documents WHERE id=?',(did,)).fetchone());cfg=billing.configuration(db)
  class Client:
   calls=0
   def download(self,*a):return raw if a[-1]=='xml' else b'%PDF-fixture'
   def cancel(self,*a):Client.calls+=1;return {'Status':'pending'}
  service=BillingService(self.pos,lambda c:Client());service.collect(doc,cfg,Client(),'qa-id')
  billing.request_cancel(self.pos,1,did,{'motive':'02'});service.once();service.once()
  self.assertEqual(Client.calls,1);self.assertEqual(billing.detail(self.pos,1,did)['state'],'cancel_pending')
  with self.assertRaises(Error):billing.draft_income(self.pos,1,{**self.req,'request_key':'second'})
 def test_fiscal_backup_contains_no_plain_credentials(self):
  import inventory_io
  did=self.draft();raw,_,_=inventory_io.backup(self.pos,1)
  self.assertNotIn(b'fake-test-only',raw);doc=json.loads(raw)
  self.assertEqual(len(doc['tables']['fiscal_documents']),1);self.assertEqual(len(doc['tables']['fiscal_events']),1)
 def test_http_routes_permission_and_status(self):
  import threading
  from http.server import ThreadingHTTPServer
  from urllib.request import Request,build_opener,HTTPCookieProcessor
  from app import Handler
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.pos=self.pos;server.billing=BillingService(self.pos)
  t=threading.Thread(target=server.serve_forever,daemon=True);t.start();opener=build_opener(HTTPCookieProcessor());url=f'http://127.0.0.1:{server.server_port}'
  def call(path,data=None):
   request=Request(url+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json','X-POS-Request':'1'})
   with opener.open(request,timeout=5) as response:return json.load(response)
  try:
   call('/api/login',{'username':'admin','secret':'test-only-password'})
   self.assertFalse(call('/api/billing/status')['production_enabled']);did=call('/api/billing/income',self.req)['id']
   self.assertEqual(call('/api/billing/document?id='+str(did))['state'],'draft');self.assertEqual(len(call('/api/billing/documents')),1)
  finally:server.shutdown();server.server_close();t.join()

if __name__=='__main__':unittest.main()
