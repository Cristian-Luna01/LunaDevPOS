import contextlib, io, sqlite3, tempfile, unittest, runpy
from http.server import ThreadingHTTPServer as LegacyHTTPServer
from pathlib import Path
from unittest.mock import patch, MagicMock
import app,iniciar,recuperar_acceso,core,migrations,inventory_io

class StartupAuditTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=self.root/'data/pos.sqlite3';self.pos=core.POS(self.db);(self.root/'schema.sql').write_bytes((core.ROOT/'schema.sql').read_bytes())
 def tearDown(self):self.tmp.cleanup()
 def test_cli_initialize_backup_and_server_close(self):
  args=['app.py','init','--db',str(self.db)]
  with patch('sys.argv',args),patch('app.getpass.getpass',return_value='test-password'),contextlib.redirect_stdout(io.StringIO()):app.main()
  dest=self.root/'copy.sqlite3'
  with patch('sys.argv',['app.py','backup','--db',str(self.db),'--destination',str(dest)]),contextlib.redirect_stdout(io.StringIO()):app.main()
  with contextlib.closing(sqlite3.connect(dest)) as db:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
  for options in [[],['--destination',str(dest)]]:
   with patch('sys.argv',['app.py','backup','--db',str(self.db)]+options),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):app.main()
  for error in [None,KeyboardInterrupt()]:
   server=MagicMock();server.serve_forever.side_effect=error
   with patch('sys.argv',['app.py','serve','--db',str(self.db),'--port','0']),patch('app.ThreadingHTTPServer',return_value=server),contextlib.redirect_stdout(io.StringIO()):app.main()
   server.server_close.assert_called_once()
  with patch('sys.argv',['app.py','serve','--db',str(self.root/'empty.sqlite3')]),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):app.main()
 def test_windows_launcher_first_start_existing_and_browser_failure(self):
  server=MagicMock(server_port=8765);server.serve_forever.side_effect=KeyboardInterrupt()
  with patch('core.ROOT',self.root),patch('iniciar.serve_available',return_value=server),patch('iniciar.getpass.getpass',side_effect=['short','password-A','password-B','test-password','test-password']),patch('iniciar.webbrowser.open',side_effect=RuntimeError('Prueba')),contextlib.redirect_stdout(io.StringIO()):iniciar.main()
  self.assertTrue((self.root/'data/Direccion.url').exists());server.server_close.assert_called_once()
  with patch('core.ROOT',self.root),patch('iniciar.serve_available',return_value=MagicMock()),patch('iniciar.webbrowser.open'),contextlib.redirect_stdout(io.StringIO()):iniciar.main()
 def test_busy_ports_and_unexpected_socket_failure(self):
  with patch('app.ThreadingHTTPServer',side_effect=[OSError(98,'busy'),MagicMock()]) as create:
   self.assertIsNotNone(iniciar.serve_available(self.pos,start=10001,stop=10002));self.assertEqual(create.call_count,2)
  with patch('app.ThreadingHTTPServer',side_effect=OSError(98,'busy')),self.assertRaises(RuntimeError):iniciar.serve_available(self.pos,start=10001,stop=10002)
  with patch('app.ThreadingHTTPServer',side_effect=OSError(1,'unexpected')),self.assertRaises(OSError):iniciar.serve_available(self.pos)
 def test_existing_http_listener_cannot_share_the_pos_port(self):
  with LegacyHTTPServer(('127.0.0.1',0),app.Handler) as legacy:
   with self.assertRaisesRegex(RuntimeError,'puertos'):
    iniciar.serve_available(self.pos,start=legacy.server_port,stop=legacy.server_port)
 def test_local_recovery_only_on_isolated_database(self):
  self.pos.initialize('qa','test-password');token=self.pos.login('qa','test-password')
  def run(inputs,passwords):
   with patch('recuperar_acceso.ROOT',self.root),patch('builtins.input',side_effect=inputs),patch('recuperar_acceso.getpass.getpass',side_effect=passwords),contextlib.redirect_stdout(io.StringIO()):recuperar_acceso.main()
  for inputs,passwords in [(['999'],[]),(['1'],['short']),(['1'],['password-A','password-B'])]:
   with self.assertRaises(RuntimeError):run(inputs,passwords)
  run(['1','CANCELAR'],['new-password','new-password']);self.pos.session_user(token)
  run(['1','RECUPERAR'],['new-password','new-password']);self.pos.login('qa','new-password')
  with self.assertRaises(core.Error):self.pos.session_user(token)
  with self.pos.db(True) as db:db.execute('UPDATE users SET active=0')
  with self.assertRaises(RuntimeError):run([],[])
 def test_migrations_empty_future_and_inconsistent_relations(self):
  empty=self.root/'empty.sqlite3';sqlite3.connect(empty).close();migrations.upgrade(empty,core.PERMISSIONS)
  self.pos.initialize('qa','test-password')
  with self.pos.db(True) as db:db.execute('PRAGMA user_version=12')
  with self.assertRaises(RuntimeError):migrations.upgrade(self.db,core.PERMISSIONS)
  with contextlib.closing(sqlite3.connect(self.db)) as db:
   db.execute('PRAGMA user_version=6');db.execute("INSERT INTO products(barcode,name,category_id,cost_cents,price_cents) VALUES ('BROKEN','Broken',999,0,1)");db.commit()
  with self.assertRaises(RuntimeError):migrations.upgrade(self.db,core.PERMISSIONS)
  with contextlib.closing(sqlite3.connect(self.db)) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],6)

 def test_script_entrypoints_and_cancellation(self):
  self.pos.initialize('qa','test-password')
  with patch('core.ROOT',self.root),patch('sys.argv',['app.py','backup','--db',str(self.db),'--destination',str(self.root/'guard-copy.sqlite3')]),contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(core.ROOT/'app.py') if core.ROOT!=self.root else str(Path(app.__file__)),run_name='__main__')
  for error in [KeyboardInterrupt(),EOFError(),RuntimeError('Error de prueba')]:
   with patch('core.ROOT',self.root),patch('iniciar.getpass.getpass',side_effect=error),patch('app.ThreadingHTTPServer',side_effect=error),contextlib.redirect_stdout(io.StringIO()):
    if isinstance(error,RuntimeError):
     with self.assertRaises(SystemExit):runpy.run_path(str(Path(iniciar.__file__)),run_name='__main__')
    else:runpy.run_path(str(Path(iniciar.__file__)),run_name='__main__')
  for error in [KeyboardInterrupt(),EOFError(),RuntimeError('Error de prueba')]:
   with patch('core.ROOT',self.root),patch('builtins.input',side_effect=error),contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(Path(recuperar_acceso.__file__)),run_name='__main__')
 def test_failed_backup_integrity_aborts_cli_and_migration(self):
  self.pos.initialize('qa','test-password')
  real_connect=sqlite3.connect
  class BrokenIntegrity(sqlite3.Connection):
   def execute(self,sql,*args):
    if sql=='PRAGMA integrity_check':
     row=MagicMock();row.fetchone.return_value=('simulated corruption',);return row
    return super().execute(sql,*args)
  def connect(path,*args,**kwargs):
   if 'bad-copy' in str(path) or '.antes-v7-' in str(path):kwargs['factory']=BrokenIntegrity
   return real_connect(path,*args,**kwargs)
  with patch('app.sqlite3.connect',side_effect=connect),patch('sys.argv',['app.py','backup','--db',str(self.db),'--destination',str(self.root/'bad-copy.sqlite3')]),self.assertRaises(RuntimeError):app.main()
  with self.pos.db(True) as db:db.execute('PRAGMA user_version=6')
  with patch('migrations.sqlite3.connect',side_effect=connect),self.assertRaises(RuntimeError):migrations.upgrade(self.db,core.PERMISSIONS)
  with contextlib.closing(real_connect(self.db)) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],6)

 def test_launcher_with_existing_empty_database_file(self):
  sqlite3.connect(self.db).close()
  with patch('core.ROOT',self.root),patch('iniciar.serve_available',return_value=MagicMock()),patch('iniciar.getpass.getpass',side_effect=['test-password','test-password']),patch('iniciar.webbrowser.open'),contextlib.redirect_stdout(io.StringIO()):iniciar.main()
  self.pos.login('admin','test-password')
