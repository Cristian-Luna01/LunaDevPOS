"""Cierre acotado de solicitudes rechazadas, compartido por servidor y proxy."""
import time

def discard_small_body(handler):
    if getattr(handler,'_body_read',False):return
    timeout=handler.connection.gettimeout()
    try:
        remaining=int(handler.headers.get('Content-Length','0'));deadline=time.monotonic()+0.25
        while 0<remaining<=1024*1024 and time.monotonic()<deadline:
            handler.connection.settimeout(max(0.001,deadline-time.monotonic()))
            chunk=handler.rfile.read1(min(65536,remaining))
            if not chunk:break
            remaining-=len(chunk)
    except (OSError,ValueError):pass
    finally:handler.connection.settimeout(timeout)
