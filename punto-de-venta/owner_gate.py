"""Secreto efímero del dueño: protege todo el túnel antes de entrar a Dirección."""
import hashlib,hmac,secrets,time
from http.cookies import SimpleCookie

PAGE='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Acceso privado del dueño</title><link rel="stylesheet" href="/style.css"><script src="/owner-gate.js" defer></script><body><section class="login"><h1>Acceso privado del dueño</h1><p>Abre el enlace completo que copiaste del programa. Después entrarás con tu cuenta de administrador.</p><form id="gate"><label>Código de acceso<input name="code" type="password" required autocomplete="off"></label><button>Continuar</button></form><p id="gateStatus" role="status"></p></section></body></html>'''.encode()
SCRIPT=b'''(()=>{const f=document.getElementById('gate'),s=document.getElementById('gateStatus');const token=new URLSearchParams(location.hash.slice(1)).get('access');if(token){f.elements.code.value=token;history.replaceState(null,'',location.pathname);}f.onsubmit=async e=>{e.preventDefault();f.querySelector('button').disabled=true;s.textContent='Verificando acceso privado...';try{const r=await fetch('/owner-access/verify',{method:'POST',headers:{'Content-Type':'application/json','X-POS-Request':'1'},body:JSON.stringify({code:f.elements.code.value})});const body=await r.json();if(!r.ok)throw Error(body.error||'No se pudo verificar');location.replace('/direccion/');}catch(e){s.textContent=e.message;f.querySelector('button').disabled=false;}};if(token)f.requestSubmit();})();'''

class PrivateGate:
    def __init__(self):self.key=secrets.token_urlsafe(32);self.sessions={};self.attempts={}
    def authorized(self,headers):
        cookies=SimpleCookie()
        try:cookies.load(headers.get('Cookie',''))
        except Exception:return False
        token=cookies.get('owner_gate')
        return bool(token and self.sessions.get(hashlib.sha256(token.value.encode()).hexdigest(),0)>time.time())
    def verify(self,code,peer):
        now=time.time();failures,until=self.attempts.get(peer,(0,0))
        if until>now:return 429,{'error':'Demasiados intentos. Espera un minuto.'},None
        if not isinstance(code,str) or len(code)>80 or not code.isascii() or not hmac.compare_digest(code,self.key):
            failures=failures+1 if until>now-60 else 1
            if len(self.attempts)>1000:self.attempts.clear()
            self.attempts[peer]=(failures,now+60 if failures>=5 else now)
            return 403,{'error':'Código incorrecto. Copia de nuevo el enlace privado completo del programa.'},None
        self.attempts.pop(peer,None);self.sessions={k:v for k,v in self.sessions.items() if v>now}
        if len(self.sessions)>=100:self.sessions.clear()
        token=secrets.token_urlsafe(32);self.sessions[hashlib.sha256(token.encode()).hexdigest()]=now+43200
        return 200,{'ok':True},f'owner_gate={token}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=43200'
