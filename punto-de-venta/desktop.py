"""Arranque visual. Recursos del programa separados de los datos del usuario."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from contextlib import closing
from core import POS, Error
from iniciar import serve_available
import branding

APP_NAME = 'Nuvaria POS · Prueba'

def data_directory(override=None):
    return Path(override) if override else Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'NuvariaPOSPrueba' / 'data'

def initialized(path):
    if not path.exists():
        return False
    with closing(sqlite3.connect(path)) as db:
        return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='users'").fetchone() and db.execute('SELECT 1 FROM users LIMIT 1').fetchone())

def create_account(pos, name, username, password, confirmation):
    name, username = name.strip(), username.strip().lower()
    if not 1 <= len(name) <= 80:
        raise Error('Escribe un nombre del negocio de 1 a 80 caracteres.')
    if not username or len(username) > 50 or any(c.isspace() for c in username):
        raise Error('Usa un usuario de hasta 50 caracteres, sin espacios.')
    if len(password) < 8:
        raise Error('La contraseña debe tener al menos 8 caracteres.')
    if password != confirmation:
        raise Error('Las contraseñas no coinciden.')
    pos.initialize(username, password)
    branding.save_settings(pos, 1, {'name':name, 'receipt_footer':'Gracias por tu compra.'})

def can_stop(pos):
    with pos.db() as db:
        return not db.execute('SELECT 1 FROM cash_shifts WHERE closed_at IS NULL').fetchone()

def smoke_test(directory):
    from urllib.request import urlopen
    pos=POS(Path(directory)/'pos.sqlite3')
    if initialized(Path(pos.path)):
        raise RuntimeError('La prueba requiere una carpeta vacía.')
    create_account(pos,'Farmacia de prueba','admin','prueba-ejecutable-2026','prueba-ejecutable-2026')
    server=serve_available(pos, 18765, 18785)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        for route in ['/', '/app.js', '/style.css', '/navigation.js', '/direccion/', '/direccion/panel.js']:
            with urlopen(f'http://127.0.0.1:{server.server_port}'+route) as response:
                if response.status != 200 or not response.read(): raise RuntimeError('Recurso no disponible')
        with pos.db() as db:
            for table in ['products','sales','customers','cash_shifts']:
                if db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]: raise RuntimeError('Instalación no vacía')
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise RuntimeError('Base inválida')
        pos.login('admin','prueba-ejecutable-2026')
        if not can_stop(pos): raise RuntimeError('Cierre inválido')
    finally:
        server.shutdown();server.server_close();thread.join()
    Path(directory,'resultado.json').write_text(json.dumps({'ok':True,'empty_inventory':True,'resources':True}),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir');parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    directory=data_directory(args.data_dir);directory.mkdir(parents=True,exist_ok=True)
    if args.self_test:
        smoke_test(directory);return
    import msvcrt
    lock=open(directory/'programa.lock','a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        messagebox.showinfo(APP_NAME,'El programa ya está abierto. Busca su ventana en la barra de tareas.');lock.close();return
    root=tk.Tk();root.title(APP_NAME);root.geometry('560x600');root.minsize(500,560);root.configure(bg='#f2f6f4')
    style=ttk.Style(root);style.theme_use('clam');style.configure('TFrame',background='#f2f6f4');style.configure('TLabel',background='#f2f6f4',foreground='#173e35',font=('Segoe UI',11));style.configure('Title.TLabel',font=('Segoe UI',22,'bold'));style.configure('TButton',font=('Segoe UI',11),padding=10);style.configure('TEntry',padding=7)
    frame=ttk.Frame(root,padding=30);frame.pack(fill='both',expand=True)
    pos=POS(directory/'pos.sqlite3');server=None;thread=None
    def clear():
        for child in frame.winfo_children(): child.destroy()
    def launch():
        nonlocal server,thread
        server=serve_available(pos);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}'
        (directory/'Direccion.url').write_text('[InternetShortcut]\nURL='+url+'/direccion/\n',encoding='utf-8')
        clear();ttk.Label(frame,text='Tu farmacia está lista',style='Title.TLabel').pack(anchor='w',pady=(0,15))
        ttk.Label(frame,text='Mantén esta ventana abierta mientras trabajas.\nLos datos se guardan en esta computadora.',wraplength=460).pack(anchor='w',pady=(0,25))
        ttk.Button(frame,text='Abrir punto de venta',command=lambda:webbrowser.open(url)).pack(fill='x',pady=6)
        ttk.Button(frame,text='Abrir Administración',command=lambda:webbrowser.open(url+'/direccion/')).pack(fill='x',pady=6)
        ttk.Label(frame,text='Versión de prueba · Datos independientes',wraplength=450).pack(anchor='w',pady=20)
        ttk.Button(frame,text='Cerrar programa',command=close).pack(fill='x',pady=6)
        webbrowser.open(url)
    def close():
        if server:
            if not can_stop(pos):
                messagebox.showwarning('Turno pendiente','Primero cuenta el efectivo y cierra los turnos en Caja y corte. Después podrás cerrar el programa.',parent=root);return
            server.shutdown();server.server_close()
        root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    if initialized(Path(pos.path)):
        launch()
    else:
        ttk.Label(frame,text='Configura tu negocio',style='Title.TLabel').pack(anchor='w',pady=(0,12))
        ttk.Label(frame,text='Crea tu primera cuenta de administrador.\nEl inventario comienza vacío.').pack(anchor='w',pady=(0,18))
        entries={}
        for key,label,value in [('name','Nombre del negocio',''),('username','Usuario administrador','admin'),('password','Contraseña (mínimo 8 caracteres)',''),('confirmation','Repetir contraseña','')]:
            ttk.Label(frame,text=label).pack(anchor='w',pady=(8,3));entry=ttk.Entry(frame,show='•' if key in ('password','confirmation') else '');entry.insert(0,value);entry.pack(fill='x');entries[key]=entry
        error=ttk.Label(frame,text='',wraplength=460,foreground='#b32929');error.pack(anchor='w',pady=10)
        def submit():
            try:
                create_account(pos,**{k:e.get() for k,e in entries.items()});launch()
            except (Error,sqlite3.Error,OSError) as exc: error.configure(text=str(exc))
        ttk.Button(frame,text='Crear cuenta y empezar',command=submit).pack(fill='x',pady=8)
    try:root.mainloop()
    finally:lock.close()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        if '--self-test' in sys.argv: raise
        messagebox.showerror('No se pudo iniciar',str(exc))
