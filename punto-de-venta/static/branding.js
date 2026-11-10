(()=>{
 let canEdit=false,pending=false;
 const dialog=document.createElement('dialog');dialog.id='settingsDialog';dialog.setAttribute('aria-labelledby','settingsTitle');
 dialog.innerHTML=`<div class="section-title"><div><small>PERSONALIZACIÓN</small><h2 id="settingsTitle">Configuración</h2></div><button type="button" id="settingsClose" aria-label="Cerrar configuración">×</button></div><form id="settingsForm"><label>Nombre del negocio<input name="name" required maxlength="80"></label><label>Mensaje al pie del ticket<input name="receipt_footer" maxlength="200" placeholder="Gracias por tu compra."></label><p class="muted">Se comparte entre Mostrador y Dirección. El nombre y el mensaje aparecen en los tickets que imprimas.</p><button class="primary" type="submit">Guardar datos</button></form><hr><h3>Logotipo del negocio</h3><div class="logo-preview"><img id="settingsLogo" alt="Logotipo actual" hidden><span id="noLogo">Sin logotipo</span></div><p class="muted">PNG de hasta 2 MB. Puedes conservar el fondo transparente.</p><div class="actions"><button id="settingsUpload" type="button">Subir logotipo</button><button id="settingsRemove" type="button" hidden>Quitar logotipo</button></div><input id="settingsFile" type="file" accept="image/png" hidden><p id="settingsStatus" role="status"></p>`;
 document.body.append(dialog);
 let outsidePress=false;const outside=e=>{const r=dialog.getBoundingClientRect();return e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom;};dialog.addEventListener("pointerdown",e=>outsidePress=e.target===dialog&&outside(e));dialog.addEventListener("click",e=>{if(outsidePress&&e.target===dialog&&outside(e)&&!pending)dialog.close();outsidePress=false;});
 const preview=document.createElement("div");preview.className="ticket-preview";dialog.append(preview);
 function renderPreview(){preview.replaceChildren();const heading=document.createElement("h3");heading.textContent="Vista previa del ticket";preview.append(heading);const img=document.createElement("img");img.className="receipt-logo";img.hidden=!window.businessSettings?.has_logo;img.src="/business-logo.png?t="+Date.now();preview.append(img);for(const text of [form.elements.name.value,"Ticket de ejemplo","1 × Medicamento · $20.00","Total $20.00",form.elements.receipt_footer.value]){const line=document.createElement("p");line.textContent=text;preview.append(line);}}
 const el=id=>document.getElementById(id),form=el('settingsForm');
 const status=text=>el('settingsStatus').textContent=text;
 const base=location.pathname.startsWith('/direccion')?'/direccion/api':'/api';
 if(base==='/api'){
   const privacy=document.createElement('section');
   privacy.innerHTML='<hr><h3>Aviso de privacidad</h3><p class="muted">Configura el aviso de tu negocio para mostrarlo al registrar clientes. El texto debe corresponder a los datos y servicios que realmente utilizas.</p><form><label>Responsable (nombre o razón social)<input name="responsible" required maxlength="160"></label><label>Domicilio del responsable<textarea name="address" required maxlength="400"></textarea></label><label>Para qué se usan los datos<textarea name="purposes" required maxlength="1000"></textarea></label><label>Contacto para ejercer derechos ARCO<input name="contact" required maxlength="250"></label><label>Aviso completo<textarea name="full_notice" required maxlength="12000" rows="6"></textarea></label><button type="submit">Guardar aviso</button><p role="status"></p></form>';
   dialog.append(privacy);
   const pf=privacy.querySelector('form'),feedback=pf.querySelector('[role=status]');
   async function getNotice(){
     const r=await fetch('/api/privacy-notice');
     if(!r.ok)throw Error('No se pudo consultar el aviso.');
     return r.json();
   }
   async function loadNotice(){
     try{
       const data=await getNotice();
       for(const field of pf.elements)if(field.name)field.value=data[field.name]||'';
       feedback.textContent='';
     }catch(e){feedback.textContent=e.message;}
   }
   pf.onsubmit=async e=>{
     e.preventDefault();
     const submit=pf.querySelector('button');submit.disabled=true;
     try{await post('/privacy-notice',Object.fromEntries(new FormData(pf)));feedback.textContent='Aviso guardado.';}
     catch(error){feedback.textContent=error.message;}
     finally{submit.disabled=false;}
   };
   window.showCustomerPrivacyNotice=async container=>{
     if(!container)return;
     container.textContent='Consultando el aviso de privacidad…';
     try{
       const data=await getNotice();
       if(!data.full_notice){container.textContent='El negocio aún no ha configurado su aviso de privacidad. Consulta al responsable antes de pedir datos.';return;}
       const heading=document.createElement('strong');heading.textContent='Aviso de privacidad';
       const brief=document.createElement('p');brief.textContent=`${data.responsible} · ${data.address}. Datos de esta ficha: nombre, teléfono opcional y descuento. Uso: ${data.purposes} Para limitar el uso o ejercer derechos ARCO: ${data.contact}.`;
       const details=document.createElement('details'),summary=document.createElement('summary'),full=document.createElement('div');
       summary.textContent='Leer aviso completo';full.textContent=data.full_notice;full.style.whiteSpace='pre-wrap';details.append(summary,full);
       container.replaceChildren(heading,brief,details);
     }catch(e){container.textContent=e.message;}
   };
   dialog.addEventListener('privacy-settings-open',loadNotice);
 }
 async function post(path,data){const response=await fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json','X-POS-Request':'1'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error||'No se pudo guardar');}
 async function load(){const response=await fetch('/business-settings');if(!response.ok)throw Error('No se pudo leer la configuración');const data=await response.json();window.businessSettings=data;document.title=data.name+(location.pathname.startsWith('/direccion')?' · Dirección':' · Punto de venta');
   for(const brand of document.querySelectorAll('.business-brand')){brand.querySelector('span').firstChild.textContent=data.name;const img=brand.querySelector('img');img.hidden=!data.has_logo;if(data.has_logo)img.src='/business-logo.png?t='+Date.now();}
   const img=el('settingsLogo');img.hidden=!data.has_logo;if(data.has_logo)img.src='/business-logo.png?t='+Date.now();el('noLogo').hidden=data.has_logo;el('settingsRemove').hidden=!data.has_logo;el('settingsUpload').textContent=data.has_logo?'Cambiar logotipo':'Subir logotipo';if(dialog.open)renderPreview();return data;
 }
 window.openBusinessSettings=async()=>{if(!canEdit)return;dialog.showModal();dialog.dispatchEvent(new Event('privacy-settings-open'));dialog.scrollTop=0;status('Cargando…');try{const data=await load();form.elements.name.value=data.name;form.elements.receipt_footer.value=data.receipt_footer;renderPreview();status('');}catch(e){status(e.message);}};
 document.addEventListener('brand-permission',e=>{canEdit=!!e.detail&&!window.ownerReadOnly;const button=el('settingsOpen');if(button)button.hidden=!canEdit;});
 el('settingsClose').onclick=()=>dialog.close();
 async function action(fn){if(pending)return;pending=true;dialog.querySelectorAll('button').forEach(b=>b.disabled=true);status('Guardando…');try{await fn();await load();status('Cambios guardados.');}catch(e){status(e.message||'No se pudo guardar. Revisa que el programa siga abierto.');}finally{pending=false;dialog.querySelectorAll('button').forEach(b=>b.disabled=false);}}
 dialog.addEventListener('cancel',e=>{if(pending)e.preventDefault();});
 form.oninput=renderPreview;
 form.onsubmit=e=>{e.preventDefault();action(()=>post('/settings',Object.fromEntries(new FormData(form))));};
 el('settingsUpload').onclick=()=>el('settingsFile').click();
 el('settingsRemove').onclick=()=>action(()=>post('/branding',{remove:true}));
 el('settingsFile').onchange=()=>{const file=el('settingsFile').files[0];if(!file)return;action(async()=>{
   if(file.type!=='image/png'||file.size>2*1024*1024)throw Error('Selecciona un PNG de hasta 2 MB.');
   const preview=await createImageBitmap(file);const large=preview.width>4096||preview.height>4096;preview.close();if(large)throw Error('Máximo 4096 × 4096 píxeles.');
   const raw=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('No se pudo leer la imagen'));reader.readAsDataURL(file);});await post('/branding',{png_base64:raw.split(',')[1]});
 }).finally(()=>el('settingsFile').value='');};
 for(const caption of document.querySelectorAll('.brand-caption'))caption.textContent=location.pathname.startsWith('/direccion')?'DIRECCIÓN':'PUNTO DE VENTA';
 for(const id of ['logout','directionLogout','gateLogout'])el(id)?.addEventListener('click',()=>{canEdit=false;dialog.close();const b=el('settingsOpen');if(b)b.hidden=true;});
 load().catch(()=>{});document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!dialog.open)load().catch(()=>{});});
})();
