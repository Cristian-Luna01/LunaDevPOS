"""Acceso temporal protegido por correo. Solo publica Dirección de consulta."""
from http.server import BaseHTTPRequestHandler
from http_limits import ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
from pathlib import Path
import json, os, re, subprocess, threading
from core import ROOT, Error
from owner_gate import PrivateGate,PAGE as GATE_PAGE,SCRIPT as GATE_SCRIPT

GET_ROUTES={'/direccion','/direccion/','/direccion/panel.js','/style.css','/reports.js','/branding.js','/navigation.js','/favicon.svg','/business-settings','/business-logo.png','/direccion/api/summary','/direccion/api/history','/direccion/api/history.csv','/direccion/api/history.xlsx','/direccion/api/metrics'}
GET_ROUTES.update({'/login-hints.js','/live-view.js'})
POST_ROUTES={'/direccion/api/login','/direccion/api/logout'}

class BridgeHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)
    def log_message(self,*args):pass
    def do_GET(self):self.forward(False)
    def do_POST(self):self.forward(True)
    def error(self,status,message):
        raw=json.dumps({'error':message},ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def forward(self,write):
        manager=self.server.manager;path=urlsplit(self.path).path
        host=self.headers.get('Host','')
        hosts={manager.hostname,f'127.0.0.1:{self.server.server_port}'}
        if host not in hosts:return self.error(403,'Host no permitido')
        gate=getattr(manager,'gate',None)
        if gate and path=='/owner-gate.js' and not write:return self.gate_response(200,GATE_SCRIPT,'text/javascript')
        if gate and path=='/owner-access/verify' and write:
            if self.headers.get('Origin','')!=f'https://{manager.hostname}' or self.headers.get('X-POS-Request')!='1':return self.error(403,'Origen no permitido')
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=1024 or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError()
                body=json.loads(self.rfile.read(length));code=body.get('code')
            except (ValueError,TypeError,AttributeError):return self.error(400,'Solicitud de acceso inválida')
            with manager.lock:status,data,cookie=gate.verify(code,self.client_address[0])
            return self.gate_response(status,json.dumps(data).encode(),'application/json',cookie)
        if gate and not gate.authorized(self.headers):
            if not write and path in ('/','/direccion','/direccion/'):return self.gate_response(200,GATE_PAGE)
            if not write and path=='/style.css':pass
            else:return self.gate_response(401,json.dumps({'error':'Abre el enlace privado completo del dueño para verificar el acceso.','owner_access_required':True}).encode(),'application/json')
        if path=='/' and not write:
            self.send_response(302);self.send_header('Location','/direccion/');self.send_header('Content-Length','0');self.end_headers();return
        if path=='/owner-readonly.js' and not write:
            raw=b'window.ownerReadOnly=true;';self.send_response(200);self.send_header('Content-Type','text/javascript');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
        if path not in (POST_ROUTES if write else GET_ROUTES):return self.error(403,'El acceso del dueño es únicamente de consulta')
        headers={'Host':f'127.0.0.1:{manager.backend.server_port}'}
        if self.headers.get('Cookie'):headers['Cookie']=self.headers['Cookie']
        body=None
        if write:
            origin=self.headers.get('Origin','');allowed={f'https://{manager.hostname}',f'http://127.0.0.1:{self.server.server_port}'}
            if not origin or origin not in allowed or self.headers.get('X-POS-Request')!='1':return self.error(403,'Origen no permitido')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.error(415,'Usa application/json')
            try:length=int(self.headers.get('Content-Length','0'))
            except ValueError:return self.error(400,'Tamaño inválido')
            if not 0<length<=8192:return self.error(413,'Tamaño inválido')
            body=self.rfile.read(length);headers.update({'Content-Type':'application/json','X-POS-Request':'1','Origin':f'http://127.0.0.1:{manager.backend.server_port}'})
        try:
            request=Request(f'http://127.0.0.1:{manager.backend.server_port}'+self.path,data=body,headers=headers)
            try:response=build_opener(ProxyHandler({})).open(request,timeout=25)
            except HTTPError as error:response=error
            with response:
                raw=response.read(32*1024*1024+1)
                if len(raw)>32*1024*1024:return self.error(502,'La consulta es demasiado grande; reduce el periodo')
                if path in ('/direccion','/direccion/') and response.status==200:raw=raw.replace(b'<script src="/branding.js"',b'<script src="/owner-readonly.js" defer></script><script src="/branding.js"',1)
                self.send_response(response.status)
                for key,value in response.headers.items():
                    if key.lower() in ('content-type','content-disposition','content-security-policy','referrer-policy','x-content-type-options'):self.send_header(key,value)
                    if key.lower()=='set-cookie':self.send_header(key,value+'; Secure')
                self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        except (OSError,ValueError):self.error(502,'No se pudo consultar el punto de venta. Intenta nuevamente.')

    def gate_response(self,status,raw,mime='text/html; charset=utf-8',cookie=None):
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(raw)

class OwnerAccess:
    def __init__(self,backend):
        self.backend=backend;self.bridge=None;self.process=None;self.hostname='';self.email='';self.state='off';self.lock=threading.RLock();self.stop_event=threading.Event();self.reader=None;self.local_bridge=None;self.local_thread=None;self.local_ips=[];self.gate=None;self.mode='email'
    def status(self):
        with self.lock:
            bridge=self.local_bridge;addresses=tuple(self.local_ips)
            url=('https://'+self.hostname+'/direccion/') if self.hostname and self.state=='ready' else ''
            if url and self.gate:url+='#access='+self.gate.key
            return {'available':True,'state':self.state,'email':self.email,'mode':self.mode,'url':url, 'local_enabled':bridge is not None,'local_urls':[f'http://{a}:{bridge.server_port}/direccion/' for a in addresses] if bridge else []}
    def start_local(self):
        raise Error('El acceso local por HTTP está deshabilitado. Usa Dirección mediante un enlace HTTPS.',403)
    def stop_local(self):
        if self.local_bridge:self.local_bridge.shutdown();self.local_bridge.server_close()
        if self.local_thread:self.local_thread.join(timeout=2)
        self.local_bridge=None;self.local_thread=None;self.local_ips=[]
    def start(self,email='',mode='email'):
        email=str(email).strip().lower()
        if mode not in ('email','private_link'):raise Error('Modalidad de acceso inválida')
        if mode=='email' and (not re.fullmatch(r'[a-z0-9._%+-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}',email) or any(c in email for c in ('*',',','\n','\r')) or len(email)>254):raise Error('Escribe un único correo válido del dueño')
        with self.lock:
            if self.process and self.process.poll() is None:raise Error('Desactiva el enlace actual antes de cambiar el correo')
        self.stop_remote()
        executable=ROOT/'vendor'/'cloudflared.exe'
        if not executable.exists():raise Error('Esta versión no incluye el conector de acceso remoto')
        self.mode=mode;self.gate=PrivateGate() if mode=='private_link' else None;self.email=email if mode=='email' else '';self.state='connecting';self.stop_event.clear()
        bridge=ThreadingHTTPServer(('127.0.0.1',0),BridgeHandler);bridge.manager=self;bridge.daemon_threads=True;bridge.block_on_close=False;self.bridge=bridge
        threading.Thread(target=bridge.serve_forever,daemon=True).start()
        command=[str(executable),'tunnel','--no-autoupdate','--url',f'http://127.0.0.1:{bridge.server_port}','--protocol','http2']
        if mode=='email':command+=['--allowed-mail',email]
        try:self.process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except OSError:
            self.stop_remote();raise Error('No se pudo iniciar el conector. Revisa que el antivirus no lo haya bloqueado.')
        self.reader=threading.Thread(target=self.read_output,daemon=True);self.reader.start();return self.status()
    def read_output(self):
        process=self.process
        for line in process.stdout:
            if self.stop_event.is_set():break
            match=re.search(r'https://([a-z0-9-]+\.trycloudflare\.com)',line)
            with self.lock:
                if match:self.hostname=match.group(1)
                if 'Registered tunnel connection' in line and self.hostname:self.state='ready'
        with self.lock:
            if not self.stop_event.is_set() and process is self.process:self.state='error';self.hostname=''
    def stop(self):
        self.stop_local();self.stop_remote()
    def stop_remote(self):
        self.stop_event.set()
        process=self.process
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=4)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=4)
        if self.bridge:self.bridge.shutdown();self.bridge.server_close()
        self.bridge=None;self.process=None
        if self.reader and self.reader is not threading.current_thread():self.reader.join(timeout=2)
        self.reader=None
        with self.lock:self.state='off';self.hostname='';self.email='';self.gate=None
