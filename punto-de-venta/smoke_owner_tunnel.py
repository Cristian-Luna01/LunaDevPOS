import tempfile,threading,time
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from core import POS
from app import Handler
from owner_access import OwnerAccess
with tempfile.TemporaryDirectory() as directory:
 pos=POS(Path(directory)/'qa.sqlite3');pos.initialize('qaowner','only-a-fictitious-qa-password')
 backend=ThreadingHTTPServer(('127.0.0.1',0),Handler);backend.pos=pos;backend.daemon_threads=True;backend.block_on_close=False;thread=threading.Thread(target=backend.serve_forever,daemon=True);thread.start();manager=OwnerAccess(backend)
 try:
  manager.start('qa-owner@example.com');deadline=time.monotonic()+60
  while time.monotonic()<deadline and manager.status()['state']=='connecting':time.sleep(1)
  state=manager.status();print('Estado del conector:',state['state'])
  if state['state']!='ready':raise RuntimeError('El túnel no consiguió conectarse en la prueba')
  print('Enlace QA temporal:',state['url'])
  from urllib.error import URLError
  response=None
  for attempt in range(12):
   try:response=urlopen(Request(state['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=10);break
   except HTTPError as error:response=error;break
   except URLError:
    if attempt==11:raise
    time.sleep(3)
  with response:
   text=response.read(500000).decode('utf-8','replace').lower();print('Respuesta del enlace protegido:',response.status,'email' in text);print('Inicio de la respuesta:',text[:600])
   if 'email' not in text:raise RuntimeError('No apareció la verificación de correo')
 finally:manager.stop();backend.shutdown();backend.server_close();thread.join()
 print('Prueba externa cerrada. Solo se utilizó una base ficticia sin productos ni ventas.')
