'use strict';
const $=id=>document.getElementById(id);
const money=c=>(c/100).toLocaleString('es-MX',{style:'currency',currency:'MXN',minimumFractionDigits:2});
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let rows=[],filter='all',limit=100,previous=null,pending=false,authenticated=false,generation=0;
let purchaseLimit=100;
function renderPurchases(){
 const needed=rows.filter(p=>p.stock<=p.reorder_point);
 $('purchaseSummary').textContent=`${needed.length} productos por revisar · Mostrando ${Math.min(purchaseLimit,needed.length)}`;
 $('purchaseRows').innerHTML=needed.slice(0,purchaseLimit).map(p=>`<article class="inventory-card" data-live-key="product-${esc(p.id)}"><div><strong>${esc(p.name)}</strong><small>${esc(p.barcode)} · ${p.stock} disponibles</small></div><span>${p.max_stock>p.stock?'Sugerido: '+(p.max_stock-p.stock)+' unidades':'Revisar existencia máxima'}</span></article>`).join('')||'<p>No hay productos por reponer.</p>';
 $('purchaseMore').hidden=needed.length<=purchaseLimit;
}
function renderManagement(data){
 const closed=data.shifts.filter(s=>s.difference_cents!==null);
 const missing=closed.reduce((sum,s)=>sum+Math.max(0,-s.difference_cents),0),extra=closed.reduce((sum,s)=>sum+Math.max(0,s.difference_cents),0);
 $('cashSummary').textContent=`Faltantes en cortes cerrados hoy: ${money(missing)} · Sobrantes: ${money(extra)} · ${data.shifts.length-closed.length} turnos pendientes de cierre`;
 $('directionShifts').innerHTML=data.shifts.map(s=>`<article class="inventory-card" data-live-key="cut-${esc(s.id)}-${esc(s.user)}"><div><strong>Corte #${s.id} · ${esc(s.user)}</strong><small>${s.closed_at?'Cerrado':'Abierto · Pendiente de conteo'}</small><small>Ventas totales del turno: ${money(s.sales_cents)}</small>${s.profit_cents!==undefined?`<small>Ganancia real: ${money(s.profit_cents)}${s.zero_cost_units?' · Revisar costos cero':''}</small>`:''}${s.payments_by_method?`<small>Efectivo: ${money(s.payments_by_method.cash)} · Tarjeta: ${money(s.payments_by_method.card)} · Transferencia / depósito: ${money(s.payments_by_method.transfer)}</small>`:''}<small>Efectivo esperado: ${money(s.expected_cents)} · Contado: ${s.counted_cents===null?'Pendiente':money(s.counted_cents)}</small></div><span>${s.difference_cents===null?'Diferencia pendiente':s.difference_cents<0?'Faltante: '+money(-s.difference_cents):s.difference_cents>0?'Sobrante: '+money(s.difference_cents):'Sin diferencia'}</span></article>`).join('')||'<p>No hay turnos abiertos ni cortes cerrados hoy.</p>';
 $('directionSuppliers').innerHTML=data.suppliers.map(s=>`<article class="inventory-card"><div><strong>${esc(s.business_name)}</strong><small>${esc(s.contact)} · ${esc(s.phone||'Sin teléfono registrado')}</small><small>Crédito: ${s.credit_days} días</small></div></article>`).join('')||'<p>No hay proveedores registrados.</p>';
 renderPurchases();
}
async function api(path,data){
 const response=await fetch('/direccion/api/'+path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json','X-POS-Request':'1'}:{},body:data?JSON.stringify(data):undefined});
 let body;
 try{body=JSON.parse(await response.text());}catch{
  const e=new Error(response.status===401||response.status===403||response.redirected?'El enlace rechazó el acceso o perdió la verificación por correo. Vuelve a abrir el enlace y verifica tu correo; después usa el usuario y contraseña del programa.':'El servicio no devolvió una respuesta válida. Comprueba que el programa siga abierto y vuelve a intentar.');
  e.remoteAccess=response.status===401||response.status===403||response.redirected;e.status=response.status===200?502:response.status;throw e;
 }
 if(!response.ok){const e=new Error(body.error||'No se pudo conectar');e.remoteAccess=!!body.owner_access_required;e.status=response.status;throw e;}return body;
}
function clearPanel(){sessionStorage.removeItem('lunadev-direction-view');$('sessionLoading').hidden=true;generation++;authenticated=false;rows=[];previous=null;$('directionWorkspace').hidden=true;$('directionLogin').hidden=false;$('directionProducts').replaceChildren();$('directionPayments').replaceChildren();$('directionShifts').replaceChildren();$('directionSuppliers').replaceChildren();$('purchaseRows').replaceChildren();for(const id of ['netSales','grossSales','refundSales','dayTickets','productProfit','productCost','directionUser'])$(id).textContent='';$('notice').hidden=true;}
function render(){
  const complete=rows.every(p=>Number.isSafeInteger(p.inventory_value_cents));
  $('directionInventoryValue').textContent=complete?'Total de valor de inventario (a costo de compra): '+money(rows.reduce((n,p)=>n+p.inventory_value_cents,0)):'Valor de inventario pendiente: actualiza el programa de los locales y espera la sincronización.';
  for(const [id,value] of [['filterZero','zero'],['filterLow','low'],['filterAll','all']]){$(id).classList.toggle('selected',filter===value);$(id).setAttribute('aria-pressed',String(filter===value));}
  $('zeroCount').textContent=rows.filter(p=>p.stock===0).length;
  $('lowCount').textContent=rows.filter(p=>p.stock>0&&p.stock<=p.reorder_point).length;
  $('allCount').textContent=rows.length;
  const q=$('directionSearch').value.toLocaleLowerCase('es');
  const matches=rows.filter(p=>(p.name+' '+p.barcode).toLocaleLowerCase('es').includes(q)&&(filter==='all'||(filter==='zero'?p.stock===0:p.stock>0&&p.stock<=p.reorder_point)));
  $('directionCount').textContent=`${matches.length} productos · Mostrando ${Math.min(limit,matches.length)}`;
  $('directionProducts').innerHTML=matches.slice(0,limit).map(p=>`<article class="inventory-card" data-live-key="product-${esc(p.id)}"><div><strong>${esc(p.name)}</strong><small>${esc(p.barcode)}</small><small class="inventory-prices"><span>Venta: ${money(p.price_cents)}</span>${p.purchase_cost_cents!==undefined?`<span class="inventory-purchase-cost">Último costo de compra: ${p.purchase_cost_cents===null?'Sin recepciones':money(p.purchase_cost_cents)}</span>`:''}</small></div><span class="pill ${p.stock===0?'inventory-empty':p.stock<=p.reorder_point?'inventory-low':''}">${p.stock===0?'Agotado':p.stock+' disponibles'}</span><small>Aviso al llegar a ${p.reorder_point} unidades</small></article>`).join('')||'<p>No hay productos en esta selección.</p>';
  $('directionMore').hidden=matches.length<=limit;
  for(const [id,value] of [['filterZero','zero'],['filterLow','low'],['filterAll','all']]){$(id).classList.toggle('selected',filter===value);$(id).setAttribute('aria-pressed',String(filter===value));}
}
async function update(){
  if(pending)return;pending=true;const version=generation;
  try{const data=await api('summary');if(version!==generation)return;const viewState=window.liveView?.capture(document);authenticated=true;$('sessionLoading').hidden=true;document.dispatchEvent(new CustomEvent('brand-permission',{detail:true}));$('directionLogin').hidden=true;$('directionWorkspace').hidden=false;$('directionUser').textContent=data.user;rows=data.products;
    const now=new Date(),localDay=new Date(now.getTime()-now.getTimezoneOffset()*60000).toISOString().slice(0,10);$('directionDay').textContent=(data.day===localDay?'Hoy · ':'Último día recibido · ')+data.day.split('-').reverse().join('/');
    $('directionPayments').innerHTML=data.payments_by_method?[['cash','Efectivo'],['card','Tarjeta'],['transfer','Transferencia / depósito'],['total','Total de formas de pago']].map(([key,label])=>`<article><span>${label}</span><strong>${money(key==='total'?data.payments_by_method.cash+data.payments_by_method.card+data.payments_by_method.transfer:data.payments_by_method[key])}</strong></article>`).join(''):'<p class="error">Reinicia el programa para consultar el desglose por forma de pago.</p>';
    if(!$('directionFees')){const panel=document.createElement('section');panel.id='directionFees';panel.className='payment-summary panel';$('directionPayments').closest('section').after(panel);}const t=data;$('directionFees').innerHTML=`<section class="payment-summary"><h3>Comisiones de tarjeta y neto recibido</h3><div class="payment-summary-grid"><article><span>Comisiones estimadas (IVA incluido)</span><strong>${money(t.card_fee_cents||0)}</strong></article><article><span>Neto después de comisiones</span><strong>${money(t.after_fees_cents??t.net_cents)}</strong></article>${t.profit_cents!==undefined?`<article><span>Ganancia después de comisiones</span><strong>${money(t.profit_after_fees_cents??t.profit_cents)}</strong></article>`:''}</div><p class="muted">La venta total sigue siendo lo que pagó el cliente. La ganancia real anterior es el margen del producto; este bloque descuenta además la comisión estimada. No se asume devolución de comisiones al devolver mercancía. ${t.card_fee_unconfigured_cents?'Hay cobros con tarjeta sin tarifa configurada: el neto está incompleto.':''}</p></section>`;
    $('netSales').textContent=money(data.net_cents);$('grossSales').textContent=money(data.sales_cents);$('refundSales').textContent=money(data.refunds_cents);$('dayTickets').textContent=data.tickets;
    $('profitCard').hidden=$('costCard').hidden=data.profit_cents===undefined;
    $('productProfit').textContent=money(data.profit_cents||0);$('productCost').textContent=money(data.cost_cents||0);
    $('profitWarning').textContent=data.zero_cost_units?'Hay productos vendidos con costo cero; revisa los costos capturados.':'';
    $('directionStatus').textContent=data.coverage_warning||'Última copia de los locales recibida; consulta su fecha de actualización arriba.';window.renderCentralConnections?.(data.connections);
    const state=p=>p.stock===0?'zero':p.stock<=p.reorder_point?'low':'ok';
    if(previous){const changes=rows.filter(p=>state(p)!=='ok'&&previous.get(p.id)!==state(p));if(changes.length){$('notice').textContent=changes.slice(0,3).map(p=>p.name+': '+(p.stock===0?'agotado':p.stock+' disponibles')).join(' · ');$('notice').hidden=false;clearTimeout(update.noticeTimer);update.noticeTimer=setTimeout(()=>$('notice').hidden=true,10000);}}
    previous=new Map(rows.map(p=>[p.id,state(p)]));render();renderManagement(data);document.dispatchEvent(new CustomEvent('direction-summary-updated'));if(viewState)window.liveView.restore(viewState);
  }catch(e){if(version!==generation)return;if(e.status===401||e.status===403){clearPanel();$('loginError').textContent=e.remoteAccess||e.status===403?e.message:'Inicia sesión para consultar Dirección.';$('directionVerify').hidden=!e.remoteAccess;}else{$('sessionLoading').textContent='No se pudo comprobar la sesión. Revisa la conexión y vuelve a cargar.';$('directionStatus').textContent='Sin conexión. Los datos visibles pueden estar desactualizados.';$('loginError').textContent=e.message;}}
  finally{pending=false;}
}
$('directionLoginForm').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;$('loginError').textContent='';$('directionVerify').hidden=true;try{const loginData=Object.fromEntries(new FormData(e.target));await api('login',loginData);document.dispatchEvent(new CustomEvent('login-user-confirmed',{detail:loginData.username}));e.target.reset();await update();}catch(error){$('loginError').textContent=error.message;$('directionVerify').hidden=!error.remoteAccess;}finally{button.disabled=false;}};
$('directionLogout').onclick=async()=>{try{await api('logout',{});clearPanel();}catch(e){$('directionStatus').textContent='No se pudo cerrar la sesión. Intenta de nuevo.';}};
$('directionRefresh').onclick=update;
$('purchaseMore').onclick=()=>{purchaseLimit+=100;renderPurchases();};
document.querySelectorAll('[data-section]').forEach(button=>button.onclick=()=>{$('directionTitle').textContent=button.textContent;$('directionDay').hidden=button.dataset.section!=='day';document.querySelectorAll('.direction-section').forEach(section=>section.hidden=section.id!==button.dataset.section);document.querySelectorAll('[data-section]').forEach(b=>b.classList.toggle('selected',b===button));});
for(const [id,value] of [['filterZero','zero'],['filterLow','low'],['filterAll','all']])$(id).onclick=()=>{filter=value;limit=100;render();};
$('directionSearch').oninput=()=>{limit=100;render();};$('directionMore').onclick=()=>{limit+=100;render();};
setInterval(()=>{if(authenticated&&!document.hidden)update();},10000);
document.addEventListener('visibilitychange',()=>{if(authenticated&&!document.hidden)update();});update();

(()=>{
 const tabs=[...document.querySelectorAll('[data-day-tab]')];
 function select(key){for(const t of tabs){const active=t.dataset.dayTab===key;t.setAttribute('aria-selected',String(active));t.tabIndex=active?0:-1;}document.querySelectorAll('[data-day-panel]').forEach(p=>p.hidden=p.dataset.dayPanel!==key);}
 for(const tab of tabs){tab.onclick=()=>select(tab.dataset.dayTab);tab.onkeydown=e=>{let index=tabs.indexOf(tab);if(e.key==='ArrowRight')index=(index+1)%tabs.length;else if(e.key==='ArrowLeft')index=(index+tabs.length-1)%tabs.length;else if(e.key==='Home')index=0;else if(e.key==='End')index=tabs.length-1;else return;e.preventDefault();select(tabs[index].dataset.dayTab);tabs[index].focus();};}
})();

(()=>{const tabs=[...document.querySelectorAll('[data-purchase-tab]')];function select(key){for(const t of tabs){const active=t.dataset.purchaseTab===key;t.setAttribute('aria-selected',String(active));t.tabIndex=active?0:-1;}document.querySelectorAll('[data-purchase-panel]').forEach(p=>p.hidden=p.dataset.purchasePanel!==key);}for(const tab of tabs){tab.onclick=()=>select(tab.dataset.purchaseTab);tab.onkeydown=e=>{let index=tabs.indexOf(tab);if(e.key==='ArrowRight')index=(index+1)%tabs.length;else if(e.key==='ArrowLeft')index=(index+tabs.length-1)%tabs.length;else if(e.key==='Home')index=0;else if(e.key==='End')index=tabs.length-1;else return;e.preventDefault();select(tabs[index].dataset.purchaseTab);tabs[index].focus();};}})();

// Recarga manual: conserva la ubicación sin guardar credenciales ni cifras.
(()=>{
 const key='lunadev-direction-view';let restoring=false,restored=false;
 addEventListener('pagehide',()=>{if(!authenticated)return;const section=document.querySelector('.direction-section:not([hidden])');const fields={};document.querySelectorAll('.direction-section input:not([type=password]),.direction-section select').forEach(n=>{if(n.id)fields[n.id]=n.value;});sessionStorage.setItem(key,JSON.stringify({section:section?.id,y:scrollY,filter,limit,purchaseLimit,fields,branch:window.centralBranch||''}));});
 document.addEventListener('direction-summary-updated',()=>{if(restored||restoring)return;restored=true;let s;try{s=JSON.parse(sessionStorage.getItem(key)||'null');}catch{}if(!s)return;restoring=true;filter=s.filter||'all';limit=s.limit||100;purchaseLimit=s.purchaseLimit||100;for(const [id,value]of Object.entries(s.fields||{})){const n=document.getElementById(id);if(n)n.value=value;}document.querySelector(`[data-section="${CSS.escape(s.section||'day')}"]`)?.click();render();renderPurchases();requestAnimationFrame(()=>{scrollTo(0,s.y||0);restoring=false;});});
})();
