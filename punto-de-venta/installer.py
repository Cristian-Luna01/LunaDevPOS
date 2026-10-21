"""Instalador de prueba por usuario, sin permisos de administrador."""
import os
import json
from build_info import VERSION
from pathlib import Path
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox
import zipfile
import shutil
import uuid

PAYLOAD=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'programa.zip'
LEGACY=Path(os.environ['LOCALAPPDATA'])/'Programs'/'NuvariaPOSEscritorioPrueba'
TARGET=LEGACY if LEGACY.exists() else Path(os.environ['LOCALAPPDATA'])/'Programs'/'LunaDevPOS'

def install(target=TARGET, shortcut=True):
    target=Path(target)
    if target.resolve()==TARGET.resolve():
        import lifecycle
        lifecycle.safe(target,lifecycle.known_programs())
        lifecycle.ensure_closed()
        legacy_data=Path(os.environ['LOCALAPPDATA'])/'NuvariaPOSEscritorioPrueba'/'data'
        data_lock=(legacy_data if (legacy_data/'pos.sqlite3').exists() else Path(os.environ['LOCALAPPDATA'])/'LunaDevPOS'/'data')/'programa.lock'
        if data_lock.exists():
            import msvcrt
            with data_lock.open('r+b') as lock:
                try:
                    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
                except OSError:raise RuntimeError('Cierra los turnos y el programa antes de actualizar.')
    stage=target.parent/(target.name+'.nueva-'+uuid.uuid4().hex)
    previous=target.parent/(target.name+'.anterior-'+uuid.uuid4().hex)
    with zipfile.ZipFile(PAYLOAD) as archive:
        for item in archive.infolist():
            resolved=(stage/item.filename).resolve()
            if not resolved.is_relative_to(stage.resolve()):raise RuntimeError('Archivo de instalación inválido')
        stage.mkdir(parents=True)
        archive.extractall(stage)
    if not ((stage/'LunaDevPOS.exe').exists() or (stage/'NuvariaPOSEscritorio.exe').exists()):raise RuntimeError('Instalación incompleta')
    replaced=False
    try:
        if target.exists():target.rename(previous);replaced=True
        stage.rename(target)
    except Exception:
        if replaced and not target.exists():previous.rename(target)
        raise RuntimeError('No se pudo actualizar. Cierra el programa y vuelve a intentarlo.')
    if replaced:
        if previous.resolve().parent!=target.resolve().parent:raise RuntimeError('Ruta de actualización inválida')
        try:shutil.rmtree(previous)
        except OSError:pass
    executable=target/('LunaDevPOS.exe' if (target/'LunaDevPOS.exe').exists() else 'NuvariaPOSEscritorio.exe')
    (target/'instalacion.json').write_text(json.dumps({'product':'LunaDev POS','version':VERSION}),encoding='utf-8')
    if shortcut:
        def quote(value):return "'"+str(value).replace("'","''")+"'"
        script="$taskShell=New-Object -ComObject WScript.Shell\n$taskLink=$taskShell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'LunaDev POS.lnk'))\n$taskLink.TargetPath="+quote(executable)+"\n$taskLink.WorkingDirectory="+quote(target)+"\n$taskLink.Save()"
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'shortcut.ps1';path.write_text(script,encoding='utf-8-sig')
            subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(path)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        from lifecycle import register
        register(target)
    return executable

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--self-test':
        install(Path(sys.argv[2]),False);return
    root=tk.Tk();root.title('Instalar LunaDev POS');root.geometry('640x540');root.configure(bg='#f2f6f4')
    frame=ttk.Frame(root,padding=30);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='LunaDev POS',font=('Segoe UI',22,'bold')).pack(anchor='w',pady=10)
    ttk.Label(frame,text='Windows de 64 bits. El paquete no incluye inventario, cuentas, clientes ni claves de conexión.',wraplength=550).pack(anchor='w',pady=12)
    ttk.Label(frame,text='Se instalará solo para tu usuario.\nSe creará un acceso directo en el escritorio.\nActualizar conserva tus datos.',wraplength=480).pack(anchor='w',pady=12)
    mode=tk.StringVar(value='keep')
    ttk.Radiobutton(frame,text='Instalar o actualizar conservando mis datos',variable=mode,value='keep').pack(anchor='w',pady=6)
    ttk.Radiobutton(frame,text='Empezar desde cero y archivar los datos anteriores',variable=mode,value='clean').pack(anchor='w',pady=6)
    ttk.Label(frame,text='Empezar desde cero retira también la vinculación anterior. Se conserva una copia en LunaDevPOS-Respaldos, dentro de tu carpeta de usuario. Los reportes de Cloudflare permanecen.',wraplength=550).pack(anchor='w',pady=10)
    status=ttk.Label(frame,text='',wraplength=480);status.pack(anchor='w',pady=8)
    def submit():
        button.configure(state='disabled');status.configure(text='Instalando…');root.update_idletasks()
        try:
            executable=install()
            from lifecycle import archive_data
            backup=archive_data() if mode.get()=='clean' else None
            status.configure(text='Instalación terminada. Abre LunaDev POS desde el escritorio.'+(' Copia anterior: '+str(backup) if backup else ''))
            button.configure(text='Abrir programa',state='normal',command=lambda:subprocess.Popen([str(executable)]))
        except Exception as error:messagebox.showerror('No se pudo instalar',str(error),parent=root);button.configure(state='normal')
    button=ttk.Button(frame,text='Instalar / actualizar',command=submit);button.pack(fill='x',pady=10)
    root.mainloop()

if __name__=='__main__':main()
