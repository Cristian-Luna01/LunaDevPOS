import base64,json,struct,tempfile,unittest,zlib
from pathlib import Path
from core import POS,Error
import branding,inventory_io

def sample_png():
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\0\x80\0'))+chunk(b'IEND',b'')

class BrandingTest(unittest.TestCase):
    def test_logo_backup_restore_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            pos=POS(Path(tmp)/'a.db');pos.initialize('admin','test-password')
            raw=sample_png();data={'png_base64':base64.b64encode(raw).decode()}
            branding.save(pos,1,data);self.assertEqual(branding.read(pos),raw)
            branding.save_settings(pos,1,{'name':'Farmacia de prueba','receipt_footer':'Vuelve pronto'})
            self.assertEqual(branding.settings(pos)['name'],'Farmacia de prueba')
            uid=pos.save_user(1,dict(username='worker',display_name='Caja',secret='123456',permissions=['sell']))['id']
            with self.assertRaises(Error):branding.save(pos,uid,data)
            with self.assertRaises(Error):branding.save_settings(pos,uid,{'name':'No autorizado'})
            with self.assertRaises(Error):branding.save_settings(pos,1,{'name':' '})
            backup,_,_=inventory_io.backup(pos,1)
            target=POS(Path(tmp)/'b.db');target.initialize('admin','test-password')
            inventory_io.restore(target,1,dict(file_base64=base64.b64encode(backup).decode(),filename='backup.json',confirmation='RESTAURAR'))
            self.assertEqual(branding.read(target),raw)
            self.assertEqual(branding.settings(target)['receipt_footer'],'Vuelve pronto')
            branding.save(target,1,{'remove':True})
            self.assertFalse(branding.settings(target)['has_logo'])
            self.assertEqual(branding.settings(target)['name'],'Farmacia de prueba')
            for invalid in ['no-png',base64.b64encode(raw[:-1]).decode(),base64.b64encode(b'<svg/>').decode()]:
                with self.assertRaises(Error):branding.validate(invalid)
