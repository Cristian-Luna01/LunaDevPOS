"""Cliente de pruebas Facturama API Web. Sin envío a producción ni redirecciones."""
import base64,json,re
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.parse import urlencode,quote
from urllib.error import HTTPError
from billing_math import dump
class ProviderError(Exception):
    def __init__(self,message,status=None):super().__init__(message);self.status=status
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
class FacturamaSandbox:
    base='https://apisandbox.facturama.mx'
    def __init__(self,credentials):
        self.authorization='Basic '+base64.b64encode((credentials['username']+':'+credentials['password']).encode()).decode()
    def request(self,path,method='GET',body=None):
        if not path.startswith('/') or '\\' in path or '\r' in path or '\n' in path:raise ProviderError('Ruta fiscal inválida')
        req=Request(self.base+path,data=dump(body).encode() if body is not None else None,method=method,
            headers={'Authorization':self.authorization,'Content-Type':'application/json','User-Agent':'LunaDevPOS/1.0 (CFDI sandbox)'})
        try:
            with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=20) as response:
                raw=response.read(16*1024*1024+1)
                if len(raw)>16*1024*1024:raise ProviderError('La respuesta fiscal supera el tamaño admitido')
                return json.loads(raw)
        except HTTPError as error:
            # No registrar cuerpos ni cabeceras: pueden contener RFC o credenciales.
            raise ProviderError('El proveedor rechazó la solicitud. Revisa credenciales y validaciones en su portal (HTTP '+str(error.code)+').',error.code) from None
        except (OSError,ValueError) as error:raise ProviderError('No se pudo confirmar la respuesta del proveedor; consulta el resultado antes de reintentar') from None
    def create(self,body):return self.request('/3/cfdis','POST',body)
    @staticmethod
    def identifier(value):
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',value):raise ProviderError('El proveedor no devolvió un identificador válido')
        return value
    def get(self,identifier):return self.request('/cfdi/'+self.identifier(identifier)+'?type=issued')
    def lookup(self,folio):
        response=self.request('/cfdi?'+urlencode({'type':'issued','page':0,'folio':folio,'status':'all'}))
        if not isinstance(response,list):raise ProviderError('La consulta de facturas no devolvió una lista reconocible')
        return [r for r in response if str(r.get('Folio'))==str(folio)]
    def check(self):
        result=self.request('/cfdi?type=issued&page=0&status=all')
        if not isinstance(result,list):raise ProviderError('No se pudo verificar la cuenta de pruebas')
        return True
    def download(self,identifier,kind):
        if kind not in ('xml','pdf'):raise ProviderError('Formato no permitido')
        result=self.request('/cfdi/'+kind+'/issued/'+self.identifier(identifier))
        try:raw=base64.b64decode(result['Content'],validate=True)
        except (ValueError,KeyError,TypeError):raise ProviderError('El proveedor no devolvió el archivo solicitado') from None
        if len(raw)>(4*1024*1024 if kind=='xml' else 10*1024*1024):raise ProviderError('Documento fiscal demasiado grande')
        if kind=='pdf' and not raw.startswith(b'%PDF'):raise ProviderError('El archivo recibido no es PDF')
        return raw
    def cancel(self,identifier,request):return self.request('/cfdi/'+self.identifier(identifier)+'?'+urlencode({'type':'issued',**request}),'DELETE')
