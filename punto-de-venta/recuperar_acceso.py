"""Recuperación local de acceso: la persona elige y escribe su contraseña."""
import getpass
from core import POS,ROOT,password_hash

def main():
 pos=POS(ROOT/'data'/'pos.sqlite3')
 with pos.db() as db:
  rows=db.execute('SELECT id,username,display_name FROM users WHERE active=1 ORDER BY id').fetchall()
 if not rows:raise RuntimeError('No hay cuentas activas en esta instalación')
 print('RECUPERAR ACCESO - esta herramienta no borra inventario ni ventas.\n')
 for row in rows:print(str(row['id'])+' · '+row['username']+' · '+row['display_name'])
 selected=input('Escribe el número de la cuenta que quieres recuperar: ').strip()
 row=next((r for r in rows if str(r['id'])==selected),None)
 if not row:raise RuntimeError('Cuenta no válida. No se modificó nada.')
 secret=getpass.getpass('Nueva contraseña (mínimo 8 caracteres): ')
 if len(secret)<8:raise RuntimeError('La contraseña debe tener al menos 8 caracteres. No se modificó nada.')
 if secret!=getpass.getpass('Repite la contraseña: '):raise RuntimeError('Las contraseñas no coinciden. No se modificó nada.')
 if input('Escribe RECUPERAR para cambiar el acceso de '+row['username']+': ').strip()!='RECUPERAR':
  print('Cancelado. No se modificó nada.');return
 with pos.db(True) as db:
  db.execute('UPDATE users SET password_hash=? WHERE id=?',(password_hash(secret),row['id']))
  db.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
  db.execute('DELETE FROM login_attempts WHERE username IN (?,?)',(row['username'],'direction\0'+row['username']))
  pos.audit(db,None,'user.local_access_recovery',row['id'],{})
 print('Acceso recuperado. Usuario: '+row['username'])
 print('Abre el programa e inicia sesión con tu nueva contraseña.')
if __name__=='__main__':
 try:main()
 except (KeyboardInterrupt,EOFError):print('Cancelado. No se modificó el acceso.')
 except Exception as error:print('No se pudo recuperar el acceso: '+str(error))
