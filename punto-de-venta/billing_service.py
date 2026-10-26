"""Timbrado fuera del bloqueo del mostrador; resultados ambiguos nunca se duplican."""
import base64,json,queue,threading,re,datetime as dt
from decimal import Decimal
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from core import Error,integer
from local_secret import reveal
from billing_math import load,dump
import billing
from billing_provider import FacturamaSandbox,ProviderError
CFDI='{http://www.sat.gob.mx/cfd/4}';TFD='{http://www.sat.gob.mx/TimbreFiscalDigital}'
def verify_xml(raw,document,cfg,response_uuid=None):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise Error('XML con declaraciones no permitidas')
    try:root=ET.fromstring(raw,forbid_dtd=True)
    except (ET.ParseError,DefusedXmlException):raise Error('XML fiscal ilegible o con declaraciones no permitidas')
    if root.tag!=CFDI+'Comprobante' or root.get('Version')!='4.0' or root.get('TipoDeComprobante')!=document['kind']:raise Error('El XML no corresponde al CFDI 4.0 solicitado')
    body=load(document['payload_json']);emitter=root.find(CFDI+'Emisor');recipient=root.find(CFDI+'Receptor');stamp=root.find('.//'+TFD+'TimbreFiscalDigital')
    if emitter is None or recipient is None or stamp is None:raise Error('El XML no contiene emisor, receptor o timbre')
    if emitter.get('Rfc','').upper()!=document['issuer_rfc'] or recipient.get('Rfc','').upper()!=body['Receiver']['Rfc']:raise Error('El RFC del XML no coincide con el documento solicitado')
    normalize=lambda value:' '.join(str(value or '').upper().split())
    if normalize(emitter.get('Nombre'))!=normalize(cfg['issuer_name']) or emitter.get('RegimenFiscal')!=cfg['fiscal_regime']:raise Error('Los datos fiscales del emisor no coinciden con la configuración')
    for attr,key in [('Nombre','Name'),('RegimenFiscalReceptor','FiscalRegime'),('DomicilioFiscalReceptor','TaxZipCode'),('UsoCFDI','CfdiUse')]:
        if normalize(recipient.get(attr))!=normalize(body['Receiver'][key]):raise Error('Los datos fiscales del receptor no coinciden')
    if root.get('Folio')!=str(body['Folio']) or root.get('Serie','')!=body['Serie'] or root.get('LugarExpedicion')!=body['ExpeditionPlace']:raise Error('Folio, serie o lugar de expedición no coinciden')
    try:total=Decimal(root.get('Total','NaN'))
    except Exception:raise Error('Total fiscal inválido')
    if not total.is_finite() or total*100!=document['expected_cents']:raise Error('El total del XML no coincide con el importe esperado')
    expected_currency='XXX' if document['kind']=='P' else 'MXN'
    if root.get('Moneda')!=expected_currency:raise Error('La moneda del XML no coincide')
    if document['kind']=='I' and root.get('MetodoPago')!=body['PaymentMethod']:raise Error('El método de pago fiscal no coincide')
    if document['kind'] in ('I','E') and root.get('FormaPago')!=body['PaymentForm']:raise Error('La forma de pago fiscal no coincide')
    if root.get('Fecha')!=body['Date']:raise Error('La fecha del XML cambió respecto de la solicitud original')
    uid=stamp.get('UUID','').lower()
    if not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',uid) or stamp.get('Version')!='1.1' or not all(stamp.get(k) for k in ('SelloSAT','SelloCFD','NoCertificadoSAT','FechaTimbrado','RfcProvCertif')):raise Error('El XML no tiene un timbre completo')
    if response_uuid and str(response_uuid).lower()!=uid:raise Error('El UUID del XML no coincide con la respuesta del proveedor')
    if document['kind']=='P':
        pagos=root.find('.//{http://www.sat.gob.mx/Pagos20}Pagos')
        if pagos is None or pagos.get('Version')!='2.0':raise Error('Falta el complemento de pagos 2.0')
        expected=body['Complemento']['Payments'][0];pay=pagos.find('{http://www.sat.gob.mx/Pagos20}Pago')
        if pay is None or Decimal(pay.get('Monto','-1'))!=expected['Amount']:raise Error('El monto del pago no coincide con el abono aplicado')
        related=pay.findall('{http://www.sat.gob.mx/Pagos20}DoctoRelacionado')
        if len(related)!=len(expected['RelatedDocuments']):raise Error('No coinciden los documentos relacionados del abono')
        actual={r.get('IdDocumento','').lower():r for r in related}
        for r in expected['RelatedDocuments']:
            node=actual.get(r['Uuid'].lower())
            if node is None or int(node.get('NumParcialidad','0'))!=r['PartialityNumber']:raise Error('UUID o número de parcialidad incorrecto')
            for field,key in [('ImpSaldoAnt','PreviousBalanceAmount'),('ImpPagado','AmountPaid'),('ImpSaldoInsoluto','ImpSaldoInsoluto')]:
                if Decimal(node.get(field,'-1'))!=r[key]:raise Error('Saldo fiscal incorrecto en el complemento')
    return uid

class BillingService:
    def __init__(self,pos,client_factory=FacturamaSandbox):
        self.pos=pos;self.client_factory=client_factory;self.closed=threading.Event();self.wake=threading.Event();self.tasks=queue.Queue();self.thread=None;self.health='Cuenta de pruebas sin comprobar.'
        with pos.db(True) as db:
            db.execute("UPDATE fiscal_documents SET state='unknown',last_error='El programa se cerró mientras se enviaba. Consulta el resultado antes de reintentar.' WHERE state='sending'")
            db.execute("UPDATE fiscal_documents SET state='cancel_pending',last_error='Cancelación interrumpida; consulta el resultado.' WHERE state='cancel_sending'")
    def client(self,cfg):
        if cfg.get('mode')!='sandbox':raise Error('La emisión real no está habilitada')
        if not cfg.get('credential_blob'):raise Error('Configura las credenciales de pruebas')
        try:credentials=load(reveal(cfg['credential_blob']))
        except Exception:raise Error('Reintroduce las credenciales de pruebas en esta cuenta de Windows') from None
        return self.client_factory(credentials)
    def start(self):
        if self.thread:return
        def run():
            while not self.closed.is_set():
                try:
                    while not self.tasks.empty():
                        kind,did=self.tasks.get_nowait()
                        if kind=='check':
                            with self.pos.db() as db:cfg=billing.configuration(db)
                            self.client(cfg).check();self.health='Cuenta sandbox conectada. Verifica emisor y CSD en el portal del proveedor.'
                        else:self.reconcile(did)
                    self.once()
                except Exception:self.health='No se pudo comprobar la cuenta. Revisa las credenciales y la conexión.'
                self.wake.wait(2);self.wake.clear()
        self.thread=threading.Thread(target=run,daemon=True);self.thread.start()
    def stop(self):
        self.closed.set();self.wake.set()
        if self.thread:self.thread.join(timeout=2)
    def check(self):self.tasks.put(('check',None));self.health='Comprobando cuenta de pruebas…';self.wake.set();return {'message':self.health}
    def request_reconcile(self,did):self.tasks.put(('reconcile',did));self.wake.set();return {'message':'Consulta del resultado en proceso.'}
    def status(self):return {'mode':'sandbox','production_enabled':False,'message':self.health}
    def once(self):
        with self.pos.request_lock,self.pos.db(True) as db:
            row=db.execute("SELECT * FROM fiscal_documents WHERE state='ready' OR (state='cancel_pending' AND json_extract(cancel_request_json,'$.send_requested')=1) ORDER BY id LIMIT 1").fetchone()
            if not row:return
            doc=dict(row);cfg=billing.configuration(db)
            if cfg['revision']!=doc['config_revision']:
                db.execute("UPDATE fiscal_documents SET state=?,last_error='La configuración fiscal cambió; consulta el documento antes de enviar.' WHERE id=?",('unknown' if doc['state']=='ready' else 'cancel_pending',doc['id']));return
            # Cancelaciones pendientes se consultan; solo el pedido nuevo usa DELETE.
            if doc['state']=='cancel_pending':
                request=load(doc['cancel_request_json'] or '{}')
                if not request.get('send_requested'):return
                target='cancel_sending'
            else:target='sending'
            db.execute('UPDATE fiscal_documents SET state=?,attempts=attempts+1 WHERE id=?',(target,doc['id']));billing.event(db,doc['id'],target,{'mode':'sandbox'})
        try:
            client=self.client(cfg)
            if target=='cancel_sending':
                request.pop('send_requested',None);answer=client.cancel(doc['provider_id'],request);self.cancel_result(doc,answer)
            else:
                answer=client.create(load(doc['payload_json']));pid=FacturamaSandbox.identifier(answer.get('Id'))
                doc['provider_id']=pid
                with self.pos.db(True) as db:db.execute('UPDATE fiscal_documents SET provider_id=? WHERE id=?',(pid,doc['id']))
                stamp=(answer.get('Complement') or {}).get('TaxStamp') or {};self.collect(doc,cfg,client,pid,stamp.get('Uuid'))
        except Exception as error:
            state='cancel_pending' if target=='cancel_sending' else 'rejected' if isinstance(error,ProviderError) and error.status in (400,401,403,422) and not doc.get('provider_id') else 'unknown'
            message=str(error) if isinstance(error,(ProviderError,Error)) else 'No se confirmó el resultado. Consulta al proveedor antes de reintentar.'
            with self.pos.db(True) as db:
                current=db.execute('SELECT state FROM fiscal_documents WHERE id=?',(doc['id'],)).fetchone()
                if current and current['state']=='issued':return
                db.execute("UPDATE fiscal_documents SET state=?,last_error=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(state,message,doc['id']))
                if target=='cancel_sending':
                    old=load(doc['cancel_request_json'] or '{}');old['send_requested']=False;db.execute('UPDATE fiscal_documents SET cancel_request_json=? WHERE id=?',(dump(old),doc['id']))
                billing.event(db,doc['id'],'operation.unconfirmed',{'state':state,'message':message})
    def collect(self,doc,cfg,client,pid,response_uuid=None):
        raw=client.download(pid,'xml');uid=verify_xml(raw,doc,cfg,response_uuid)
        with self.pos.request_lock,self.pos.db(True) as db:
            db.execute("UPDATE fiscal_documents SET state='issued',provider_id=?,uuid=?,xml_base64=?,last_error='',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(pid,uid,base64.b64encode(raw).decode(),doc['id']))
            billing.event(db,doc['id'],'sandbox.stamped',{'uuid':uid,'xml_checks':'RFC, total, moneda, folio, tipo y timbre','signature_verification':'Delegada al proveedor; no es verificación criptográfica independiente del SAT'})
        try:
            pdf=client.download(pid,'pdf')
            with self.pos.db(True) as db:db.execute('UPDATE fiscal_documents SET pdf_base64=? WHERE id=?',(base64.b64encode(pdf).decode(),doc['id']))
        except Exception:
            with self.pos.db(True) as db:db.execute("UPDATE fiscal_documents SET last_error='Timbre y XML guardados; PDF pendiente de descargar.' WHERE id=?",(doc['id'],))
    def cancel_result(self,doc,answer):
        status=str(answer.get('Status','')).lower();uid=str(answer.get('Uuid',doc.get('uuid') or '')).lower()
        if doc.get('uuid') and uid!=doc['uuid']:raise Error('El resultado de cancelación corresponde a otro UUID')
        with self.pos.request_lock,self.pos.db(True) as db:
            if status=='canceled':
                ack=answer.get('AcuseXmlBase64')
                if ack:
                    try:
                        raw=base64.b64decode(ack,validate=True)
                        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError()
                        root=ET.fromstring(raw,forbid_dtd=True)
                        values=[str(v).lower() for node in root.iter() for v in list(node.attrib.values())+[node.text or '']]
                        if not any(doc['uuid'] in value for value in values):raise ValueError()
                    except Exception:raise Error('Acuse de cancelación ilegible')
                db.execute("UPDATE fiscal_documents SET state='cancelled',cancel_ack_base64=?,last_error='' WHERE id=?",(ack,doc['id']))
                for table in ('fiscal_sales','fiscal_payments','fiscal_refunds'):db.execute('UPDATE '+table+' SET active=0 WHERE document_id=?',(doc['id'],))
            else:db.execute("UPDATE fiscal_documents SET state=?,last_error=? WHERE id=?",('issued' if status=='active' else 'cancel_pending','El proveedor mantiene el comprobante vigente.' if status=='active' else 'Cancelación pendiente o respuesta no confirmada; consulta el resultado.',doc['id']))
            request=load(doc['cancel_request_json'] or '{}');request['send_requested']=False;db.execute('UPDATE fiscal_documents SET cancel_request_json=? WHERE id=?',(dump(request),doc['id']));billing.event(db,doc['id'],'cancel.result',{'provider_status':status})
    def reconcile(self,did):
        with self.pos.db() as db:
            row=db.execute('SELECT * FROM fiscal_documents WHERE id=?',(did,)).fetchone();cfg=billing.configuration(db)
        if not row:raise Error('Documento inexistente')
        doc=dict(row)
        if doc['config_revision']!=cfg['revision']:raise Error('Recupera este documento con su cuenta original del proveedor')
        client=self.client(cfg);body=load(doc['payload_json']);pid=doc['provider_id']
        try:
            if pid:
                info=client.get(pid)
            else:
                rows=client.lookup(body['Folio'])
                if len(rows)>1:raise Error('El proveedor devolvió más de un resultado. Requiere revisión manual')
                if not rows:
                    with self.pos.db(True) as db:billing.event(db,did,'lookup.notfound',{'folio':body['Folio'],'date':body['Date']})
                    return
                info=rows[0];pid=FacturamaSandbox.identifier(info.get('Id'))
                with self.pos.db(True) as db:db.execute('UPDATE fiscal_documents SET provider_id=? WHERE id=?',(pid,did))
            if str(info.get('Status','')).lower()=='canceled':self.cancel_result(doc,{'Status':'canceled','Uuid':doc.get('uuid') or ''});return
            if doc['state']=='cancel_pending':
                with self.pos.db(True) as db:billing.event(db,did,'cancel.checked',{'status':info.get('Status')})
                return
            self.collect(doc,cfg,client,pid)
        except Exception as error:
            message=str(error) if isinstance(error,(ProviderError,Error)) else 'No se confirmó el documento con el proveedor.'
            with self.pos.db(True) as db:db.execute('UPDATE fiscal_documents SET last_error=? WHERE id=?',(message,did));billing.event(db,did,'lookup.unconfirmed',{'message':message})
