"""API fiscal local. El servicio de red trabaja fuera del bloqueo del mostrador."""
import base64
from core import Error,integer
import billing

def handle(handler,pos,uid,path,data,write):
    route=path.removeprefix('/api/billing/')
    if not write and 'id' in data:
        value=data['id']
        if not isinstance(value,str) or not value.isascii() or not value.isdigit() or len(value)>12:raise Error('Identificador fiscal inválido')
        data={**data,'id':int(value)}
    service=getattr(handler.server,'billing',None)
    with pos.db() as db:billing.authorized(pos,db,uid,route in ('settings','products','product','check','retry','cancel','abandon'))
    if not write:
        if route=='settings':result=billing.settings(pos,uid)
        elif route=='status':result=service.status() if service else {'mode':'sandbox','production_enabled':False,'message':'Servicio no iniciado'}
        elif route=='products':result=billing.products(pos,uid,data.get('q',''))
        elif route=='documents':result=billing.list_documents(pos,uid)
        elif route=='document':result=billing.detail(pos,uid,integer(data.get('id'),'Documento',1))
        elif route=='download':
            did=integer(data.get('id'),'Documento',1);kind=data.get('kind')
            if kind not in ('xml','pdf','acuse'):raise Error('Formato inválido')
            column={'xml':'xml_base64','pdf':'pdf_base64','acuse':'cancel_ack_base64'}[kind]
            with pos.db() as db:row=db.execute('SELECT '+column+' FROM fiscal_documents WHERE id=?',(did,)).fetchone()
            if not row or not row[0]:raise Error('El archivo todavía no está disponible',404)
            return handler.send(200,base64.b64decode(row[0],validate=True),'application/pdf' if kind=='pdf' else 'application/xml',filename=f'PRUEBA-{did}-{kind}.'+('pdf' if kind=='pdf' else 'xml'))
        else:raise Error('Ruta fiscal inexistente',404)
    else:
        if route=='settings':result=billing.save_settings(pos,uid,data)
        elif route=='product':result=billing.save_product(pos,uid,data)
        elif route=='income':result=billing.draft_income(pos,uid,data)
        elif route=='payment':result=billing.draft_payment(pos,uid,data)
        elif route=='refund':result=billing.draft_refund(pos,uid,data)
        elif route in ('submit','abandon','retry','cancel'):
            did=integer(data.get('id'),'Documento',1)
            function={'submit':billing.enqueue,'abandon':billing.abandon,'retry':billing.retry_unknown,'cancel':billing.request_cancel}[route]
            result=function(pos,uid,did,data) if route in ('retry','cancel') else function(pos,uid,did)
            if service:service.wake.set()
        elif route in ('check','reconcile'):
            if not service:raise Error('Abre la versión de escritorio para comprobar el proveedor',503)
            if route=='check':result=service.check()
            else:
                did=integer(data.get('id'),'Documento',1);doc=billing.detail(pos,uid,did)
                if doc['state'] not in ('unknown','issued','cancel_pending','cancelled'):raise Error('Este documento no necesita consulta del resultado')
                result=service.request_reconcile(did)
        else:raise Error('Ruta fiscal inexistente',404)
    return handler.send(200,result)
