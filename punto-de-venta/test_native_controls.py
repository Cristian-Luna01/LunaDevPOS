import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from test_desktop import DesktopTest

class NativeControlsTest(DesktopTest):
 def recovery(self,username,password,count,row):
  source=ast.parse(Path('native_desktop.py').read_text(encoding='utf-8'));callback=next(n for n in ast.walk(source) if isinstance(n,ast.FunctionDef) and n.name=='confirm')
  self.messages=[];self.accepted=[];self.reloads=[]
  env={'pos':self.pos,'rows':[row],'selector':SimpleNamespace(currentIndex=lambda:0),'user':SimpleNamespace(text=lambda:username),'secret':SimpleNamespace(text=lambda:password),'count':SimpleNamespace(text=lambda:count),'views':[SimpleNamespace(reload=lambda:self.reloads.append(True))],'dialog':SimpleNamespace(accept=lambda:self.accepted.append(True)),'status':SimpleNamespace(setText=self.messages.append)}
  from core import Error
  env['Error']=Error;exec(compile(ast.fix_missing_locations(ast.Module(body=[callback],type_ignores=[])),'recovery','exec'),env);env['confirm']()
 def test_admin_can_close_another_users_pending_shift(self):
  from desktop import create_account,can_stop
  create_account(self.pos,'Farmacia','admin','12345678','12345678');uid=self.pos.save_user(1,{'username':'seller','display_name':'Vendedor','secret':'abcdefgh','permissions':['sell']})['id'];sid=self.pos.open_shift(uid,{'register_id':'A','opening_cents':1000})['id']
  self.recovery('admin','12345678','10.00',{'id':sid,'user_id':uid});self.assertTrue(self.accepted);self.assertTrue(can_stop(self.pos));self.assertTrue(self.reloads)
  with self.pos.db() as db:
   self.assertEqual(db.execute('SELECT counted_cents FROM cash_shifts WHERE id=?',(sid,)).fetchone()[0],1000)
   self.assertEqual(db.execute("SELECT user_id FROM audit_log WHERE action='shift.desktop_recovery'").fetchone()[0],1)
   self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],0)
 def test_unauthorized_account_and_invalid_count_preserve_shift(self):
  from desktop import create_account,can_stop
  create_account(self.pos,'Farmacia','admin','12345678','12345678');uid=self.pos.save_user(1,{'username':'seller','display_name':'Vendedor','secret':'abcdefgh','permissions':['sell']})['id'];sid=self.pos.open_shift(1,{'register_id':'A','opening_cents':1000})['id'];row={'id':sid,'user_id':1}
  self.recovery('seller','abcdefgh','10.00',row);self.assertFalse(self.accepted);self.assertTrue(self.messages);self.assertFalse(can_stop(self.pos))
  for amount in ('-1','nan','1.001',''):
   self.recovery('admin','12345678',amount,row);self.assertFalse(self.accepted);self.assertFalse(can_stop(self.pos))
 def test_native_close_keeps_window_and_checkout_when_shift_open(self):
  source=ast.parse(Path('native_desktop.py').read_text(encoding='utf-8'));node=next(n for n in ast.walk(source) if isinstance(n,ast.ClassDef) and n.name=='Window');events=[]
  env={'QMainWindow':object,'can_stop':lambda p:False,'pos':None,'QMessageBox':SimpleNamespace(warning=lambda *args:events.append('warning')),'tabs':SimpleNamespace(setCurrentIndex=lambda i:events.append(i))};exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'close','exec'),env)
  event=SimpleNamespace(ignore=lambda:events.append('keep-open'),accept=lambda:events.append('closed'));env['Window']().closeEvent(event);self.assertEqual(events,['warning','keep-open'])
  env['can_stop']=lambda p:True;events.clear();env['Window']().closeEvent(event);self.assertEqual(events,['closed'])
