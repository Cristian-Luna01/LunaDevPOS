import datetime as dt,json,socket,time,tempfile,unittest
from pathlib import Path
from urllib.error import HTTPError
import test_customer_http as fixture
from core import POS,Error,password_hash
from branch_sync import BranchSync
import operation_journal,automatic_backup,external_backup,inventory_io

class ReliabilityTest(unittest.TestCase):
 setUp=fixture.CustomerHTTPTest.setUp
 tearDown=fixture.CustomerHTTPTest.tearDown
 request=fixture.CustomerHTTPTest.request
 receive=fixture.test_pos.POSTest.receive
 def test_history_permissions_cover_all_downloads(self):
  sale=self.pos.sale(1,{'request_key':'admin','items':[{'product_id':self.pid,'quantity':1}],'payments':[{'method':'cash','amount_cents':1160}]})
  with self.pos.db(True) as db:
   uid=db.execute("INSERT INTO users(username,display_name,password_hash) VALUES('seller','Seller',?)",(password_hash('test-password'),)).lastrowid
   db.execute("INSERT INTO user_permissions VALUES(?,'sell',1)",(uid,))
  with self.request('/api/login',{'username':'seller','secret':'test-password'}) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  for suffix in ('','.csv','.xlsx'):
   with self.assertRaises(HTTPError) as e:self.request('/api/sales/history'+suffix)
   self.assertEqual(e.exception.code,403);e.exception.close()
  with self.request('/api/tickets') as r:self.assertEqual(json.load(r)['items'],[])
 def test_slow_incomplete_request_does_not_hold_operation_lock(self):
  connection=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
  try:
   connection.sendall(('POST /api/login HTTP/1.0\r\nHost: 127.0.0.1:'+str(self.server.server_port)+'\r\nX-POS-Request: 1\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{').encode())
   start=time.monotonic()
   with self.request('/api/me') as response:self.assertEqual(response.status,200)
   self.assertLess(time.monotonic()-start,2)
  finally:connection.close()
 def test_repeat_cash_and_receipts_are_atomic_and_content_checked(self):
  cases=[(self.pos.cash_movement,{'request_key':'cash-qa','direction':'in','category':'change','amount_cents':100,'concept':'QA'}),
         (self.pos.restock,{'request_key':'restock-qa','product_id':self.pid,'quantity':2}),
         (self.pos.receive,{'request_key':'receive-qa','product_id':self.pid,'quantity':2,'unit_cost_cents':500,'reason':'QA'})]
  for fn,body in cases:
   first=fn(1,body);self.assertEqual(first,fn(1,dict(body)))
   field='amount_cents' if 'amount_cents' in body else 'quantity'
   with self.assertRaises(Error) as e:fn(1,{**body,field:body[field]+1})
   self.assertEqual(e.exception.status,409)
  with self.pos.db() as db:
   self.assertEqual(db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0],24)
   self.assertEqual(db.execute('SELECT COUNT(*) FROM cash_movements').fetchone()[0],1)
 def test_http_mutations_require_request_key(self):
  with self.assertRaises(HTTPError) as e:self.request('/api/cash',{'direction':'in','category':'change','amount_cents':100,'concept':'QA'})
  self.assertEqual(e.exception.code,400);e.exception.close()
 def test_closed_cut_uses_frozen_metadata_and_money(self):
  self.pos.cash_movement(1,{'request_key':'supplier','direction':'out','category':'supplier','amount_cents':100,'supplier_id':1,'invoice_ref':'QA','concept':'QA'})
  closed=self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':9900})
  with self.pos.db(True) as db:db.execute("UPDATE suppliers SET business_name='Renamed' WHERE id=1");db.execute("UPDATE categories SET name='Changed' WHERE id=1")
  with self.pos.db() as db:
   frozen=self.pos.report(db,self.sid)
   self.assertEqual(frozen['movements'][0]['supplier_name'],'Distribuidor')
   self.assertEqual(frozen['expected_cents'],closed['expected_cents'])
   self.assertEqual(frozen['departments'],closed['departments'])
 def test_prepare_recover_ack_and_cancel_reject_late_execution(self):
  body={'request_key':'durable','direction':'in','category':'change','amount_cents':100,'concept':'QA'}
  data={'kind':'cash','key':body['request_key'],'body':body}
  self.assertEqual(operation_journal.handle(self.pos,1,'prepare',data,True)['state'],'not_found')
  result=self.pos.cash_movement(1,body)
  reopened=POS(self.pos.path)
  found=operation_journal.handle(reopened,1,'pending',{},False)['pending']
  self.assertEqual(found['state'],'confirmed');self.assertEqual(found['result'],result)
  done=operation_journal.handle(reopened,1,'cancel',{'kind':'cash','key':'durable'},True)
  self.assertEqual(done['state'],'confirmed')
  body={**body,'request_key':'cancelled'};operation_journal.handle(self.pos,1,'prepare',{'kind':'cash','key':'cancelled','body':body},True)
  self.assertEqual(operation_journal.handle(self.pos,1,'cancel',{'kind':'cash','key':'cancelled'},True)['state'],'cancelled')
  with self.assertRaises(Error):self.pos.cash_movement(1,body)
  with self.pos.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM cash_movements').fetchone()[0],1)
 def test_pending_sale_survives_reopen_and_cancellation_is_final(self):
  body={'request_key':'pending-sale','items':[{'product_id':self.pid,'quantity':1}],'payments':[{'method':'cash','amount_cents':1160}]}
  operation_journal.handle(self.pos,1,'prepare',{'kind':'sale','key':'pending-sale','body':body},True)
  operation_journal.handle(self.pos,1,'cancel',{'kind':'sale','key':'pending-sale'},True)
  with self.assertRaises(Error):self.pos.sale(1,body)
  with self.pos.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM sales').fetchone()[0],0)
 def test_external_copy_verified_and_unavailable_is_reported(self):
  with tempfile.TemporaryDirectory() as directory:
   external_backup.configure(self.pos,directory)
   report=self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':10000})
   result=report['automatic_backup'];self.assertTrue(result['external']['ok'])
   self.assertEqual(Path(result['path']).read_bytes(),Path(result['external']['path']).read_bytes())
   document=json.loads(Path(result['path']).read_bytes());self.assertEqual(document['version'],11)
   self.assertIn('operation_intents',document['tables'])
  result=automatic_backup.after_shift(self.pos,self.sid)
  self.assertTrue(result['ok']);self.assertFalse(result['external']['ok'])
 def test_large_document_resumes_from_confirmed_block_after_restart(self):
  import base64,hashlib
  sync=BranchSync(self.pos);raw=json.dumps({'revision':33,'data':'ñ'*500000},ensure_ascii=False).encode();parts={};failed=False;calls=[]
  def send(url,token,packet):
   nonlocal failed
   p=json.loads(packet);calls.append(p['part'])
   if p['part']==2 and not failed:failed=True;raise OSError('lost')
   parts[p['part']]=base64.b64decode(p['data'])
   if len(parts)==p['total']:
    assembled=b''.join(parts[i] for i in range(p['total']));self.assertEqual(hashlib.sha256(assembled).hexdigest(),p['digest']);return {'ok':True,'revision':33}
   return {'ok':True,'part':p['part'],'complete':False}
  with self.assertRaises(OSError):sync.send_payload('https://qa.workers.dev','a'*64,raw,'snapshot',send)
  calls.clear();BranchSync(self.pos).send_payload('https://qa.workers.dev','a'*64,raw,'snapshot',send)
  self.assertEqual(calls[0],2)

 def test_restore_keeps_pending_identity_and_idempotency(self):
  import base64
  body={'request_key':'restore-me','direction':'in','category':'change','amount_cents':100,'concept':'QA'}
  operation_journal.handle(self.pos,1,'prepare',{'kind':'cash','key':'restore-me','body':body},True);result=self.pos.cash_movement(1,body)
  with self.pos.db() as db:raw,_,_=inventory_io.backup_document(db)
  other=POS(Path(self.temp.name)/'restore.sqlite3');other.initialize('other','another-password')
  inventory_io.restore(other,1,{'file_base64':base64.b64encode(raw).decode(),'confirmation':'RESTAURAR'})
  self.assertEqual(other.cash_movement(1,body),result)
  self.assertEqual(operation_journal.handle(other,1,'pending',{},False)['pending']['state'],'confirmed')
 def test_closed_seller_cut_does_not_expose_costs(self):
  uid=self.pos.save_user(1,{'username':'seller-cut','display_name':'QA','secret':'password-qa','permissions':['sell']})['id']
  sid=self.pos.open_shift(uid,{'register_id':'B','opening_cents':0})['id']
  with self.request('/api/login',{'username':'seller-cut','secret':'password-qa'}) as r:self.cookie=r.headers['Set-Cookie'].split(';')[0]
  with self.request('/api/shifts/close',{'shift_id':sid,'counted_cents':0}) as r:closed=json.load(r)
  with self.request('/api/shifts/report?id='+str(sid)) as r:again=json.load(r)
  for report in (closed,again):
   self.assertNotIn('cost_cents',report);self.assertNotIn('profit_cents',report)
 def test_indexed_date_range_matches_sqlite_local_day_boundaries(self):
  from time_ranges import utc_bounds
  day=dt.date.today().isoformat()
  with self.pos.db() as db:
   start,end=utc_bounds(db,day,day)
   timestamps=[start,end,(dt.datetime.fromisoformat(start.replace('Z','+00:00'))-dt.timedelta(milliseconds=1)).isoformat(timespec='milliseconds').replace('+00:00','Z'),(dt.datetime.fromisoformat(end.replace('Z','+00:00'))-dt.timedelta(milliseconds=1)).isoformat(timespec='milliseconds').replace('+00:00','Z')]
   for value in timestamps:
    old=db.execute("SELECT date(?,'localtime')=?",(value,day)).fetchone()[0]
    self.assertEqual(bool(old),start<=value<end)

if __name__=='__main__':unittest.main()
