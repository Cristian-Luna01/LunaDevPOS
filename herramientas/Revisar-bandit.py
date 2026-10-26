"""No oculta alertas: toda coincidencia nueva o cuyo código cambie exige revisión."""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parent.parent

def identity(result):
    name=str(Path(result['filename']).relative_to(root)).replace('\\','/')
    return name+'|'+result['test_id']+'|'+hashlib.sha256(result['code'].encode()).hexdigest()

def main():
    with tempfile.TemporaryDirectory() as directory:
        report=Path(directory)/'bandit.json'
        result=subprocess.run([sys.executable,'-m','bandit','-r',str(root/'punto-de-venta'),'-x','test_,vendor','--ignore-nosec','-f','json','-o',str(report)],capture_output=True,text=True)
        if result.returncode not in (0,1) or not report.exists():raise SystemExit('No se pudo completar Bandit: '+result.stderr)
        data=json.loads(report.read_text(encoding='utf-8'))
        if data.get('errors'):raise SystemExit('El escáner no pudo analizar todos los archivos')
    reviewed=json.loads((root/'docs/seguridad/bandit-revisado.json').read_text(encoding='utf-8'))
    unknown=[r for r in data['results'] if identity(r) not in reviewed]
    for r in unknown:print(str(Path(r['filename']).relative_to(root)),r['line_number'],r['test_id'],r['issue_text'])
    print(f"Coincidencias revisadas: {len(data['results'])-len(unknown)}. Sin revisión: {len(unknown)}.")
    raise SystemExit(bool(unknown))

if __name__=='__main__':main()
