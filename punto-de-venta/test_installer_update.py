import tempfile,unittest,zipfile
from pathlib import Path
import installer
class InstallerUpdateTest(unittest.TestCase):
 def test_update_replaces_program_and_preserves_separate_data(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);payload=root/'payload.zip';target=root/'program';data=root/'data';data.mkdir();(data/'pos.sqlite3').write_bytes(b'conservar')
   with zipfile.ZipFile(payload,'w') as archive:archive.writestr('NuvariaPOSEscritorio.exe',b'primera version')
   original=installer.PAYLOAD;installer.PAYLOAD=payload
   try:
    installer.install(target,False)
    with zipfile.ZipFile(payload,'w') as archive:archive.writestr('NuvariaPOSEscritorio.exe',b'version actualizada')
    installer.install(target,False)
    self.assertEqual((target/'NuvariaPOSEscritorio.exe').read_bytes(),b'version actualizada');self.assertEqual((data/'pos.sqlite3').read_bytes(),b'conservar')
   finally:installer.PAYLOAD=original
 def test_invalid_payload_preserves_previous_program(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);payload=root/'payload.zip';target=root/'program';target.mkdir();(target/'NuvariaPOSEscritorio.exe').write_bytes(b'anterior')
   with zipfile.ZipFile(payload,'w') as archive:archive.writestr('../escape.txt',b'no')
   original=installer.PAYLOAD;installer.PAYLOAD=payload
   try:
    with self.assertRaises(RuntimeError):installer.install(target,False)
    self.assertEqual((target/'NuvariaPOSEscritorio.exe').read_bytes(),b'anterior');self.assertFalse((root/'escape.txt').exists())
   finally:installer.PAYLOAD=original
