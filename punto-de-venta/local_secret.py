"""Claves de conexión protegidas con la cuenta de Windows (DPAPI)."""
import base64
import ctypes
from ctypes import wintypes
import os

class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

def transform(raw, encrypt):
    if os.name!='nt':
        raise RuntimeError('La conexión de sucursales requiere protección de claves de Windows')
    array=(ctypes.c_ubyte*len(raw)).from_buffer_copy(raw)
    source=Blob(len(raw),array);target=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    if encrypt:
        ok=crypt.CryptProtectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    else:
        ok=crypt.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    if not ok:raise ctypes.WinError(ctypes.get_last_error())
    try:return ctypes.string_at(target.data,target.size)
    finally:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.LocalFree.argtypes=[ctypes.c_void_p]
        kernel.LocalFree.restype=ctypes.c_void_p
        kernel.LocalFree(target.data)

def protect(secret):
    return base64.b64encode(transform(secret.encode(),True)).decode()

def reveal(secret):
    return transform(base64.b64decode(secret),False).decode()
