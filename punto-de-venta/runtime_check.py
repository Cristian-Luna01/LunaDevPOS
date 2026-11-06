"""Prueba real de Qt WebEngine con datos temporales y una respuesta perdida."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS','--disable-gpu')
SOURCE=Path(__file__).resolve().parents[1]/'punto-de-venta';sys.path.insert(0,str(SOURCE))
from core import POS
from app import Handler
from http.server import ThreadingHTTPServer
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl,QTimer
from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

def run(output,existing_app):
    from types import SimpleNamespace
    args=SimpleNamespace(output=Path(output));args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lunadev-qt-') as directory:
        pos=POS(Path(directory)/'data'/'pos.sqlite3');pos.initialize('qa','desktop-test-password')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.pos=pos;server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        app=existing_app;errors=[];result={'ok':False};stage=[0]
        class Page(QWebEnginePage):
            def javaScriptConsoleMessage(self,level,message,line,source):
                # Chromium omite el aviso de salida cuando el conductor de pruebas
                # recarga una página sin un gesto humano; es esperado en este caso.
                if level==QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel and not message.startswith("Blocked attempt to show a 'beforeunload'"):errors.append(message)
        profile=QWebEngineProfile(app);view=QWebEngineView();view.resize(1280,900);page=Page(profile,view);view.setPage(page);view.show()
        initial='''(async()=>{try{
         await new Promise(r=>setTimeout(r,250));
         await requestApi('/login',{username:'qa',secret:'desktop-test-password'});await refresh();
         await api('/shifts/open',{shift_number:1,opening_cents:0});await refresh();
         const product=await api('/products/save',{barcode:'7501234567890',name:'Producto de prueba',category_id:1,cost_cents:500,price_cents:1000,tax_bps:0});
         await api('/inventory/receive',{product_id:product.id,quantity:5,unit_cost_cents:500,reason:'Prueba de escritorio'});
         const payload={request_key:'qt-lost-response',items:[{product_id:product.id,quantity:1}],payments:[{method:'cash',amount_cents:1000,tendered_cents:2000}]};
         let lost=false;try{await safeOperations.submit('/sales',payload,async(path,data)=>{const r=await requestApi(path,data);if(path==='/operations/recover'&&!lost){lost=true;throw Error('Respuesta perdida de prueba');}return r;});}catch{}
         window.__qaResult={ok:true};
        }catch(e){window.__qaResult={error:e.stack||e.message};}})();'''
        recovery='''(async()=>{try{
         await refresh();
         const before=await requestApi('/operations/pending');if(before.items.length!==1)throw Error('No se conservó la operación pendiente');
         const button=[...document.querySelectorAll('button')].find(b=>b.textContent==='Recuperar resultado');if(!button)throw Error('No aparece Recuperar resultado');
         await button.onclick();
         const after=await requestApi('/operations/pending');if(after.items.length)throw Error('No se confirmó la recuperación');
         const tickets=await api('/tickets');if(tickets.items.length!==1)throw Error('La venta se duplicó');
         const products=await api('/products?q=7501234567890');if(products[0].stock!==4)throw Error('Existencia incorrecta');
         window.__qaResult={ok:true,ticket:tickets.items[0].id,stock:products[0].stock};
        }catch(e){window.__qaResult={error:e.stack||e.message};}})();'''
        def loaded(ok):
            if not ok:result['error']='No se cargó el mostrador';app.quit();return
            if stage[0]==0.5:stage[0]=1
            page.runJavaScript(initial if stage[0]==0 else recovery)
        page.loadFinished.connect(loaded)
        def check(value):
            if not value:return
            if value.get('error'):result.update(error=value['error']);app.quit();return
            if stage[0]==0:
                stage[0]=0.5;page.runJavaScript('window.__qaResult=null',lambda _:page.triggerAction(QWebEnginePage.WebAction.Reload));return
            if stage[0]==1:
                stage[0]=2;result.update(value);view.grab().save(str(args.output/'mostrador-prueba.png'))
                page.runJavaScript("document.getElementById('productEdit').click();document.getElementById('chooseProductQuery').value='Producto';document.getElementById('chooseProductQuery').dispatchEvent(new Event('input'));window.__qaResult=null;")
                QTimer.singleShot(600,finish)
        def finish():
            page.runJavaScript("document.querySelector('#chooseProductRows button')?.click();")
            QTimer.singleShot(400,lambda:verify_form())
        def verify_form():
            def verified(value):
                if not value:result.update(ok=False,error='El selector de productos no abrió el formulario')
                view.grab().save(str(args.output/'editar-producto-prueba.png'))
                if not value:app.quit();return
                from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
                from PySide6.QtGui import QTextDocument
                printer=QPrinter(QPrinter.PrinterMode.HighResolution)
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                native_pdf=args.output/'impresion-qt.pdf'
                printer.setOutputFileName(str(native_pdf))
                document=QTextDocument();document.setHtml('<h1>LunaPOS</h1><p>Prueba de impresión</p>');document.print_(printer)
                result['qt_print_pdf']=native_pdf.exists() and native_pdf.read_bytes().startswith(b'%PDF')
                result['printers_detected']=len(QPrinterInfo.availablePrinters())
                def pdf_ready(raw):
                    content=bytes(raw)
                    result['webengine_pdf']=content.startswith(b'%PDF') and len(content)>1000
                    if result['webengine_pdf']:(args.output/'impresion-web.pdf').write_bytes(content)
                    if not result['qt_print_pdf'] or not result['webengine_pdf']:result.update(ok=False,error='Falló impresión PDF')
                    app.quit()
                page.printToPdf(pdf_ready)
            page.runJavaScript("document.getElementById('dialogForm').elements.name?.value==='Producto de prueba'",verified)
        timer=QTimer();timer.timeout.connect(lambda:page.runJavaScript('JSON.stringify(window.__qaResult||null)',lambda value:check(json.loads(value) if value else None)));timer.start(200)
        def timeout():
            result.update(ok=False,error='Tiempo de prueba agotado',stage=stage[0])
            page.runJavaScript("JSON.stringify({ready:document.readyState,qa:window.__qaResult,workspace:document.getElementById('workspace')?.hidden})",lambda value:(result.update(debug=value),app.quit()))
        QTimer.singleShot(45000,timeout)
        view.setUrl(QUrl(f'http://127.0.0.1:{server.server_port}/'));app.exec()
        page.deleteLater();view.deleteLater();app.processEvents();server.shutdown();server.server_close();thread.join()
        result['console_errors']=errors
        if errors:result['ok']=False
        (args.output/'prueba-escritorio.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result));return 0 if result.get('ok') else 1
