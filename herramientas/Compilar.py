"""Construcción de Windows desde dependencias bloqueadas; no publica ni instala."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'punto-de-venta'

def run(*args,cwd=SOURCE):subprocess.run([sys.executable,*map(str,args)],cwd=cwd,check=True)
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def zip_tree(directory,target,manifest=None):
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(directory.rglob('*')):
            if not path.is_file():continue
            info=zipfile.ZipInfo(path.relative_to(directory).as_posix(),(2026,10,21,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,path.read_bytes())
        if manifest is not None:
            info=zipfile.ZipInfo('payload-manifest.json',(2026,10,21,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,json.dumps(manifest,sort_keys=True).encode())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'outputs'/'release');parser.add_argument('--skip-tests',action='store_true');parser.add_argument('--incremental',action='store_true');args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if not args.skip_tests:run('-m','unittest','discover','-s','.','-p','test_*.py')
    build=ROOT/'work'/'compilacion';dist=build/'dist';build.mkdir(parents=True,exist_ok=True)
    clean=[] if args.incremental else ['--clean']
    run('-m','PyInstaller','--noconfirm',*clean,'--distpath',dist,'--workpath',build/'desktop','LunaDevPOS.spec')
    program=dist/'LunaDevPOS'
    run('-m','PyInstaller','--noconfirm',*clean,'--distpath',dist,'--workpath',build/'uninstaller','Desinstalar-LunaDevPOS.spec')
    import shutil
    shutil.copy2(dist/'Desinstalar-LunaDevPOS.exe',program/'Desinstalar-LunaDevPOS.exe')
    manifest={'version':(ROOT/'VERSION').read_text().strip(),'files':{p.relative_to(program).as_posix():digest(p) for p in sorted(program.rglob('*')) if p.is_file()}}
    zip_tree(program,SOURCE/'programa.zip',manifest)
    run('-m','PyInstaller','--noconfirm',*clean,'--distpath',dist,'--workpath',build/'installer','Instalar-LunaDevPOS.spec')
    installer=output/'Instalar-LunaDevPOS-mejorado.exe';shutil.copy2(dist/'Instalar-LunaDevPOS.exe',installer)
    portable=output/'LunaDevPOS-mejorado-portable.zip';zip_tree(program,portable)
    # Comprobar instalación en un directorio nuevo, sin tocar la instalación habitual.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='lunadev-installer-') as directory:
        subprocess.run([str(installer),'--self-test',str(Path(directory)/'program')],check=True,timeout=180)
    try:source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError):source_commit=None
    release={'version':manifest['version'],'python':sys.version,'artifacts':{p.name:digest(p) for p in (installer,portable)},'source_commit':source_commit,'local_changes':True}
    (output/'SHA256.json').write_text(json.dumps(release,indent=2),encoding='utf-8')
    shutil.copy2(ROOT/'requirements-release.lock',output/'requirements-release.lock')
    print(json.dumps(release,indent=2))

if __name__=='__main__':main()
