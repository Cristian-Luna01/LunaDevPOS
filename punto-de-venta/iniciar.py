"""Inicio interactivo de Windows: errores visibles y navegador automático."""
import getpass
import sqlite3
import sys
import webbrowser
from contextlib import closing
from pathlib import Path


def serve_available(pos, start=8765, stop=8775):
    from app import Handler, ThreadingHTTPServer
    for port in range(start, stop + 1):
        try:
            server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        except OSError as error:
            # Windows también devuelve 10013 si el puerto está reservado o
            # lo ocupa un proceso que abrió el socket con acceso exclusivo.
            if error.errno not in (48, 98, 10048) and getattr(error, 'winerror', None) not in (10048, 10013):
                raise
            continue
        server.pos = pos
        return server
    raise RuntimeError('Los puertos 8765 a 8775 estan ocupados. Cierra una instancia anterior de Botica.')


def main():
    from core import POS, ROOT
    print('\nBOTICA - PUNTO DE VENTA\n')
    path = ROOT / 'data' / 'pos.sqlite3'
    pos = POS(path)
    initialized = False
    if path.exists():
        with closing(sqlite3.connect(path)) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
                initialized = bool(db.execute('SELECT 1 FROM users LIMIT 1').fetchone())
    if not initialized:
        print('Primer inicio. Usuario administrador: admin')
        print('Crea una contrasena de al menos 8 caracteres.')
        print('Al escribirla no se mostraran caracteres en pantalla.\n')
        while True:
            secret = getpass.getpass('Nueva contrasena: ')
            if len(secret) < 8:
                print('La contrasena debe tener al menos 8 caracteres.\n')
                continue
            if secret != getpass.getpass('Repite la contrasena: '):
                print('Las contrasenas no coinciden. Intenta de nuevo.\n')
                continue
            pos.initialize('admin', secret)
            break
        print('\nBase creada correctamente.\n')
    server = serve_available(pos)
    url = f'http://127.0.0.1:{server.server_port}'
    (ROOT/'data'/'Direccion.url').write_text('[InternetShortcut]\nURL='+url+'/direccion/\n',encoding='utf-8')
    print(f'Botica esta listo: {url}')
    print(f'Panel exclusivo de administracion: {url}/direccion/')
    print(f'Tus datos se guardan en: {path}')
    print('Deja esta ventana abierta mientras trabajas.')
    print('Para detener Botica, presiona Ctrl+C.\n')
    try:
        try:
            webbrowser.open(url)
        except Exception:
            print('No se pudo abrir el navegador. Abre manualmente la direccion indicada.')
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nBotica se ha detenido.')
    finally:
        server.server_close()


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nInicio cancelado.')
    except Exception as error:
        print(f'\nNo se pudo iniciar Botica: {error}')
        print('Comparte este mensaje para revisar el problema.')
        sys.exit(1)
