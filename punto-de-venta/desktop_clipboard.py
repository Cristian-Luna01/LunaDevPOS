"""Escribe el enlace en el portapapeles desde el hilo de la aplicación Qt."""
import threading
from PySide6.QtCore import QObject,Signal,Slot,Qt
from PySide6.QtWidgets import QApplication

class OwnerClipboard(QObject):
    requested=Signal(str,object)
    def __init__(self,parent=None):
        super().__init__(parent);self.requested.connect(self.set_link,Qt.ConnectionType.QueuedConnection)
    @Slot(str,object)
    def set_link(self,text,result):
        try:
            clipboard=QApplication.clipboard();clipboard.setText(text);result.copied=clipboard.text()==text
        except Exception:result.copied=False
        finally:result.set()
    def copy_link(self,text):
        result=threading.Event();result.copied=False;self.requested.emit(text,result)
        return result.wait(3) and result.copied
