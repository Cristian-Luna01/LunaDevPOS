"""Límite de conexiones activas: clientes lentos no crean hilos ilimitados."""
from http.server import ThreadingHTTPServer as BaseServer
import socket
import threading

class ThreadingHTTPServer(BaseServer):
    max_connections=32
    # Windows SO_REUSEADDR can share an active listener, not just a closed port.
    allow_reuse_address=not hasattr(socket,'SO_EXCLUSIVEADDRUSE')

    def server_bind(self):
        if not self.allow_reuse_address and hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

    def __init__(self,*args,**kwargs):
        self.connection_slots=threading.BoundedSemaphore(self.max_connections)
        super().__init__(*args,**kwargs)
    def process_request(self,request,address):
        if not self.connection_slots.acquire(blocking=False):
            try:
                request.settimeout(.2)
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\nRetry-After: 1\r\n\r\n')
            except OSError:pass
            self.shutdown_request(request)
            return
        try:super().process_request(request,address)
        except BaseException:
            self.connection_slots.release()
            raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.connection_slots.release()
