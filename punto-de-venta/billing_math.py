"""CFDI 4.0, MXN y cálculos decimales sobre importes históricos del ticket."""
from decimal import Decimal,ROUND_HALF_UP
import datetime as dt,json,re
from core import Error
D=Decimal
def q6(value):return value.quantize(D('0.000001'),rounding=ROUND_HALF_UP)
def q2(value):return value.quantize(D('0.01'),rounding=ROUND_HALF_UP)
def dump(value):
    if isinstance(value,D):
        if not value.is_finite():raise Error('Importe fiscal inválido')
        return format(value,'f')
    if isinstance(value,dict):return '{'+','.join(json.dumps(k,ensure_ascii=False)+':'+dump(v) for k,v in value.items())+'}'
    if isinstance(value,list):return '['+','.join(dump(v) for v in value)+']'
    return json.dumps(value,ensure_ascii=False,allow_nan=False)
def load(value):return json.loads(value,parse_float=D)
def rfc(value):
    value=str(value or '').strip().upper()
    if not re.fullmatch(r'[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}',value):raise Error('RFC: usa el formato de 12 o 13 caracteres del SAT')
    return value
def receiver(data,payment=False):
    result={k:str(data.get(k,'')).strip().upper() for k in ('Rfc','Name','FiscalRegime','TaxZipCode','CfdiUse')}
    result['Rfc']=rfc(result['Rfc'])
    if not result['Name'] or len(result['Name'])>254:raise Error('Indica el nombre fiscal del receptor')
    if not re.fullmatch(r'\d{5}',result['TaxZipCode']) or not re.fullmatch(r'\d{3}',result['FiscalRegime']):raise Error('Revisa el código postal y régimen fiscal del receptor')
    if payment:result['CfdiUse']='CP01'
    elif result['CfdiUse']=='CP01':raise Error('CP01 se utiliza únicamente en complementos de pago')
    if not re.fullmatch(r'[A-Z][0-9]{2}|CP01',result['CfdiUse']):raise Error('Indica el uso CFDI del catálogo SAT')
    return result
def item(row,mapping):
    if not mapping or not mapping['reviewed']:raise Error('Configura y revisa las claves fiscales de '+row['product_name'])
    obj,factor=mapping['tax_object'],mapping['tax_factor'];rate=D(row['tax_bps'])/10000
    if mapping['tax_bps']!=row['tax_bps']:raise Error('La tasa fiscal revisada no coincide con el impuesto histórico del ticket: '+row['product_name'])
    if obj not in ('01','02') or factor not in ('Tasa','Exento'):raise Error('Esta versión necesita revisión para este objeto/factor de impuesto')
    if (obj=='01' or factor=='Exento') and row['tax_bps']!=0:raise Error('El impuesto configurado no coincide con el impuesto histórico del ticket')
    if row['total_cents']==0:raise Error('Una partida con importe cero requiere revisión fiscal; no se timbrará automáticamente')
    qty=D(row['quantity']);gross=D(row['unit_price_cents'])/100;discount=D(row['discount_cents'])/100
    divisor=1+rate if obj=='02' and factor=='Tasa' else D(1)
    unit=q6(gross/divisor);subtotal=q6(unit*qty);disc=q6(discount/divisor);base=q6(subtotal-disc)
    taxes=[]
    if obj=='02':
        tax={'Name':'IVA','Base':base,'Rate':rate if factor=='Tasa' else D(0),'IsRetention':False,'Total':q6(base*rate) if factor=='Tasa' else D(0)}
        if factor=='Exento':tax['IsExempt']=True
        taxes=[tax]
    total=q6(base+sum((t['Total'] for t in taxes),D(0)))
    if q2(total)!=D(row['total_cents'])/100:raise Error('La precisión fiscal no coincide con el ticket. Revisa esta partida antes de facturar')
    return {'ProductCode':mapping['product_code'],'IdentificationNumber':str(row['product_id']),'Description':row['product_name'],
            'UnitCode':mapping['unit_code'],'UnitPrice':unit,'Quantity':qty,'Subtotal':subtotal,'Discount':disc,'TaxObject':obj,'Taxes':taxes,'Total':total}
def common(config,folio,kind='I'):
    return {'NameId':'14' if kind=='P' else '1','Folio':folio,'Serie':config['series'],'CfdiType':kind,
            'ExpeditionPlace':config['postal_code'],'Date':dt.datetime.now().replace(microsecond=0).isoformat(),
            'Observations':'PRUEBA SIN VALOR FISCAL. No usar para deducciones ni declaraciones.'}
def proportional_taxes(items,paid,before,total):
    groups={}
    for i in items:
        for t in i['Taxes']:
            key=(str(t['Rate']),bool(t.get('IsExempt')))
            group=groups.setdefault(key,{**t,'Base':D(0),'Total':D(0)})
            group['Base']+=D(t['Base']);group['Total']+=D(t['Total'])
    # Acumulación proporcional: la última parcialidad recupera los decimales residuales.
    previous_paid=total-before;after_paid=previous_paid+paid
    for g in groups.values():
        for key in ('Base','Total'):g[key]=q6(g[key]*D(after_paid)/D(total))-q6(g[key]*D(previous_paid)/D(total))
    return list(groups.values())
