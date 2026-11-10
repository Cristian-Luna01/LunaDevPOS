"""Aplicación de escritorio con motor incluido, sin navegador externo."""
import argparse
import os
from pathlib import Path
import sys
import threading
import json
from core import POS, Error
from desktop import create_account, initialized, can_stop, smoke_test
from iniciar import serve_available

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir');parser.add_argument('--self-test',action='store_true');parser.add_argument('--engine-check',action='store_true');args=parser.parse_args()
    legacy=Path(os.environ['LOCALAPPDATA'])/'NuvariaPOSEscritorioPrueba'/'data'
    directory=Path(args.data_dir) if args.data_dir else legacy if (legacy/'pos.sqlite3').exists() else Path(os.environ['LOCALAPPDATA'])/'LunaDevPOS'/'data'
    directory.mkdir(parents=True,exist_ok=True)
    if args.self_test:
        try:smoke_test(directory)
        except Exception:
            import traceback
            (directory/'error-autoprueba.txt').write_text(traceback.format_exc(),encoding='utf-8')
            raise SystemExit(1)
        return
    from PySide6.QtCore import QUrl, Qt, QTimer
    from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QFormLayout, QLineEdit, QLabel, QPushButton, QMessageBox, QDialog, QDialogButtonBox, QTabWidget, QFileDialog, QComboBox
    from PySide6.QtGui import QShortcut, QKeySequence
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtPrintSupport import QPrinter, QPrintDialog
    app=QApplication(sys.argv[:1]);app.setApplicationName('LunaDev POS');app.setStyleSheet('QWidget {font-family: Segoe UI; font-size:14px;} QPushButton {padding:10px; background:#126553; color:white; border-radius:6px;} QLineEdit,QComboBox {padding:8px;}')
    if args.engine_check:
        view=QWebEngineView();view.resize(800,600);QTimer.singleShot(1000,app.quit);app.exec();(directory/'motor-ok.txt').write_text('Qt WebEngine disponible',encoding='utf-8');return
    import msvcrt
    lock=open(directory/'programa.lock','a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:QMessageBox.information(None,'Punto de Venta','El programa ya está abierto. Busca su ventana en la barra de tareas.');lock.close();return
    pos=POS(directory/'pos.sqlite3')
    from automatic_backup import cleanup
    def clean_backups():
        try:cleanup(pos)
        except OSError:pass
    clean_backups()
    backup_cleanup_timer=QTimer(app)
    backup_cleanup_timer.timeout.connect(clean_backups)
    backup_cleanup_timer.start(60000)
    if not initialized(Path(pos.path)):
        setup=QDialog();setup.setWindowTitle('Configura tu negocio');setup.resize(500,460);layout=QVBoxLayout(setup);title=QLabel('Configura tu negocio');title.setStyleSheet('font-size:25px;font-weight:bold;color:#126553');layout.addWidget(title);layout.addWidget(QLabel('Crea la cuenta de administrador. El inventario empieza vacío.'));form=QFormLayout();layout.addLayout(form);entries={}
        for key,label,value in [('name','Nombre del negocio',''),('username','Usuario administrador','admin'),('password','Contraseña (mínimo 8 caracteres)',''),('confirmation','Repetir contraseña','')]:
            entry=QLineEdit(value)
            if key in ('password','confirmation'):entry.setEchoMode(QLineEdit.Password)
            entries[key]=entry;form.addRow(label,entry)
        status=QLabel();status.setWordWrap(True);status.setStyleSheet('color:#b32929');layout.addWidget(status);button=QPushButton('Crear cuenta y empezar');layout.addWidget(button)
        def submit():
            try:create_account(pos,**{key:entry.text() for key,entry in entries.items()});setup.accept()
            except Exception as error:status.setText(str(error))
        button.clicked.connect(submit)
        if setup.exec()!=QDialog.Accepted:lock.close();return
    server=serve_available(pos)
    (directory/'runtime.json').write_text(json.dumps({'port':server.server_port}),encoding='utf-8')
    from owner_access import OwnerAccess;server.owner_access=OwnerAccess(server)
    from branch_sync import BranchSync
    server.branch_sync=BranchSync(pos);server.branch_sync.start()
    from billing_service import BillingService
    server.billing=BillingService(pos);server.billing.start()
    from desktop_clipboard import OwnerClipboard
    clipboard_service=OwnerClipboard(app);server.copy_owner_link=clipboard_service.copy_link
    from directory_picker import DirectoryPicker
    directory_service=DirectoryPicker(app);server.choose_backup_directory=directory_service.pick
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}'
    class LocalPage(QWebEnginePage):
        def acceptNavigationRequest(self,target,kind,main_frame):
            return target.scheme() in ('http','about') and (target.scheme()=='about' or (target.host()=='127.0.0.1' and target.port()==server.server_port))
    class Window(QMainWindow):
        def closeEvent(self,event):
            if not can_stop(pos):
                QMessageBox.warning(self,'Turno pendiente','Primero cierra el turno en Caja y corte. El mostrador seguirá abierto para que puedas hacerlo.');event.ignore();return
            event.accept()
    window=Window();window.setWindowTitle('LunaDev POS');window.resize(1150,800)
    from PySide6.QtWebEngineCore import QWebEngineProfile
    browser_profile=QWebEngineProfile('punto-venta',app);browser_profile.setPersistentStoragePath(str(directory/'web-profile'));browser_profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
    view=QWebEngineView();page=LocalPage(browser_profile,view);view.setPage(page);window.setCentralWidget(view);views=[view];view.setUrl(QUrl(url+'/'))
    def print_ticket():
        printer=QPrinter(QPrinter.HighResolution);dialog=QPrintDialog(printer,window)
        if dialog.exec()==QDialog.Accepted:
            window.ticket_printer=printer;view.print(printer)
    view.printRequested.connect(print_ticket)
    profile=view.page().profile()
    def download(request):
        path,_=QFileDialog.getSaveFileName(window,'Guardar archivo',request.downloadFileName())
        if path:request.setDownloadDirectory(str(Path(path).parent));request.setDownloadFileName(Path(path).name);request.accept()
        else:request.cancel()
    profile.downloadRequested.connect(download)
    def recovery():
        with pos.db() as db:rows=[dict(row) for row in db.execute('SELECT s.id,s.user_id,u.display_name FROM cash_shifts s JOIN users u ON u.id=s.user_id WHERE closed_at IS NULL ORDER BY s.id')]
        if not rows:QMessageBox.information(window,'Recuperación','No hay turnos pendientes.');return
        dialog=QDialog(window);dialog.setWindowTitle('Cerrar un turno pendiente');layout=QFormLayout(dialog);layout.addRow(QLabel('Usa tu cuenta para cerrar tu turno, o una cuenta de administrador.'))
        selector=QComboBox()
        for row in rows:selector.addItem(f"Turno #{row['id']} · {row['display_name']}")
        user=QLineEdit();secret=QLineEdit();secret.setEchoMode(QLineEdit.Password);count=QLineEdit('0.00');status=QLabel();status.setWordWrap(True)
        for label,widget in [('Turno',selector),('Usuario',user),('Contraseña',secret),('Efectivo contado',count)]:layout.addRow(label,widget)
        layout.addRow(status);button=QPushButton('Registrar conteo y cerrar turno');layout.addRow(button)
        def confirm():
            token=None
            try:
                from decimal import Decimal,InvalidOperation
                token=pos.login(user.text().strip().lower(),secret.text());uid=pos.session_user(token);row=rows[selector.currentIndex()]
                with pos.db() as db:
                    if uid!=row['user_id']:pos.require(db,uid,'users.manage')
                    else:pos.require(db,uid,'sell')
                value=Decimal(count.text().strip())
                if not value.is_finite() or value<0 or value*100!=(value*100).to_integral_value():raise Error('Usa un importe válido con hasta dos decimales.')
                pos.close_shift(row['user_id'],{'shift_id':row['id'],'counted_cents':int(value*100)})
                with pos.db(True) as db:pos.audit(db,uid,'shift.desktop_recovery',row['id'],{'counted_cents':int(value*100)})
                for view in views:view.reload()
                dialog.accept()
            except Exception as error:status.setText(str(error))
            finally:
                if token:
                    pos.revoke_session(token)
        button.clicked.connect(confirm);dialog.exec()
    window.recovery_shortcut=QShortcut(QKeySequence('Ctrl+Shift+R'),window);window.recovery_shortcut.activated.connect(recovery)
    window.reload_shortcut=QShortcut(QKeySequence('Ctrl+R'),window);window.reload_shortcut.activated.connect(view.reload)
    window.show()
    try:app.exec()
    finally:server.billing.stop();server.branch_sync.stop();server.owner_access.stop();server.shutdown();server.server_close();thread.join();lock.close()

if __name__=='__main__':main()
