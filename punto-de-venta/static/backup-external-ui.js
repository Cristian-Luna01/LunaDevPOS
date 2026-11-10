(()=>{
 const section=document.createElement('section');section.className='panel';section.innerHTML='<h3>Respaldo externo automático</h3><p>Al cerrar el turno se copia también a este destino, si está conectado. Elige una USB o disco externo: otra carpeta del mismo disco no protege de una falla física.</p><label>Carpeta de destino (ruta completa)<input data-directory placeholder="Ejemplo: E:\\Respaldos"></label><div class="actions"><button type="button" data-choose>Elegir carpeta</button><button type="button" data-save>Guardar destino</button><button type="button" data-disable>Desactivar destino externo</button><button type="button" data-copy>Comprobar copia del último turno</button></div><p>Las copias automáticas propias se conservan 30 días. Los respaldos descargados manualmente no se borran.</p><p data-status role="status"></p>';
 document.getElementById('maintenanceOptions').append(section);
 const protection=document.createElement('div');
 protection.innerHTML='<h4>Frase para copias automáticas portátiles</h4><p>Sin frase, las copias locales se protegen con tu perfil de Windows. Para copiar a un destino externo y restaurar en otro equipo, guarda una frase separada del archivo.</p><label>Frase<input data-phrase type="password" autocomplete="new-password" minlength="12" maxlength="256"></label><label>Repite la frase<input data-repeat type="password" autocomplete="new-password" minlength="12" maxlength="256"></label><button type="button" data-key>Guardar frase</button><p data-key-status role="status"></p>';
 section.prepend(protection);
 const field=section.querySelector('[data-directory]'),message=text=>section.querySelector('[data-status]').textContent=text;
 async function action(fn){const buttons=section.querySelectorAll('button');buttons.forEach(b=>b.disabled=true);try{await fn();}catch(e){message(e.message);}finally{buttons.forEach(b=>b.disabled=false);}}
 const keyStatus=section.querySelector('[data-key-status]');
 section.querySelector('[data-key]').onclick=()=>action(async()=>{
  const phrase=section.querySelector('[data-phrase]'),repeat=section.querySelector('[data-repeat]');
  if(phrase.value!==repeat.value)throw Error('Las frases no coinciden.');
  await api('/backup/key',{passphrase:phrase.value});phrase.value=repeat.value='';
  keyStatus.textContent='Frase guardada. Las copias anteriores conservan su protección original.';
 });
 section.querySelector('[data-choose]').onclick=()=>action(async()=>{const v=await api('/backup/external/choose',{});if(v.directory)field.value=v.directory;message('Pulsa Guardar destino para usar esta carpeta.');});
 section.querySelector('[data-save]').onclick=()=>action(async()=>{const v=await api('/backup/external',{directory:field.value.trim()});field.value=v.directory;message('Destino guardado. Debe estar disponible al cerrar el turno.');});
 section.querySelector('[data-disable]').onclick=()=>action(async()=>{await api('/backup/external',{directory:''});field.value='';message('Destino externo desactivado. Se conservan las copias ya creadas.');});
 section.querySelector('[data-copy]').onclick=()=>action(async()=>{const v=await api('/backup/external/copy',{});message(v.external?.ok?'Copia externa comprobada.':v.external?.warning||v.warning||'No se confirmó la copia externa.');});
 document.addEventListener('brand-permission',async()=>{section.hidden=!me?.permissions.includes('backup.manage');if(section.hidden)return;try{const [v,key]=await Promise.all([api('/backup/external'),api('/backup/key')]);field.value=v.directory;keyStatus.textContent=key.configured?'Ya hay una frase configurada.':'Falta configurar la frase para el destino externo.';}catch{message('No se pudo consultar la configuración del respaldo.');}});
})();
