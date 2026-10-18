import unittest
import test_pos
import credit
from core import Error
class CreditTest(unittest.TestCase):
 setUp=test_pos.POSTest.setUp
 tearDown=test_pos.POSTest.tearDown
 receive=test_pos.POSTest.receive
 def charge(self,key,quantity=1):
  return self.pos.sale(1,{'request_key':key,'customer_id':1,'on_account':True,'items':[{'product_id':self.pid,'quantity':quantity}],'payments':[]})
 def pay(self,key,amount,method='cash'):
  return credit.payment(self.pos,1,{'request_key':key,'customer_id':1,'amount_cents':amount,'method':method})
 def test_global_balance_stock_idempotency_and_cash(self):
  sale=self.charge('a',3)
  self.assertTrue(sale['on_account'])
  self.assertEqual(sale['total_cents'],3132)
  self.charge('a',3)
  self.pay('p',1000);self.pay('p',1000)
  self.charge('b')
  account=credit.read(self.pos,1,{'id':'1'})
  self.assertEqual(account['balance_cents'],3176)
  self.assertEqual(len(account['movements']),3)
  with self.pos.db() as db:
   self.assertEqual(db.execute('SELECT SUM(quantity) FROM batches').fetchone()[0],16)
   report=self.pos.report(db,self.sid)
   self.assertEqual(report['expected_cents'],11000)
   self.assertEqual(report['net_sales_cents'],1000)
   self.assertEqual(report['collections_by_method']['cash'],1000)
  with self.assertRaises(Error):self.pay('too-much',3177,'transfer')
  with self.assertRaises(Error):self.pay('p',500)
 def test_noncash_closed_shift_and_required_customer(self):
  self.charge('c');self.pay('t',200,'transfer')
  with self.pos.db() as db:self.assertEqual(self.pos.report(db,self.sid)['expected_cents'],10000)
  with self.assertRaises(Error):self.pos.sale(1,{'request_key':'bad','on_account':True,'items':[{'product_id':self.pid,'quantity':1}],'payments':[]})
  self.pos.close_shift(1,{'shift_id':self.sid,'counted_cents':10000})
  with self.assertRaises(Error):self.pay('closed',100)
 def test_migration_and_backup(self):
  import inventory_io,json,base64
  from core import POS
  self.charge('backup');self.pay('bp',200)
  raw,_,_=inventory_io.backup(self.pos,1)
  if isinstance(raw,str):raw=raw.encode()
  data=inventory_io.read_backup({'file_base64':base64.b64encode(raw).decode()})
  self.assertEqual(len(data['tables']['customer_ledger']),2)
  from pathlib import Path
  target=POS(Path(self.temp.name)/'restore.db');target.initialize('admin','test-password')
  inventory_io.restore(target,1,{'file_base64':base64.b64encode(raw).decode(),'confirmation':'RESTAURAR'})
  self.assertEqual(credit.read(target,1,{'id':'1'})['balance_cents'],844)
  with self.pos.db(True) as db:db.execute('PRAGMA user_version=6')
  POS(self.pos.path)
  self.assertEqual(credit.read(self.pos,1,{'id':'1'})['balance_cents'],844)

 def test_permissions(self):
  self.pos.save_user(1,{'username':'cashier','display_name':'Cajero','secret':'123456','permissions':['sell']})
  with self.pos.db() as db:uid=db.execute("SELECT id FROM users WHERE username='cashier'").fetchone()[0]
  with self.assertRaises(Error):credit.read(self.pos,uid,{})
  with self.assertRaises(Error):credit.payment(self.pos,uid,{'request_key':'no','customer_id':1,'amount_cents':100,'method':'cash'})

 def test_pending_shift_reports_owner_without_modifying_it(self):
  self.pos.save_user(1,{'username':'other','display_name':'Otro cajero','secret':'123456','permissions':['sell']})
  with self.pos.db() as db:uid=db.execute("SELECT id FROM users WHERE username='other'").fetchone()[0]
  with self.assertRaisesRegex(Error,'Administrador'):
   self.pos.open_shift(uid,{'register_id':'A','opening_cents':0})
  with self.assertRaisesRegex(Error,'Ya tienes un turno abierto'):
   self.pos.open_shift(1,{'register_id':'A','opening_cents':0})
  with self.pos.db() as db:
   self.assertEqual(db.execute('SELECT COUNT(*) FROM cash_shifts WHERE closed_at IS NULL').fetchone()[0],1)
   self.assertEqual(self.pos.shift(db,1)['opening_cents'],10000)

 def test_cash_overpayment_returns_change_and_replays_without_double_counting(self):
  sale=self.charge('change-sale')
  amount=sale['total_cents']
  result=self.pay('change-payment',amount+300)
  self.assertEqual(result['applied_cents'],amount)
  self.assertEqual(result['change_cents'],300)
  self.assertEqual(result['balance_cents'],0)
  self.assertEqual(self.pay('change-payment',amount+300),result)
  with self.pos.db() as db:
   self.assertEqual(self.pos.report(db,self.sid)['expected_cents'],10000+amount)
   self.assertEqual(db.execute('SELECT COUNT(*) FROM customer_ledger WHERE amount_cents<0').fetchone()[0],1)
  with self.assertRaises(Error):self.pay('no-debt',100)
 def test_noncash_overpayment_and_concurrent_balance_are_checked(self):
  sale=self.charge('partial-change');amount=sale['total_cents']
  with self.assertRaises(Error):self.pay('card-excess',amount+100,'debit')
  self.pay('partial-before',200,'transfer')
  result=self.pay('remaining-cash',amount+100)
  self.assertEqual(result['applied_cents'],amount-200)
  self.assertEqual(result['change_cents'],300)

 def test_received_cash_separate_from_applied_amount(self):
  sale=self.charge('separate-cash');debt=sale['total_cents']
  body={'request_key':'separate-pay','customer_id':1,'amount_cents':debt,'received_cents':debt+3500,'method':'cash'}
  result=credit.payment(self.pos,1,body)
  self.assertEqual(result['change_cents'],3500)
  self.assertEqual(result['applied_cents'],debt)
  self.assertEqual(result['balance_cents'],0)
  self.assertEqual(credit.payment(self.pos,1,body),result)
  with self.pos.db() as db:self.assertEqual(self.pos.report(db,self.sid)['expected_cents'],10000+debt)
 def test_received_cash_validation(self):
  self.charge('validate-received')
  for amount,received,method in [(500,499,'cash'),(500,600,'transfer')]:
   with self.assertRaises(Error):credit.payment(self.pos,1,{'request_key':'bad-'+method,'customer_id':1,'amount_cents':amount,'received_cents':received,'method':method})
