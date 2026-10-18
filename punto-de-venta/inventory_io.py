"""Importación revisable, exportación y respaldo lógico con formato versionado."""
import base64
import binascii
import csv
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import unicodedata
from core import Error, integer, fingerprint, required

HEADERS = ['Codigo','Descripcion','Precio Costo','Precio Venta','Precio Mayoreo','Inventario','Inv. Minimo','Departamento']
TABLES = ['permissions','users','roles','user_roles','role_permissions','user_permissions','categories','suppliers',
 'customers','products','batches','cash_shifts','cash_movements','sales','sale_items','sale_item_batches',
 'sale_payments','prescriptions','returns','return_items','return_allocations','return_payments',
 'inventory_movements','quarantine','audit_log','inventory_imports','promotions','business_branding','business_settings','customer_ledger']
from billing_schema import TABLES as FISCAL_TABLES
TABLES += FISCAL_TABLES
from card_fees import TABLES as FEE_TABLES
TABLES += FEE_TABLES

def file_bytes(data):
    try:
        raw = base64.b64decode(data.get('file_base64',''),validate=True)
    except (ValueError,binascii.Error):
        raise Error('Archivo inválido')
    if not raw or len(raw)>64*1024*1024:
        raise Error('Selecciona un archivo de hasta 64 MB')
    return raw

def decoded(raw):
    if raw.startswith((b'\xd0\xcf\x11\xe0',b'PK\x03\x04')):
        raise Error('Este es un libro Excel binario. Guárdalo como CSV para importarlo. El XLS de texto del sistema anterior sí es compatible.')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('cp1252')

def decimal_value(value, name, money=False):
    text = str(value).strip().replace('$','').replace(',','')
    try:
        value = Decimal(text)
        scaled = value*100 if money else value
        if not scaled.is_finite() or scaled<0 or scaled!=scaled.to_integral_value() or scaled>10**12:
            raise InvalidOperation()
        return int(scaled)
    except InvalidOperation:
        raise Error(f'{name}: valor no válido ({text[:30]})')

def unescape(value):
    # Nuestros CSV anteponen apóstrofo a textos interpretables como fórmulas.
    if value.startswith("'") and value[1:2] in ('=','+','-','@'):
        return value[1:]
    return value

def text_value(value, name, optional=False):
    if not isinstance(value,str) or len(value)>500 or (not optional and not value.strip()):
        raise Error(f'{name}: texto vacío o demasiado largo')
    return value.strip()

def validate_product(p):
    fields = {'barcode':text_value(p.get('barcode'),'Código'), 'name':text_value(p.get('name'),'Descripción'),
      'generic_name':text_value(p.get('generic_name',''),'Sustancia',True),
      'category':text_value(p.get('category','Sin Departamento'),'Departamento')}
    for key,default,maximum in [('cost_cents',0,10**12),('price_cents',0,10**12),('tax_bps',0,10000),
       ('min_stock',0,1000000),('max_stock',100,1000000),('reorder_point',0,1000000),('requires_prescription',0,1),('active',1,1)]:
        fields[key]=integer(p.get(key,default),key,0,maximum)
    if fields['max_stock']<fields['min_stock']:
        raise Error('Stock máximo menor que mínimo')
    batches=p.get('batches',[])
    if not isinstance(batches,list) or len(batches)>10000:
        raise Error('Lotes inválidos')
    fields['batches']=[]
    for batch in batches:
        expiry=batch.get('expires_on') or None
        if expiry:
            try:
                if dt.date.fromisoformat(expiry).isoformat()!=expiry:raise ValueError()
            except (TypeError,ValueError):raise Error('Caducidad inválida')
        received=batch.get('received_at')
        if received is not None:
            try:dt.datetime.fromisoformat(received.replace('Z','+00:00'))
            except (ValueError,TypeError,AttributeError):raise Error('Fecha de recepción inválida')
        fields['batches'].append({'lot_number':text_value(batch.get('lot_number') or 'SIN LOTE CAPTURADO','Lote'),
            'expires_on':expiry,'quantity':integer(batch.get('quantity'),'Existencia',0,1000000),
            'unit_cost_cents':integer(batch.get('unit_cost_cents',fields['cost_cents']),'Costo de lote'),
            'supplier':text_value(batch.get('supplier') or '', 'Proveedor',True),'received_at':received})
    return fields

def parse_file(data):
    raw=file_bytes(data)
    text=decoded(raw)
    mode=data.get('selection','positive')
    if mode not in ('positive','numeric'):raise Error('Selección inválida')
    products,issues=[],[]
    skipped_na=skipped_zero=0
    if text.lstrip().startswith('{'):
        try:document=json.loads(text)
        except ValueError:raise Error('JSON inválido')
        if document.get('format')!='botica-inventory' or document.get('version')!=1:
            raise Error('Para un respaldo completo, usa Restaurar respaldo. Este archivo no es un inventario Botica compatible.')
        source=document.get('products')
        if not isinstance(source,list):raise Error('Lista de productos inválida')
        total=len(source)
        for index,p in enumerate(source,1):
            try:
                item=validate_product(p)
                if mode=='positive' and sum(b['quantity'] for b in item['batches'])==0:
                    skipped_zero+=1
                    continue
                products.append(dict(item,source_row=index))
            except (Error,TypeError,AttributeError) as e:issues.append({'row':index,'message':str(e)})
    else:
        delimiter='\t' if '\t' in text.splitlines()[0] else (';' if ';' in text.splitlines()[0] else ',')
        reader=csv.DictReader(io.StringIO(text),delimiter=delimiter)
        if reader.fieldnames is None or set(HEADERS)-set(h.strip() for h in reader.fieldnames):
            raise Error('Faltan columnas. Se esperan: '+', '.join(HEADERS))
        total=0
        tax=integer(data.get('tax_bps',0),'IVA predeterminado',0,10000)
        for index,row in enumerate(reader,2):
            total+=1
            if total>50000:raise Error('Máximo 50,000 productos por archivo')
            try:
                if None in row:raise Error('Hay más celdas que columnas')
                row={k.strip():unescape((v or '').strip()) for k,v in row.items()}
                if row['Inventario'].upper() in ('N/A','NA',''):
                    skipped_na+=1
                    continue
                qty=decimal_value(row['Inventario'],'Inventario')
                if mode=='positive' and qty==0:
                    skipped_zero+=1
                    continue
                cost=decimal_value(row['Precio Costo'],'Costo',True)
                minimum=decimal_value(row['Inv. Minimo'],'Mínimo')
                item=validate_product({'barcode':row['Codigo'],'name':row['Descripcion'],
                   'category':'Sin Departamento' if row['Departamento'] in ('','- Sin Departamento -') else row['Departamento'],
                   'cost_cents':cost,'price_cents':decimal_value(row['Precio Venta'],'Venta',True),
                   'min_stock':minimum,'max_stock':max(100,minimum),'reorder_point':minimum,'tax_bps':tax,
                   'batches':[{'quantity':qty,'unit_cost_cents':cost,'lot_number':'SIN LOTE CAPTURADO','expires_on':None}] if qty else []})
                products.append(dict(item,source_row=index))
            except Error as e:issues.append({'row':index,'message':str(e)})
    if total>50000:raise Error('Máximo 50,000 productos por archivo')
    seen=set()
    for p in products:
        if p['barcode'] in seen:issues.append({'row':p['source_row'],'message':'Código repetido: '+p['barcode']})
        seen.add(p['barcode'])
    return products,{'source_format':'botica' if text.lstrip().startswith('{') else 'table',
      'rows':total,'candidates':len(products),'skipped_na':skipped_na,'skipped_zero':skipped_zero,
      'issues':issues,'zero_prices':sum(p['price_cents']==0 for p in products),
      'without_expiry':sum(b['quantity'] for p in products for b in p['batches'] if b['expires_on'] is None)}

def revision(db):
    return fingerprint({t:[tuple(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY id')] for t in ('products','batches')})

def preview(pos,uid,data):
    products,summary=parse_file(data)
    with pos.db() as db:
        pos.require(db,uid,'inventory.import')
        existing={r[0] for r in db.execute('SELECT barcode FROM products')}
        summary.update(existing=sum(p['barcode'] in existing for p in products),revision=revision(db))
    summary['new']=summary['candidates']-summary['existing']
    summary['products']=[{'row':p['source_row'],'barcode':p['barcode'],'name':p['name'],
        'price_cents':p['price_cents'],'quantity':sum(b['quantity'] for b in p['batches']),
        'category':p['category'],'existing':p['barcode'] in existing} for p in products]
    return summary

def import_inventory(pos,uid,data):
    products,summary=parse_file(data)
    if summary['issues'] and data.get('skip_invalid') is not True:
        raise Error('Corrige las filas con errores o selecciona omitirlas antes de importar')
    omitted=data.get('excluded_rows',[])
    if not isinstance(omitted,list) or any(type(r) is not int for r in omitted):raise Error('Selección de filas inválida')
    invalid={issue['row'] for issue in summary['issues']}
    excluded=set(omitted)|invalid
    products=[p for p in products if p['source_row'] not in excluded]
    if not products:raise Error('No hay productos seleccionados')
    strategy=data.get('existing','skip')
    if strategy not in ('skip','replace'):raise Error('Tratamiento de existentes inválido')
    key=required(data,'request_key')
    digest=fingerprint(data)
    with pos.db(True) as db:
        pos.require(db,uid,'inventory.import')
        old=db.execute('SELECT * FROM inventory_imports WHERE request_key=?',(key,)).fetchone()
        if old:
            if old['user_id']!=uid or old['request_hash']!=digest:
                raise Error('Clave de importación reutilizada',409)
            return json.loads(old['result_json'])
        if revision(db)!=data.get('revision'):
            raise Error('El inventario cambió. Vuelve a revisar el archivo antes de confirmar.',409)
        if strategy=='replace' and db.execute('SELECT 1 FROM cash_shifts WHERE closed_at IS NULL').fetchone():
            raise Error('Cierra los turnos antes de sustituir existencias. También puedes omitir códigos existentes.',409)
        result={'created':0,'updated':0,'skipped':0,'units':0}
        columns=['barcode','name','generic_name','cost_cents','price_cents','tax_bps','min_stock','max_stock','reorder_point','requires_prescription','active']
        for p in products:
            existing=db.execute('SELECT * FROM products WHERE barcode=?',(p['barcode'],)).fetchone()
            if existing and strategy=='skip':
                result['skipped']+=1
                continue
            db.execute('INSERT OR IGNORE INTO categories(name) VALUES (?)',(p['category'],))
            cid=db.execute('SELECT id FROM categories WHERE name=?',(p['category'],)).fetchone()[0]
            if existing and summary['source_format']=='table':
                # El archivo anterior no contiene estos campos: nunca borrar
                # la trazabilidad de receta o reactivar una baja por ausencia.
                for field in ('generic_name','requires_prescription','active','reorder_point'):
                    p[field]=existing[field]
                p['max_stock']=max(existing['max_stock'],p['min_stock'])
            values=[p[k] for k in columns]
            if existing:
                pid=existing['id']
                db.execute('UPDATE products SET '+','.join(k+'=?' for k in columns)+',category_id=? WHERE id=?',(*values,cid,pid))
                for b in db.execute('SELECT id,quantity FROM batches WHERE product_id=? AND quantity>0',(pid,)).fetchall():
                    db.execute('UPDATE batches SET quantity=0 WHERE id=?',(b['id'],))
                    db.execute("INSERT INTO inventory_movements(batch_id,user_id,quantity_delta,kind,reason) VALUES (?,?,?,'adjustment','Sustitución de inventario por importación')",(b['id'],uid,-b['quantity']))
                result['updated']+=1
            else:
                pid=db.execute('INSERT INTO products('+','.join(columns)+',category_id) VALUES ('+','.join('?' for _ in range(len(columns)+1))+')',(*values,cid)).lastrowid
                result['created']+=1
            for batch in p['batches']:
                supplier=None
                if batch['supplier']:
                    row=db.execute('SELECT id FROM suppliers WHERE business_name=? ORDER BY id LIMIT 1',(batch['supplier'],)).fetchone()
                    supplier=row[0] if row else db.execute('INSERT INTO suppliers(business_name) VALUES (?)',(batch['supplier'],)).lastrowid
                bid=db.execute("INSERT INTO batches(product_id,supplier_id,lot_number,expires_on,quantity,unit_cost_cents,received_at) VALUES (?,?,?,?,?,?,COALESCE(?,strftime('%Y-%m-%dT%H:%M:%fZ','now')))",
                    (pid,supplier,batch['lot_number'],batch['expires_on'],batch['quantity'],batch['unit_cost_cents'],batch['received_at'])).lastrowid
                if batch['quantity']:
                    db.execute("INSERT INTO inventory_movements(batch_id,user_id,quantity_delta,kind,reason) VALUES (?,?,?,'receipt','Inventario inicial importado')",(bid,uid,batch['quantity']))
                result['units']+=batch['quantity']
        db.execute('INSERT INTO inventory_imports(request_key,request_hash,user_id,result_json) VALUES (?,?,?,?)',(key,digest,uid,json.dumps(result)))
        pos.audit(db,uid,'inventory.import',None,result)
        return result

def export_inventory(pos,uid,kind):
    if kind not in ('csv','xls','json'):raise Error('Formato de exportación inválido')
    with pos.db() as db:
        pos.require(db,uid,'inventory.export')
        products=[]
        batches={}
        for b in db.execute("SELECT b.*,COALESCE(s.business_name,'') supplier FROM batches b LEFT JOIN suppliers s ON s.id=b.supplier_id ORDER BY b.id"):
            batches.setdefault(b['product_id'],[]).append({k:b[k] for k in ('lot_number','expires_on','quantity','unit_cost_cents','supplier','received_at')})
        for row in db.execute('SELECT p.*,c.name category FROM products p JOIN categories c ON c.id=p.category_id ORDER BY p.id'):
            p={k:row[k] for k in row.keys() if k not in ('id','category_id')}
            p['batches']=batches.get(row['id'],[])
            products.append(p)
    date=dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    if kind=='json':
        content=json.dumps({'format':'botica-inventory','version':1,'products':products},ensure_ascii=False,indent=2).encode()
        return content,f'inventario-{date}.botica-inventario.json','application/json'
    out=io.StringIO(newline='')
    writer=csv.writer(out,delimiter='\t' if kind=='xls' else ',')
    writer.writerow(HEADERS)
    def safe(value):
        value=str(value)
        return "'"+value if value.startswith(('=','+','-','@','\t','\r','\n')) else value
    for p in products:
        if not p['active']:continue
        writer.writerow([safe(p['barcode']),safe(p['name']),f"{p['cost_cents']/100:.2f}",f"{p['price_cents']/100:.2f}",'0.00',
            sum(b['quantity'] for b in p['batches']),p['min_stock'],safe(p['category'])])
    return out.getvalue().encode('utf-8-sig'),f'inventario-{date}.{kind}','text/tab-separated-values' if kind=='xls' else 'text/csv'

def backup(pos,uid):
    with pos.db() as db:
        pos.require(db,uid,'backup.manage')
        return backup_document(db)

def backup_document(db):
        tables={name:[dict(r) for r in db.execute('SELECT * FROM '+name)] for name in TABLES}
        document={'format':'botica-backup','version':10,'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'tables':tables}
        document['sha256']=fingerprint(document)
        return json.dumps(document,ensure_ascii=False,separators=(',',':')).encode(),f'respaldo-{dt.datetime.now():%Y%m%d-%H%M%S}.botica.json','application/json'

def read_backup(data):
    try:document=json.loads(file_bytes(data).decode('utf-8-sig'))
    except (ValueError,UnicodeError):raise Error('Respaldo ilegible')
    if not isinstance(document,dict) or document.get('format')!='botica-backup' or document.get('version') not in (2,3,4,5,6,7,8,9,10):
        raise Error('Selecciona un respaldo completo Botica compatible (.botica.json)')
    digest=document.pop('sha256',None)
    if digest!=fingerprint(document):raise Error('El respaldo está incompleto o fue modificado; no coincide su verificación')
    tables=document.get('tables')
    if document['version']<10 and isinstance(tables,dict):
        for name in ('customers','suppliers'):
            for row in tables.get(name,[]):row.setdefault('active',1)
    if document['version']<9 and isinstance(tables,dict):
        for name in FEE_TABLES:tables.setdefault(name,[])
    if document['version']<8 and isinstance(tables,dict):
        for name in FISCAL_TABLES:tables.setdefault(name,[])
    if document['version']<7 and isinstance(tables,dict):tables.setdefault('customer_ledger',[])
    if document['version']<6 and isinstance(tables,dict):tables.setdefault('business_settings',[])
    if document['version']<5 and isinstance(tables,dict):tables.setdefault('business_branding',[])
    if document['version']==2 and isinstance(tables,dict) and set(tables)==set(TABLES)-{'promotions'}:
        tables['promotions']=[]
    if not isinstance(tables,dict) or set(tables)!=set(TABLES):raise Error('Tablas de respaldo incompletas')
    if any(not isinstance(rows,list) for rows in tables.values()):raise Error('Datos del respaldo inválidos')
    if document['version']<4:
        for row in tables['promotions']:
            if isinstance(row,dict):
                row.setdefault('schedule_type','temporary');row.setdefault('weekday_mask',127);row.setdefault('bundle_quantity',1)
    from branding import validate
    for row in tables['business_branding']:
        if not isinstance(row,dict):raise Error('Logotipo inválido en respaldo')
        validate(row.get('png_base64'))
    return document

def empty_for_restore(db):
    return not any(db.execute('SELECT 1 FROM '+name+' LIMIT 1').fetchone() for name in
        ('products','suppliers','customers','cash_shifts','sales','inventory_imports'))

def restore_preview(pos,uid,data):
    document=read_backup(data)
    with pos.db() as db:
        pos.require(db,uid,'backup.manage')
        eligible=empty_for_restore(db)
    return {'eligible':eligible,'created_at':document['created_at'],
       'counts':{name:len(document['tables'][name]) for name in ('products','batches','sales','users','customers','customer_ledger','cash_shifts')}}

def restore(pos,uid,data):
    document=read_backup(data)
    if data.get('confirmation')!='RESTAURAR':raise Error('Escribe RESTAURAR para confirmar')
    with pos.db(True) as db:
        pos.require(db,uid,'backup.manage')
        if not empty_for_restore(db):
            raise Error('Restaura en una instalación vacía, sin productos, proveedores, clientes ni turnos. La base actual no se sustituirá.',409)
        # Solo tablas y columnas del esquema local; jamás se ejecuta SQL del archivo.
        for name in TABLES:
            columns={r['name'] for r in db.execute('PRAGMA table_info('+name+')')}
            for row in document['tables'][name]:
                if not isinstance(row,dict) or set(row)!=columns:
                    raise Error('Estructura no válida en '+name)
                if any(isinstance(v,(dict,list)) for v in row.values()):
                    raise Error('Dato no válido en '+name)
        # Conserva las restricciones; se difieren las relaciones hasta el COMMIT.
        db.execute('PRAGMA defer_foreign_keys=ON')
        triggers=list(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
        for t in triggers:db.execute('DROP TRIGGER "'+t['name']+'"')
        db.execute('DELETE FROM sessions')
        db.execute('DELETE FROM login_attempts')
        for name in reversed(TABLES):db.execute('DELETE FROM '+name)
        for name in TABLES:
            rows=document['tables'][name]
            if not rows:continue
            columns=list(rows[0])
            db.executemany('INSERT INTO '+name+'('+','.join('"'+c+'"' for c in columns)+') VALUES ('+','.join('?' for _ in columns)+')',
                [tuple(r[c] for c in columns) for r in rows])
        for t in triggers:db.execute(t['sql'])
        if db.execute('PRAGMA foreign_key_check').fetchone():
            raise Error('El respaldo contiene relaciones inconsistentes')
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise Error('No se pudo verificar la base restaurada')
        if not any('backup.manage' in pos.permissions(db,u['id']) for u in db.execute('SELECT id FROM users WHERE active=1').fetchall()):
            raise Error('El respaldo no contiene un administrador activo con acceso a respaldos')
        for code,label in [('billing.issue','Crear y emitir facturas de prueba'),('billing.manage','Configurar facturación y gestionar cancelaciones')]:
            db.execute('INSERT OR IGNORE INTO permissions VALUES (?,?)',(code,label))
            db.execute("INSERT OR IGNORE INTO role_permissions SELECT id,? FROM roles WHERE name='Administrador'",(code,))
        # El usuario que autorizó en la base vacía puede no existir en el respaldo.
        pos.audit(db,None,'backup.restore',None,{'created_at':document['created_at']})
    return {'restored':True,'products':len(document['tables']['products']),'sales':len(document['tables']['sales'])}
