(()=>{
 const form=document.getElementById('adjustmentFilters'),day=document.getElementById('adjustmentDay'),cards=document.getElementById('adjustmentCards'),status=document.getElementById('adjustmentStatus'),section=document.getElementById('productMovements');
 day.value=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Mexico_City',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 let version=0,pending=false,lastBranch=window.centralBranch;
 const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 async function load(){
  const request=++version,selected=day.value,branch=window.centralBranch;
  if(lastBranch!==branch){cards.replaceChildren();lastBranch=branch;}
  status.textContent='Consultando ajustes…';pending=true;
  try{
   const response=await fetch('/direccion/api/inventory-adjustments?'+new URLSearchParams({from:selected,to:selected}));
   const result=await response.json();if(request!==version||branch!==window.centralBranch||selected!==day.value)return;
   if(!response.ok)throw Error(result.error||'No se pudieron consultar los ajustes.');
   let message;
   if(!result.available)message='La información de ajustes está incompleta. Actualiza el programa de los locales y espera la sincronización; no se puede confirmar que no hubo ajustes.';
   else if(result.detail_coverage.summary_days.length)message=`Esta fecha conserva solo resumen: ${result.count} modificación(es). Consulta el programa del local para ver productos y motivos.`;
   else message=result.items.length?`${result.items.length} modificación(es) registrada(s) el ${selected}.`:`No hubo modificaciones de existencia, precio o costo registradas el ${selected}.`;
   status.textContent=message;
   const markup=result.items.map(a=>`<article class="panel product-adjustment" data-live-key="adjustment-${safe(a.id)}"><strong>${safe(a.name)}</strong><p class="muted">${safe(a.barcode)} · ${safe(a.branch_name)} · ${safe(a.happened_at)}</p>${a.kind==='price_change'?Object.entries(a.changes||{}).map(([field,c])=>`<p>${field==='price_cents'?'Precio de venta':'Costo de compra configurado'}: <strong>${money(c.before)} → ${money(c.after)}</strong></p>`).join(''):`<p>Existencia: <strong>${safe(a.before)} → ${safe(a.after)}</strong> · ${a.difference>0?'+':''}${safe(a.difference)} unidades</p>`}<p><strong>Motivo:</strong> ${safe(a.reason)}</p><p class="muted">Registrado por ${safe(a.user_name)}</p></article>`).join('');
   if(window.liveView)window.liveView.html(cards,markup);else cards.innerHTML=markup;
  }catch(error){if(request===version){cards.replaceChildren();status.textContent=error.message||'Sin conexión. No se pudo comprobar si hubo ajustes.';}}
  finally{if(request===version)pending=false;}
 }
 form.onsubmit=e=>{e.preventDefault();load();};
 day.oninput=()=>{version++;pending=false;cards.replaceChildren();status.textContent='Pulsa Consultar para revisar esta fecha.';};
 document.querySelector('[data-section="productMovements"]').addEventListener('click',load);
 document.addEventListener('direction-summary-updated',()=>{if(lastBranch!==window.centralBranch){version++;pending=false;cards.replaceChildren();lastBranch=window.centralBranch;}if(!section.hidden&&!pending)load();});
 document.getElementById('directionLogout').addEventListener('click',()=>{version++;pending=false;cards.replaceChildren();status.textContent='';});
})();
