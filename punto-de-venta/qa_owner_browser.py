import tempfile,threading,time,json
from pathlib import Path
from http.server import ThreadingHTTPServer
from core import POS
from app import Handler
from owner_access import OwnerAccess
with tempfile.TemporaryDirectory() as directory:
 pos=POS(Path(directory)/'qa.sqlite3');pos.initialize('qaowner','only-a-fictitious-qa-password')
 backend=ThreadingHTTPServer(('127.0.0.1',0),Handler);backend.pos=pos;backend.daemon_threads=True;backend.block_on_close=False;thread=threading.Thread(target=backend.serve_forever,daemon=True);thread.start();manager=OwnerAccess(backend)
 try:
  manager.start('qa-owner@example.com');deadline=time.monotonic()+60
  while time.monotonic()<deadline and manager.status()['state']=='connecting':time.sleep(1)
  state=manager.status();print(json.dumps(state),flush=True)
  if state['state']!='ready':raise RuntimeError('No conectó el túnel')
  time.sleep(120)
 finally:manager.stop();backend.shutdown();backend.server_close();thread.join()
