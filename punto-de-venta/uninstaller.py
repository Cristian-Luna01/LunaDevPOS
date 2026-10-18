"""Desinstalador por usuario, con conservación de datos por defecto."""
import sys,os,subprocess,tempfile,shutil,ctypes
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
import lifecycle
def shell_folder(csidl):
 buffer=ctypes.create_unicode_buffer(260)
 if ctypes.windll.shell32.SHGetFolderPathW(None,csidl,None,0,buffer)!=0:raise RuntimeError('No se pudo localizar la carpeta de accesos directos')
 return Path(buffer.value)
def main():
 if len(sys.argv)==3 and sys.argv[1]=='--self-test':
  import json
  from core import POS
  test=Path(sys.argv[2])
  if test.exists():raise RuntimeError('La prueba requiere una carpeta nueva')
  test.mkdir(parents=True);base=test/'Local';data=lifecycle.known_data(base)[0];data.mkdir(parents=True);pos=POS(data/'pos.sqlite3');pos.initialize('qa','qa-test-password')
  program=lifecycle.known_programs(base)[0];program.mkdir(parents=True);(program/'qa.txt').write_text('QA')
  lifecycle.uninstall(True,test/'respaldo',base,registry=False)
  assert not program.exists() and not data.exists() and list((test/'respaldo').rglob('*.botica.json'))
  (test/'resultado.json').write_text(json.dumps({'ok':True,'data_archived':True,'program_removed':True}));return
 if getattr(sys,'frozen',False) and '--temporary' not in sys.argv:
  current=Path(sys.executable).resolve()
  if any(current.is_relative_to(p.resolve()) for p in lifecycle.known_programs()):
   folder=Path(tempfile.mkdtemp(prefix='LunaDev-desinstalar-'));exe=folder/'Desinstalar-LunaDevPOS.exe';shutil.copy2(current,exe)
   subprocess.Popen([str(exe),'--temporary'],creationflags=subprocess.CREATE_NO_WINDOW);return
 app=tk.Tk();app.title('Desinstalar LunaDev POS');app.geometry('620x460');frame=ttk.Frame(app,padding=25);frame.pack(fill='both',expand=True)
 ttk.Label(frame,text='Desinstalar LunaDev POS',font=('Segoe UI',20,'bold')).pack(anchor='w',pady=8)
 ttk.Label(frame,text='Reconoce LunaDev POS y las versiones Nuvaria anteriores. Cierra todos los turnos y programas antes de continuar.',wraplength=550).pack(anchor='w',pady=8)
 mode=tk.StringVar(value='keep')
 ttk.Radiobutton(frame,text='Quitar el programa y conservar los datos para reinstalar',variable=mode,value='keep').pack(anchor='w',pady=8)
 ttk.Radiobutton(frame,text='Empezar de cero: quitar el programa y archivar los datos',variable=mode,value='archive').pack(anchor='w',pady=8)
 ttk.Label(frame,text='Los reportes de Cloudflare permanecen. Para una prueba nueva, crea una sucursal de prueba nueva. El respaldo se guardará en LunaDevPOS-Respaldos, dentro de tu carpeta de usuario.',wraplength=550).pack(anchor='w',pady=12)
 status=ttk.Label(frame,text='',wraplength=550);status.pack(anchor='w',pady=8)
 def remove():
  button.configure(state='disabled');app.update_idletasks()
  try:
   location=lifecycle.uninstall(mode.get()=='archive',shortcuts=[shell_folder(0x10),shell_folder(0x02)])
   status.configure(text='Programa retirado. '+('Datos archivados en: '+str(location) if location else 'Los datos locales se conservaron.'))
   button.configure(text='Cerrar',state='normal',command=app.destroy)
  except Exception as error:messagebox.showerror('No se pudo desinstalar',str(error),parent=app);button.configure(state='normal')
 button=ttk.Button(frame,text='Desinstalar',command=remove);button.pack(fill='x',pady=10);app.mainloop()
if __name__=='__main__':main()
