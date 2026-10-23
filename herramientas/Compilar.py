"""Compilación oficial Windows x64: entorno fijado y tres recetas vigentes."""
import argparse,hashlib,importlib.metadata as metadata,json,os,shutil,ssl,subprocess,sys,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent.parent;source=root/'punto-de-venta'
parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(root/'dist'));args=parser.parse_args();output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
for name,version in [('PySide6','6.12.0'),('PyInstaller','6.22.3'),('openpyxl','3.1.5')]:
    if metadata.version(name)!=version:raise SystemExit('Instala requirements-build.lock en un entorno limpio: '+name)
if (root/'VERSION').read_text().strip()!=__import__('runpy').run_path(str(source/'build_info.py'))['VERSION']:raise SystemExit('Versiones inconsistentes')
def build(spec,dist,work):
    print('Compilando '+spec,flush=True)
    with (output/(Path(spec).stem+'.log')).open('w',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--distpath',str(dist),'--workpath',str(work),spec],cwd=source,check=True,stdout=log,stderr=subprocess.STDOUT)
build('LunaDevPOS.spec',output/'native',output/'work/native')
build('Desinstalar-LunaDevPOS.spec',output/'uninstaller',output/'work/uninstaller')
program=output/'native/LunaDevPOS';shutil.copy2(output/'uninstaller/Desinstalar-LunaDevPOS.exe',program/'Desinstalar-LunaDevPOS.exe')
# Algunos runtimes añaden una lista de certificados rechazados al módulo ssl.
# Es un recurso público del motor, no una clave del negocio.
runtime_ca=Path(ssl.__file__).with_name('codex-rejected-cas.pem')
if runtime_ca.is_file():shutil.copy2(runtime_ca,program/'_internal'/runtime_ca.name)
shutil.copy2(program/'LunaDevPOS.exe',program/'NuvariaPOSEscritorio.exe')
licenses=program/'licenses';licenses.mkdir(exist_ok=True)
components=[]
for name in ['PySide6','PySide6_Essentials','PySide6_Addons','PySide6_WebEngine','PySide6_Pdf','shiboken6','PyInstaller','openpyxl','et-xmlfile']:
    dist=metadata.distribution(name);components.append({'name':name,'version':dist.version,'license':dist.metadata.get('License'),'home':dist.metadata.get('Home-page')})
    for file in dist.files or []:
        if 'license' in str(file).lower() and dist.locate_file(file).is_file():
            target=licenses/name/str(file);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dist.locate_file(file),target)
(licenses/'components.json').write_text(json.dumps(components,indent=2),encoding='utf-8')
shutil.copy2(root/'docs/GUIA-ACTUALIZACION-0.2.md',program/'GUIA-ACTUALIZACION.md')
assert not any(program.rglob('*.sqlite3')) and not any(program.rglob('*.db'))
for path in (source/'static').iterdir():
    if path.is_file() and (program/'_internal/static'/path.name).read_bytes()!=path.read_bytes():raise RuntimeError('Recurso distinto: '+path.name)
with zipfile.ZipFile(source/'programa.zip','w',zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
    for path in program.rglob('*'):
        if path.is_file():archive.write(path,path.relative_to(program))
build('Instalar-LunaDevPOS.spec',output,output/'work/installer')
checks={name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in ['Instalar-LunaDevPOS.exe']}
(output/'SHA256.json').write_text(json.dumps(checks,indent=2),encoding='utf-8');print('Instalador listo: '+str(output/'Instalar-LunaDevPOS.exe'),flush=True)
