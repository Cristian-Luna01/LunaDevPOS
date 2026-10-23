"""Selector de carpeta en el hilo Qt; el servidor no controla widgets desde otro hilo."""
import threading
from PySide6.QtCore import QObject,Signal,Slot,Qt
from PySide6.QtWidgets import QFileDialog

class DirectoryPicker(QObject):
    requested=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent);self.requested.connect(self.choose,Qt.ConnectionType.QueuedConnection)
    @Slot(object)
    def choose(self,result):
        try:result.directory=QFileDialog.getExistingDirectory(None,'Destino del respaldo externo')
        finally:result.set()
    def pick(self):
        result=threading.Event();result.directory='';self.requested.emit(result)
        if not result.wait(120):raise TimeoutError('Selector de carpeta sin respuesta')
        return result.directory
