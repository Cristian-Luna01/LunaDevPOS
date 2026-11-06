"""Transporte fragmentado comprimido; compatible con el envío pequeño anterior."""
import base64
import gzip
import hashlib
import json
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from core import Error

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def send(url,token,path,payload):
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
    if len(raw)>32*1024*1024:raise Error('La actualización supera 32 MB. Reduce el periodo o divide el catálogo.')
    def post(route,body):
        request=Request(url+route,data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+token,'User-Agent':'LunaDevPOS/0.2'},method='POST')
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=30) as response:
            return json.loads(response.read(4096))
    if len(raw)<=900000:return post(path,raw)
    packed=gzip.compress(raw,mtime=0);hash=hashlib.sha256(packed).hexdigest()
    chunks=[packed[i:i+512*1024] for i in range(0,len(packed),512*1024)]
    if len(chunks)>32:raise Error('La actualización comprimida supera 16 MB')
    for i,chunk in enumerate(chunks):
        part={'kind':'snapshot' if path.endswith('/snapshot') else 'history','instance_id':payload['instance_id'],
              'revision':payload['revision'],'upload_id':hash,'sha256':hash,'parts':len(chunks),'part':i,'data':base64.b64encode(chunk).decode()}
        result=post('/api/upload-part',json.dumps(part,separators=(',',':')).encode())
        if result.get('ok') is not True or result.get('revision')!=payload['revision']:raise Error('No se confirmó una parte de la actualización')
    if result.get('complete') is not True:raise Error('La página central no confirmó todas las partes')
    return result
