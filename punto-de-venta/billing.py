"""Borradores fiscales y cola durable. Emisión real desactivada en esta versión."""
import datetime as dt,json,re,secrets,hashlib
from decimal import Decimal
from core import Error,integer,password_hash,password_matches
from local_secret import protect,reveal
from billing_math import receiver,rfc,item,common,dump,load,q2,q6,proportional_taxes

ACTIVE=('draft','ready','sending','unknown','issued','cancel_pending','cancel_sending')
def authorized(pos,db,uid,manage=False):
    if manage:pos.require(db,uid,'billing.manage')
    elif not pos.permissions(db,uid).intersection({'billing.issue','billing.manage'}):raise Error('No tienes permiso de facturación',403)
def event(db,doc,action,details):db.execute('INSERT INTO fiscal_events(document_id,action,details) VALUES(?,?,?)',(doc,action,dump(details)))
def configuration(db):
    row=db.execute('SELECT * FROM fiscal_config WHERE id=1').fetchone()
    if not row:raise Error('Primero configura la facturación de pruebas')
    return {**json.loads(row['settings_json']),'revision':row['revision'],'credential_blob':row['credential_blob']}
def settings(pos,uid):
    with pos.db() as db:
        authorized(pos,db,uid,True)
        row=db.execute('SELECT * FROM fiscal_config WHERE id=1').fetchone()
        public=json.loads(row['settings_json']) if row else {};public.pop('credential_check',None)
        return {'production_enabled':False,'mode':'sandbox',**public,'credentials_saved':bool(row and row['credential_blob'])}
def save_settings(pos,uid,data):
    if data.get('mode','sandbox')!='sandbox' or data.get('production_enabled'):raise Error('La emisión real está bloqueada hasta validar el PAC y la configuración fiscal',403)
    config={'mode':'sandbox','provider':'facturama','issuer_rfc':rfc(data.get('issuer_rfc')),'issuer_name':str(data.get('issuer_name','')).strip().upper(),
            'fiscal_regime':str(data.get('fiscal_regime','')),'postal_code':str(data.get('postal_code','')),'series':str(data.get('series','PRUEBA')).upper()}
    if not config['issuer_name'] or len(config['issuer_name'])>254 or not re.fullmatch(r'\d{3}',config['fiscal_regime']) or not re.fullmatch(r'\d{5}',config['postal_code']) or not re.fullmatch(r'[A-Z0-9]{1,10}',config['series']):raise Error('Revisa el nombre fiscal, régimen, código postal y serie (1 a 10 letras/números)')
    with pos.db(True) as db:
        authorized(pos,db,uid,True)
        old=db.execute('SELECT * FROM fiscal_config WHERE id=1').fetchone();blob=old['credential_blob'] if old else None
        old_config=json.loads(old['settings_json']) if old else {};old_check=old_config.pop('credential_check',None)
        same_credentials=False
        if data.get('username') or data.get('password'):
            username=str(data.get('username','')).strip();secret=str(data.get('password',''))
            if not username or ':' in username or len(username)>200 or not secret or len(secret)>300:raise Error('Indica usuario y contraseña de la cuenta sandbox de Facturama')
            credentials=dump({'username':username,'password':secret});same_credentials=bool(old_check and password_matches(credentials,old_check))
            blob=protect(credentials);config['credential_check']=old_check if same_credentials else password_hash(credentials)
        elif old_check:config['credential_check']=old_check
        if not data.get('username') and not data.get('password') and not data.get('forget_credentials'):same_credentials=True
        unchanged={k:v for k,v in config.items() if k!='credential_check'}==old_config
        if db.execute("SELECT 1 FROM fiscal_documents WHERE state IN('ready','sending','unknown','cancel_pending','cancel_sending')").fetchone() and not (unchanged and same_credentials and not data.get('forget_credentials')):raise Error('Resuelve primero los documentos en proceso. Solo se permite reintroducir exactamente las mismas credenciales para recuperar el acceso',409)
        if data.get('forget_credentials'):blob=None
        revision=old['revision'] if old and unchanged and same_credentials else (old['revision']+1) if old else 1
        db.execute('INSERT INTO fiscal_config VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET settings_json=excluded.settings_json,credential_blob=excluded.credential_blob,revision=excluded.revision',(dump(config),blob,revision))
        pos.audit(db,uid,'billing.settings',None,{'mode':'sandbox','issuer_rfc':config['issuer_rfc'],'revision':revision})
    return settings(pos,uid)
def products(pos,uid,q=''):
    with pos.db() as db:
        authorized(pos,db,uid,True)
        return [dict(r) for r in db.execute('''SELECT p.id,p.name,p.barcode,p.tax_bps AS sale_tax_bps,f.product_code,f.unit_code,f.tax_object,f.tax_factor,f.tax_bps,f.reviewed
            FROM products p LEFT JOIN fiscal_products f ON f.product_id=p.id WHERE p.active=1 AND (p.name LIKE ? OR p.barcode=?) ORDER BY p.name LIMIT 100''',('%'+q[:100]+'%',q[:100]))]
def save_product(pos,uid,data):
    pid=integer(data.get('product_id'),'Producto',1);code=str(data.get('product_code',''));unit=str(data.get('unit_code','')).upper();obj=str(data.get('tax_object',''));factor=data.get('tax_factor');tax=integer(data.get('tax_bps'),'IVA',0,1600)
    if not re.fullmatch(r'\d{8}',code) or not re.fullmatch(r'[A-Z0-9]{2,3}',unit) or obj not in ('01','02') or factor not in ('Tasa','Exento') or tax not in (0,800,1600) or ((obj=='01' or factor=='Exento') and tax!=0):raise Error('Revisa las claves SAT y tratamiento de IVA')
    if data.get('reviewed') is not True:raise Error('Confirma que revisaste la clasificación fiscal de este producto')
    with pos.db(True) as db:
        authorized(pos,db,uid,True)
        p=db.execute('SELECT tax_bps FROM products WHERE id=?',(pid,)).fetchone()
        if not p:raise Error('Producto inexistente',404)
        if p[0]!=tax:raise Error('Primero ajusta el IVA del producto en Editar producto. La facturación no cambiará sus precios o impuestos silenciosamente')
        db.execute('INSERT INTO fiscal_products VALUES(?,?,?,?,?,?,1) ON CONFLICT(product_id) DO UPDATE SET product_code=excluded.product_code,unit_code=excluded.unit_code,tax_object=excluded.tax_object,tax_factor=excluded.tax_factor,tax_bps=excluded.tax_bps,reviewed=1',(pid,code,unit,obj,factor,tax))
        pos.audit(db,uid,'billing.product',pid,{'product_code':code,'unit_code':unit,'tax_object':obj,'tax_factor':factor,'tax_bps':tax})
    return {'ok':True}
def payment_form(db,sales,data):
    totals={}
    for sid in sales:
        for row in db.execute('SELECT method,amount_cents FROM sale_payments WHERE sale_id=?',(sid,)):totals[row['method']]=totals.get(row['method'],0)+row['amount_cents']
    if not totals:raise Error('No hay pagos de esta venta para definir la forma fiscal')
    method=max(totals,key=totals.get)
    if method in ('debit','credit'):
        form=data.get('card_form')
        if form not in ('04','28'):raise Error('Confirma si la tarjeta utilizada fue de crédito (04) o débito (28)')
        return form
    return {'cash':'01','transfer':'03'}[method]
def create_record(db,uid,cfg,key,request_hash,payload,total,kind,receiver_data):
    old=db.execute('SELECT id,request_hash FROM fiscal_documents WHERE request_key=?',(key,)).fetchone()
    if old:
        if old['request_hash']!=request_hash:raise Error('Clave de borrador reutilizada con otros datos',409)
        return old['id'],False
    did=db.execute("INSERT INTO fiscal_documents(request_key,request_hash,kind,mode,state,user_id,config_revision,issuer_rfc,receiver_json,payload_json,expected_cents) VALUES(?,?,?,'sandbox','draft',?,?,?,?,?,?)",(key,request_hash,kind,uid,cfg['revision'],cfg['issuer_rfc'],dump(receiver_data),dump(payload),total)).lastrowid
    event(db,did,'draft.created',{'kind':kind,'mode':'sandbox','expected_cents':total});return did,True
def request_identity(data):
    key=str(data.get('request_key',''))
    if not key or len(key)>100:raise Error('Falta identificador de la solicitud')
    return key,hashlib.sha256(dump(data).encode()).hexdigest()
def existing_request(db,key,digest):
    old=db.execute('SELECT id,request_hash FROM fiscal_documents WHERE request_key=?',(key,)).fetchone()
    if old:
        if old['request_hash']!=digest:raise Error('Solicitud de facturación reutilizada',409)
        return old['id']
def draft_income(pos,uid,data):
    key,digest=request_identity(data)
    with pos.db(True) as db:
        authorized(pos,db,uid);cfg=configuration(db)
        if old:=existing_request(db,key,digest):return {'id':old}
        global_invoice=data.get('global') is True
        ids=data.get('sale_ids') if global_invoice else [data.get('sale_id')]
        if not isinstance(ids,list) or not 1<=len(ids)<=200 or len(set(ids))!=len(ids):raise Error('Selecciona de 1 a 200 tickets distintos')
        ids=[integer(s,'Ticket',1) for s in ids];sales=[];items=[]
        for sid in ids:
            s=db.execute('SELECT * FROM sales WHERE id=?',(sid,)).fetchone()
            if not s or s['status']!='completed':raise Error('El ticket no existe o tiene devolución/anulación; requiere revisión fiscal')
            if db.execute('SELECT 1 FROM fiscal_sales WHERE sale_id=? AND active=1',(sid,)).fetchone():raise Error('El ticket ya está reservado o facturado. No se duplicará',409)
            on_account=bool(db.execute('SELECT 1 FROM customer_ledger WHERE sale_id=?',(sid,)).fetchone())
            if global_invoice and on_account:raise Error('Los créditos se facturan individualmente con PPD; no se incluyen automáticamente en la global')
            sales.append(dict(s,on_account=on_account))
            for row in db.execute('SELECT * FROM sale_items WHERE sale_id=? ORDER BY id',(sid,)):
                mapping=db.execute('SELECT * FROM fiscal_products WHERE product_id=?',(row['product_id'],)).fetchone()
                concept=item(row,mapping)
                if global_invoice:
                    concept.update(ProductCode='01010101',UnitCode='ACT',Description='Venta ticket '+str(sid),IdentificationNumber=str(sid),Quantity=Decimal(1),UnitPrice=concept['Subtotal'])
                items.append(concept)
        total=sum(s['total_cents'] for s in sales)
        if int(q2(sum((i['Total'] for i in items),Decimal(0)))*100)!=total:raise Error('La suma fiscal no coincide con los tickets. Revisa los redondeos antes de emitir')
        recipient=receiver(data.get('receiver',{})) if not global_invoice else {'Rfc':'XAXX010101000','Name':'PUBLICO EN GENERAL','FiscalRegime':'616','TaxZipCode':cfg['postal_code'],'CfdiUse':'S01'}
        if not global_invoice and recipient['Rfc'] in ('XAXX010101000','XEXX010101000'):raise Error('Usa Factura global para público en general. Receptores extranjeros requieren otra configuración fiscal')
        payload=common(cfg,secrets.token_hex(16));payload.update(Currency='MXN',Exportation='01',Receiver=recipient,Items=items)
        payload.update(PaymentMethod='PPD' if sales[0]['on_account'] else 'PUE',PaymentForm='99' if sales[0]['on_account'] else payment_form(db,ids,data))
        if global_invoice:
            start=str(data.get('from',''));end=str(data.get('to',''))
            try:a=dt.date.fromisoformat(start);b=dt.date.fromisoformat(end)
            except ValueError:raise Error('Indica el periodo de la factura global')
            if a>b or a.month!=b.month or a.year!=b.year or b>dt.date.today():raise Error('La global de prueba admite un periodo dentro del mismo mes, sin fechas futuras')
            for sid in ids:
                day=db.execute("SELECT date(created_at,'localtime') FROM sales WHERE id=?",(sid,)).fetchone()[0]
                if not start<=day<=end:raise Error('Hay un ticket fuera del periodo seleccionado')
            periodicity=str(data.get('periodicity','01'))
            if periodicity not in ('01','02','03','04') or (periodicity=='01' and a!=b):raise Error('Revisa la periodicidad de la global')
            payload['GlobalInformation']={'Periodicity':periodicity,'Months':f'{a.month:02}','Year':str(a.year)};payload['NameId']='34'
        did,new=create_record(db,uid,cfg,key,digest,payload,total,'I',recipient)
        if new:
            db.executemany('INSERT INTO fiscal_sales(document_id,sale_id) VALUES(?,?)',[(did,sid) for sid in ids]);pos.audit(db,uid,'billing.draft',did,{'kind':'I','tickets':ids,'mode':'sandbox'})
    return {'id':did}
def allocations(db,customer_id):
    queue=[];result=[];counts={}
    for l in db.execute('SELECT * FROM customer_ledger WHERE customer_id=? ORDER BY id',(customer_id,)):
        if l['amount_cents']>0:queue.append({'sale_id':l['sale_id'],'remaining':l['amount_cents']})
        else:
            left=-l['amount_cents']
            for s in queue:
                if left<=0:break
                take=min(left,s['remaining'])
                if not take:continue
                counts[s['sale_id']]=counts.get(s['sale_id'],0)+1
                result.append(dict(ledger_id=l['id'],sale_id=s['sale_id'],amount_cents=take,previous_cents=s['remaining'],balance_cents=s['remaining']-take,partiality=counts[s['sale_id']],method=l['method'],received_at=l['created_at']))
                left-=take;s['remaining']-=take
            if left:raise Error('El abono no puede asignarse íntegramente a las compras registradas')
    return result
def draft_payment(pos,uid,data):
    key,digest=request_identity(data);lid=integer(data.get('ledger_id'),'Abono',1)
    with pos.db(True) as db:
        authorized(pos,db,uid);cfg=configuration(db)
        if old:=existing_request(db,key,digest):return {'id':old}
        ledger=db.execute('SELECT * FROM customer_ledger WHERE id=? AND amount_cents<0',(lid,)).fetchone()
        if not ledger:raise Error('Selecciona un abono registrado, no el dinero recibido antes del cambio')
        all_parts=allocations(db,ledger['customer_id']);parts=[a for a in all_parts if a['ledger_id']==lid];related=[];links=[];recipients=[]
        for a in parts:
            original=db.execute("SELECT d.* FROM fiscal_documents d JOIN fiscal_sales f ON f.document_id=d.id WHERE f.sale_id=? AND f.active=1 AND d.kind='I' AND d.state='issued'",(a['sale_id'],)).fetchone()
            if not original:raise Error('Primero timbra la factura PPD del ticket #'+str(a['sale_id']))
            if original['issuer_rfc']!=cfg['issuer_rfc']:raise Error('El abono corresponde a otro emisor fiscal')
            body=load(original['payload_json'])
            if body['PaymentMethod']!='PPD':raise Error('El documento original no es una factura PPD')
            if db.execute('SELECT 1 FROM fiscal_payments WHERE ledger_id=? AND income_document_id=? AND active=1',(lid,original['id'])).fetchone():raise Error('El abono ya tiene complemento o borrador reservado',409)
            for previous in (p for p in all_parts if p['sale_id']==a['sale_id'] and p['ledger_id']<lid):
                if not db.execute("SELECT 1 FROM fiscal_payments p JOIN fiscal_documents d ON d.id=p.document_id WHERE p.ledger_id=? AND p.income_document_id=? AND p.active=1 AND d.state='issued'",(previous['ledger_id'],original['id'])).fetchone():raise Error('Primero resuelve los complementos de los abonos anteriores de este ticket')
            recipients.append(body['Receiver'])
            related.append({'Uuid':original['uuid'],'Serie':body['Serie'],'Folio':body['Folio'],'Currency':'MXN','EquivalenceDocRel':1,
                'PartialityNumber':a['partiality'],'PreviousBalanceAmount':Decimal(a['previous_cents'])/100,'AmountPaid':Decimal(a['amount_cents'])/100,'ImpSaldoInsoluto':Decimal(a['balance_cents'])/100,
                'TaxObject':'02' if any(i['TaxObject']=='02' for i in body['Items']) else '01','Taxes':proportional_taxes(body['Items'],a['amount_cents'],a['previous_cents'],original['expected_cents'])})
            links.append((lid,original['id'],a['amount_cents'],a['previous_cents'],a['balance_cents'],a['partiality']))
        if not parts or sum(p['amount_cents'] for p in parts)!=-ledger['amount_cents']:raise Error('La asignación fiscal no coincide con el abono aplicado')
        if len({dump(receiver(r,True)) for r in recipients})!=1:raise Error('El abono abarca receptores fiscales diferentes; requiere revisión antes de emitir')
        method=ledger['method'];form={'cash':'01','transfer':'03'}.get(method,data.get('card_form'))
        if method=='debit' and form not in ('04','28'):raise Error('Confirma crédito o débito para el abono con tarjeta')
        recipient=receiver(recipients[0],True);payload=common(cfg,secrets.token_hex(16),'P');payload['Receiver']=recipient
        date=db.execute("SELECT datetime(created_at,'localtime') FROM customer_ledger WHERE id=?",(lid,)).fetchone()[0].replace(' ','T')
        payload['Complemento']={'Payments':[{'Currency':'MXN','Date':date,'PaymentForm':form,'Amount':Decimal(-ledger['amount_cents'])/100,'RelatedDocuments':related}]}
        did,new=create_record(db,uid,cfg,key,digest,payload,0,'P',recipient)
        if new:db.executemany('INSERT INTO fiscal_payments VALUES(?,?,?,?,?,?,?,1)',[(did,*p) for p in links])
    return {'id':did}
def list_documents(pos,uid):
    with pos.db() as db:
        authorized(pos,db,uid)
        docs=[dict(r) for r in db.execute('SELECT id,kind,mode,state,expected_cents,provider_id,uuid,last_error,created_at,updated_at FROM fiscal_documents ORDER BY id DESC LIMIT 200')]
        for d in docs:d['operational_review']=bool(db.execute("SELECT 1 FROM fiscal_sales f JOIN sales s ON s.id=f.sale_id WHERE f.document_id=? AND s.status!='completed'",(d['id'],)).fetchone())
        return docs
def detail(pos,uid,did):
    with pos.db() as db:
        authorized(pos,db,uid);r=db.execute('SELECT * FROM fiscal_documents WHERE id=?',(did,)).fetchone()
        if not r:raise Error('Documento fiscal inexistente',404)
        return {'id':r['id'],'kind':r['kind'],'state':r['state'],'mode':'sandbox','expected_cents':r['expected_cents'],'uuid':r['uuid'],'last_error':r['last_error'],'payload':json.loads(r['payload_json']),
                'events':[dict(e) for e in db.execute('SELECT action,details,created_at FROM fiscal_events WHERE document_id=? ORDER BY id',(did,))]}
def enqueue(pos,uid,did):
    with pos.db(True) as db:
        authorized(pos,db,uid);cfg=configuration(db);d=db.execute('SELECT * FROM fiscal_documents WHERE id=?',(did,)).fetchone()
        if not d:raise Error('Documento inexistente',404)
        if d['state'] in ('ready','sending','issued'):return {'id':did,'state':d['state']}
        if d['state'] not in ('draft','rejected'):raise Error('Consulta el resultado pendiente antes de intentar otra emisión',409)
        if not cfg['credential_blob']:raise Error('Configura primero las credenciales sandbox del proveedor')
        if d['config_revision']!=cfg['revision']:raise Error('Cambió la configuración fiscal. Descarta este borrador y prepara uno nuevo')
        created=dt.datetime.fromisoformat(d['created_at'].replace('Z','+00:00'))
        if dt.datetime.now(dt.timezone.utc)-created>dt.timedelta(hours=48):raise Error('El borrador lleva más de 48 horas; revisa su fecha antes de enviarlo')
        if db.execute("SELECT 1 FROM fiscal_sales f JOIN sales s ON s.id=f.sale_id WHERE f.document_id=? AND s.status!='completed'",(did,)).fetchone():raise Error('El ticket cambió por devolución/anulación. Revisa el borrador antes de emitir')
        db.execute("UPDATE fiscal_documents SET state='ready',last_error='' WHERE id=?",(did,));event(db,did,'send.queued',{'by':uid});pos.audit(db,uid,'billing.queue',did,{'mode':'sandbox'})
    return {'id':did,'state':'ready'}
def abandon(pos,uid,did):
    with pos.db(True) as db:
        authorized(pos,db,uid,True);d=db.execute('SELECT state,uuid FROM fiscal_documents WHERE id=?',(did,)).fetchone()
        if not d or d['uuid'] or d['state'] not in ('draft','rejected'):raise Error('Solo se descartan borradores sin timbre ni resultado incierto')
        db.execute("UPDATE fiscal_documents SET state='abandoned' WHERE id=?",(did,))
        for table in ('fiscal_sales','fiscal_payments','fiscal_refunds'):db.execute('UPDATE '+table+' SET active=0 WHERE document_id=?',(did,))
        event(db,did,'draft.abandoned',{'by':uid})
    return {'ok':True}

def retry_unknown(pos,uid,did,data):
    if data.get('confirm_same_request') is not True:raise Error('Confirma el reintento con el mismo folio, fecha y contenido')
    with pos.db(True) as db:
        authorized(pos,db,uid,True);cfg=configuration(db);d=db.execute('SELECT * FROM fiscal_documents WHERE id=?',(did,)).fetchone()
        if not d or d['state']!='unknown' or d['provider_id'] or d['uuid']:raise Error('Recupera el documento existente; no se enviará otra factura')
        if d['config_revision']!=cfg['revision']:raise Error('No se reintenta desde una cuenta fiscal diferente')
        if not db.execute("SELECT 1 FROM fiscal_events WHERE document_id=? AND action='lookup.notfound'",(did,)).fetchone():raise Error('Primero consulta el resultado con el proveedor')
        created=dt.datetime.fromisoformat(d['created_at'].replace('Z','+00:00'))
        if dt.datetime.now(dt.timezone.utc)-created>dt.timedelta(hours=48):raise Error('La fecha del comprobante requiere revisión manual; no se regenerará silenciosamente')
        db.execute("UPDATE fiscal_documents SET state='ready',last_error='' WHERE id=?",(did,));event(db,did,'send.same_request_retry',{'by':uid})
    return {'id':did,'state':'ready'}

def request_cancel(pos,uid,did,data):
    motive=str(data.get('motive',''));replacement=str(data.get('replacement_uuid','')).lower()
    if motive not in ('01','02','03','04'):raise Error('Elige uno de los cuatro motivos SAT de cancelación')
    if motive=='01' and not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',replacement):raise Error('El motivo 01 necesita el UUID del CFDI sustituto ya emitido')
    if motive!='01' and replacement:raise Error('Solo el motivo 01 permite UUID sustituto')
    with pos.db(True) as db:
        authorized(pos,db,uid,True);cfg=configuration(db);d=db.execute('SELECT * FROM fiscal_documents WHERE id=?',(did,)).fetchone()
        if not d or d['state']!='issued' or not d['uuid']:raise Error('Solo se solicita cancelación de un comprobante timbrado y vigente')
        if motive=='01' and replacement==d['uuid']:raise Error('El sustituto no puede ser el mismo UUID')
        if motive=='04' and (d['kind']!='I' or 'GlobalInformation' not in load(d['payload_json'])):raise Error('El motivo 04 corresponde a una operación incluida en una factura global')
        if cfg['revision']!=d['config_revision']:raise Error('Gestiona la cancelación desde la cuenta original del documento')
        if db.execute("SELECT 1 FROM fiscal_payments p JOIN fiscal_documents f ON f.id=p.document_id WHERE p.income_document_id=? AND p.active=1 AND f.state NOT IN('abandoned','cancelled','rejected')",(did,)).fetchone():raise Error('Primero resuelve los complementos de pago relacionados')
        if db.execute("SELECT 1 FROM fiscal_refunds r JOIN fiscal_documents f ON f.id=r.document_id WHERE r.income_document_id=? AND r.active=1 AND f.state NOT IN('abandoned','cancelled','rejected')",(did,)).fetchone():raise Error('Primero resuelve las notas de crédito relacionadas')
        request={'motive':motive,'send_requested':True}
        if replacement:request['uuidReplacement']=replacement
        db.execute("UPDATE fiscal_documents SET state='cancel_pending',cancel_request_json=?,last_error='' WHERE id=?",(dump(request),did));event(db,did,'cancel.requested',{'by':uid,'motive':motive,'replacement':replacement})
    return {'id':did,'state':'cancel_pending'}

def draft_refund(pos,uid,data):
    key,digest=request_identity(data);rid=integer(data.get('return_id'),'Devolución',1)
    with pos.db(True) as db:
        authorized(pos,db,uid);cfg=configuration(db)
        if old:=existing_request(db,key,digest):return {'id':old}
        refund=db.execute('SELECT * FROM returns WHERE id=?',(rid,)).fetchone()
        if not refund or refund['kind']=='void':raise Error('Selecciona una devolución. Una anulación necesita revisión de la cancelación fiscal, no una nota automática')
        original=db.execute("SELECT d.* FROM fiscal_documents d JOIN fiscal_sales f ON f.document_id=d.id WHERE f.sale_id=? AND f.active=1 AND d.state='issued'",(refund['sale_id'],)).fetchone()
        if not original:raise Error('Primero necesita existir la factura original timbrada')
        if original['issuer_rfc']!=cfg['issuer_rfc']:raise Error('La devolución corresponde a otro emisor')
        if db.execute('SELECT 1 FROM fiscal_refunds WHERE return_id=? AND active=1',(rid,)).fetchone():raise Error('Esta devolución ya tiene una nota o borrador reservado',409)
        body=load(original['payload_json']);concepts=[]
        for row in db.execute('''SELECT ri.*,i.product_id FROM return_items ri JOIN sale_items i ON i.id=ri.sale_item_id WHERE ri.return_id=? ORDER BY ri.id''',(rid,)):
            matches=[i for i in body['Items'] if i['IdentificationNumber']==str(row['product_id'])]
            if 'GlobalInformation' in body or len(matches)!=1:raise Error('La devolución en una global o partida repetida requiere revisión fiscal específica')
            src=matches[0];qty=Decimal(row['quantity']);sub=q6(src['UnitPrice']*qty);disc=q6(src['Discount']*qty/src['Quantity']);base=q6(sub-disc);taxes=[]
            for t in src['Taxes']:
                rate=Decimal(t['Rate']);taxes.append({**t,'Base':base,'Total':Decimal(0) if t.get('IsExempt') else q6(base*rate)})
            total=q6(base+sum((t['Total'] for t in taxes),Decimal(0)))
            if q2(total)!=Decimal(row['total_cents'])/100:raise Error('La nota no coincide con el reembolso registrado; revisa los redondeos')
            concepts.append({**src,'Quantity':qty,'Subtotal':sub,'Discount':disc,'Taxes':taxes,'Total':total})
        recipient=body['Receiver'];payload=common(cfg,secrets.token_hex(16),'E');payload.update(Currency='MXN',Exportation='01',PaymentMethod='PUE',PaymentForm=body['PaymentForm'],Receiver=recipient,Items=concepts,Relations={'Type':'01','Cfdis':[{'Uuid':original['uuid']}]})
        if int(q2(sum((i['Total'] for i in concepts),Decimal(0)))*100)!=refund['total_cents']:raise Error('La nota fiscal no coincide con el reembolso')
        did,new=create_record(db,uid,cfg,key,digest,payload,refund['total_cents'],'E',recipient)
        if new:db.execute('INSERT INTO fiscal_refunds VALUES(?,?,?,1)',(did,rid,original['id']))
    return {'id':did}
