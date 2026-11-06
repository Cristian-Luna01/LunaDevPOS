(()=>{
 const anchor=document.getElementById('backupExport');if(!anchor)return;
 const button=document.createElement('button');button.textContent='Respaldos automáticos externos';button.dataset.permission='backup.manage';anchor.after(button);
 button.onclick=act(async()=>{
  const config=await api('/backup/settings');
  transferScreen('Proteger los datos del negocio',`<p>Se guarda una copia cada 30 minutos mientras el programa está abierto. Elige USB, otro disco o una carpeta sincronizada.</p><form id="externalBackupForm"><label>Carpeta externa<input name="directory" value="${esc(config.directory)}" placeholder="E:\\Respaldos-LunaDevPOS"></label><button>Guardar carpeta</button></form><p>Una carpeta del mismo disco ayuda a conservar versiones, pero no protege si ese disco falla.</p><div class="actions"><button id="backupNow">Respaldar ahora</button><button id="testRestore">Respaldar y comprobar restauración</button></div><p id="externalBackupStatus" role="status"></p>`);
  const status=document.getElementById('externalBackupStatus');status.textContent=config.status?.message||'Selecciona la carpeta de destino.';
  document.getElementById('externalBackupForm').onsubmit=e=>{e.preventDefault();transferAction(async()=>{await api('/backup/settings',{directory:new FormData(e.target).get('directory')});status.textContent='Carpeta guardada. Usa Respaldar ahora para comprobarla.';});};
  const run=verify=>transferAction(async()=>{status.textContent='Creando y verificando el respaldo…';const result=await api('/backup/run',{verify_restore:verify});status.textContent=(result.restore_test?'Restauración de prueba correcta. ':'')+'Respaldo guardado: '+result.path+(result.same_drive?' · Está en el mismo disco: conserva otra copia fuera de este equipo.':'');});
  document.getElementById('backupNow').onclick=()=>run(false);document.getElementById('testRestore').onclick=()=>run(true);
 });
})();
