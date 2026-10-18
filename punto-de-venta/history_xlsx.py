"""Exportación OpenXML ligera: cuatro vistas completas del mismo periodo."""
import datetime as dt,io,re,zipfile,math
from decimal import Decimal
from xml.etree.ElementTree import Element,SubElement,tostring
from core import Error

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
def column(n):
    name=''
    while n:n,r=divmod(n-1,26);name=chr(65+r)+name
    return name
def clean(text):return re.sub('[\x00-\x08\x0b\x0c\x0e-\x1f]', '',str(text))[:32767]
def money(cents):return Decimal(cents)/100
def date(value):
    value=dt.datetime.fromisoformat(value)
    return Decimal(str((value-dt.datetime(1899,12,30)).total_seconds()))/86400

STYLES='''<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="3"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00;[Red](&quot;$&quot;#,##0.00);&quot;$&quot;0.00"/><numFmt numFmtId="165" formatCode="dd/mm/yyyy"/><numFmt numFmtId="166" formatCode="dd/mm/yyyy hh:mm:ss"/></numFmts><fonts count="3"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><b/><sz val="16"/><color rgb="FF126553"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF126553"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="7"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''

def worksheet(title,period,note,heads,rows,money_cols,date_cols,total_cols):
    if len(rows)>1048570:raise Error('El periodo excede la cantidad de filas de Excel. Reduce las fechas.')
    root=Element('worksheet',xmlns=NS)
    views=SubElement(root,'sheetViews');view=SubElement(views,'sheetView',workbookViewId='0',showGridLines='0');SubElement(view,'pane',ySplit='5',topLeftCell='A6',activePane='bottomLeft',state='frozen')
    cols=SubElement(root,'cols');widths=[]
    for i,h in enumerate(heads,1):
        width=35 if h in ('Producto','Concepto / motivo','Proveedor','Registrado por') else 27 if h=='Categoría' else 23 if i-1 in date_cols else 20 if i-1 in money_cols else max(13,min(25,len(h)))
        widths.append(width)
        SubElement(cols,'col',min=str(i),max=str(i),width=str(width),customWidth='1')
    data=SubElement(root,'sheetData')
    def row(number,values,styles=None,formulas=None):
        r=SubElement(data,'row',r=str(number))
        if number in (3,5):r.set('ht','42');r.set('customHeight','1')
        if number>=6:
            height=max([15]+[15*math.ceil(len(str(v))/max(1,widths[i]-2)) for i,v in enumerate(values) if isinstance(v,str)])
            r.set('ht',str(min(390,height)));r.set('customHeight','1')
        for i,value in enumerate(values):
            if value is None:continue
            style=styles[i] if styles else 0
            if style==0 and isinstance(value,str):style=7
            cell=SubElement(r,'c',r=column(i+1)+str(number),s=str(style))
            if formulas and i in formulas:SubElement(cell,'f').text=formulas[i]
            if isinstance(value,(int,Decimal)):
                SubElement(cell,'v').text=str(value)
            else:
                cell.set('t','inlineStr');text=SubElement(SubElement(cell,'is'),'t');text.set('{http://www.w3.org/XML/1998/namespace}space','preserve');text.text=clean(value)
    row(1,[title],[5]);row(2,[period]);row(3,[note],[6]);row(5,heads,[4]*len(heads))
    styles=[1 if i in money_cols else date_cols.get(i,0) for i in range(len(heads))]
    for n,values in enumerate(rows,6):row(n,values,styles)
    end=5+len(rows)
    if rows:
        totals=[None]*len(heads);totals[0]='TOTAL';formulas={}
        for i in total_cols:totals[i]=sum((values[i] for values in rows),Decimal(0));formulas[i]=f'SUM({column(i+1)}6:{column(i+1)}{end})'
        row(end+2,totals,styles,formulas)
        SubElement(root,'autoFilter',ref=f'A5:{column(len(heads))}{end}')
    else:row(6,['Sin movimientos en estas fechas.'])
    merges=SubElement(root,'mergeCells',count='3')
    for n in (1,2,3):SubElement(merges,'mergeCell',ref=f'A{n}:{column(len(heads))}{n}')
    SubElement(root,'pageMargins',left='0.3',right='0.3',top='0.5',bottom='0.5',header='0.2',footer='0.2')
    SubElement(root,'pageSetup',orientation='landscape',paperSize='9',fitToWidth='1',fitToHeight='0')
    return tostring(root,encoding='utf-8',xml_declaration=True)

def export_history_xlsx(result):
    profit='profit_cents' in result['totals'];extra=['IVA neto MXN','Costo correspondiente MXN','Ganancia real MXN'] if profit else []
    def costs(r):return [money(r[k]) for k in ('tax_cents','cost_cents','profit_cents')] if profit else []
    daily=sorted(result['daily'],key=lambda r:r['day'],reverse=True)
    sheets=[];period=f"Del {result['from']} al {result['to']} · Fechas locales del negocio"
    heads=['Fecha','Cobros MXN','Devoluciones MXN','Ventas totales MXN','Efectivo MXN','Tarjeta MXN','Transferencia MXN','Entregadas','Devueltas','Tickets','Crédito registrado MXN']+extra+['Comisiones tarjeta MXN','Neto tras comisiones MXN']
    rows=[[date(r['day']),*[money(r[k]) for k in ('sales_cents','refunds_cents','net_cents')],*[money(r['payments_by_method'][k]) for k in ('cash','card','transfer')],r['sold_units'],r['returned_units'],r['tickets'],money(r['credit_cents'])]+costs(r)+[money(r.get('card_fee_cents',0)),money(r.get('after_fees_cents',r['net_cents']))] for r in daily]
    monetary={1,2,3,4,5,6,10,*range(11,len(heads))};sheets.append(('Por día',worksheet('Totales por día',period,'Ventas pagadas y abonos menos devoluciones. El crédito pendiente y las entradas extraordinarias de caja no se suman a ventas.',heads,rows,monetary,{0:2},set(range(1,len(heads))))))
    heads=['Producto','Código','Entregadas','Devueltas','Cobros MXN','Devoluciones MXN','Ventas totales MXN','Crédito registrado MXN']+extra
    rows=[[r['name'],r['barcode'],r['sold_units'],r['returned_units'],*[money(r[k]) for k in ('sales_cents','refunds_cents','net_cents','credit_cents')]]+costs(r) for r in result['products']]
    sheets.append(('Por producto',worksheet('Productos del periodo',period,'Los abonos reconocen dinero y costo proporcional; no vuelven a sumar unidades entregadas.',heads,rows,set(range(4,len(heads))),{},set(range(2,len(heads))))))
    heads=['Fecha y hora','Movimiento','Ticket original','Devolución','Abono','Partida','Código','Producto','Unidades','Importe cobrado MXN','Crédito registrado MXN','Estado actual']+extra
    events=sorted(result['events'],key=lambda e:(e['happened_at'],e['ticket_id'],e['item_id'],e['collection_id'] or 0),reverse=True)
    rows=[[date(e['happened_at']),e['kind'],e['ticket_id'],e['return_id'],e['collection_id'],e['item_id'],e['barcode'],e['name'],e['units'],money(e['cents']),money(e['credit_cents']),{'completed':'Confirmado','partial_return':'Devolución parcial','returned':'Devuelto','voided':'Anulado'}.get(e['status'],e['status'])]+costs(e) for e in events]
    sheets.append(('Detalle de movimientos',worksheet('Movimientos por ticket y partida',period,'Ventas con 100 % de descuento: importe cero, ticket y unidades conservados. Los importes negativos son devoluciones. Estado actual del ticket.',heads,rows,{9,10,*range(12,len(heads))},{0:3},{8,9,10,*range(12,len(heads))})))
    heads=['Fecha y hora','Folio','Movimiento','Entrada MXN','Salida MXN','Balance MXN','Concepto / motivo','Categoría','Turno','Registrado por','Proveedor','Factura / nota']
    rows=[[date(m['happened_at']),m['id'],'Entrada' if m['direction']=='in' else 'Salida',money(m['amount_cents']) if m['direction']=='in' else money(0),money(m['amount_cents']) if m['direction']=='out' else money(0),money(m['amount_cents']*(1 if m['direction']=='in' else -1)),m['concept'],{'change':'Entrada de efectivo','supplier':'Pago a proveedor','expense':'Gasto operativo','safekeeping':'Retiro / resguardo'}.get(m['category'],m['category']),m['shift_id'],m['user_name'],m['supplier_name'],m['invoice_ref']] for m in result['cash_movements']]
    sheets.append(('Entradas y salidas',worksheet('Entradas y salidas de caja',period,'Movimientos extraordinarios de efectivo. No incluye ventas, abonos, devoluciones ni fondo inicial. No se suman a las ventas totales.',heads,rows,{3,4,5},{0:3},{3,4,5})))
    heads=['Fecha','Movimiento','Folio','Cobrado MXN','Comisión estimada MXN','Neto estimado MXN','Proveedor','Tarifa configurada']
    rows=[[date(f['happened_at']),'Venta' if f['source_kind']=='sale' else 'Abono',f['source_id'],money(f['gross_cents']),money(f['fee_cents']),money(f['net_cents']),f['tariff']['provider'],'Sí' if f['configured'] else 'No'] for f in result.get('card_fees',[])]
    sheets.append(('Comisiones tarjeta',worksheet('Comisiones estimadas de tarjeta',period,'Tarifa congelada por cobro. No modifica el precio del cliente; validar contra el estado de cuenta del proveedor.',heads,rows,{3,4,5},{0:3},{3,4,5})))
    workbook=Element('workbook',xmlns=NS);book_sheets=SubElement(workbook,'sheets')
    rels=Element('Relationships',xmlns='http://schemas.openxmlformats.org/package/2006/relationships')
    content=Element('Types',xmlns='http://schemas.openxmlformats.org/package/2006/content-types')
    SubElement(content,'Default',Extension='rels',ContentType='application/vnd.openxmlformats-package.relationships+xml');SubElement(content,'Default',Extension='xml',ContentType='application/xml')
    for i,(name,_) in enumerate(sheets,1):
        SubElement(book_sheets,'sheet',name=name,sheetId=str(i),attrib={'{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id':f'rId{i}'})
        SubElement(rels,'Relationship',Id=f'rId{i}',Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet',Target=f'worksheets/sheet{i}.xml')
        SubElement(content,'Override',PartName=f'/xl/worksheets/sheet{i}.xml',ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
    SubElement(workbook,'calcPr',calcId='191029',fullCalcOnLoad='1')
    SubElement(rels,'Relationship',Id=f'rId{len(sheets)+1}',Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles',Target='styles.xml')
    for part,kind in [('workbook','sheet.main'),('styles','styles')]:SubElement(content,'Override',PartName=f'/xl/{part}.xml',ContentType=f'application/vnd.openxmlformats-officedocument.spreadsheetml.{kind}+xml')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',tostring(content));z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml',tostring(workbook));z.writestr('xl/_rels/workbook.xml.rels',tostring(rels));z.writestr('xl/styles.xml',STYLES.replace('cellXfs count="7"','cellXfs count="8"').replace('</cellXfs>','<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs>'))
        for i,(_,xml) in enumerate(sheets,1):z.writestr(f'xl/worksheets/sheet{i}.xml',xml)
    return stream.getvalue()
