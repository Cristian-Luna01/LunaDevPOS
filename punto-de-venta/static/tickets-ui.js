'use strict';
(()=>{
 const dialog=document.createElement('dialog');dialog.id='ticketHistoryDialog';dialog.className='ticket-history-dialog';dialog.setAttribute('aria-labelledby','ticketHistoryTitle');
 dialog.innerHTML=`<div class="ticket-history-header"><h2 id="ticketHistoryTitle">Historial de tickets</h2><button type="button" id="ticketHistoryClose" aria-label="Cerrar historial de tickets">×</button></div><form id="ticketHistoryFilters" class="overview-controls"><label>Desde<input id="ticketFrom" type="date" required></label><label>Hasta<input id="ticketTo" type="date" required></label><button type="submit">Consultar</button></form><p id="ticketHistoryStatus" class="muted" role="status"></p><div id="ticketHistoryList"></div><button type="button" id="ticketHistoryMore" hidden>Ver más tickets</button><section id="ticketHistoryDetail" hidden></section>`;
 document.body.append(dialog);attachOutsideClose(dialog,()=>true);
 let version=0,next=null,rows=[],scope='own';
 const states={completed:'Confirmado',partial_return:'Devolución parcial',returned:'Devuelto',voided:'Anulado'};
 const methods={cash:'Efectivo',debit:'Tarjeta de débito',credit:'Tarjeta de crédito',transfer:'Transferencia / depósito'};
 const time=value=>{const d=new Date(value);return Number.isNaN(d.getTime())?value:d.toLocaleString('es-MX');};
 const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
 function showList(){
  $('ticketHistoryDetail').hidden=true;$('ticketHistoryList').hidden=false;$('ticketHistoryFilters').hidden=false;$('ticketHistoryMore').hidden=!next;
  $('ticketHistoryList').innerHTML=rows.map(t=>`<button type="button" class="ticket-history-row" data-ticket-id="${t.id}"><span><strong>Ticket #${t.id}</strong><small>${esc(time(t.created_at))}</small><small>${esc(t.customer_name||'Público general')} · ${esc(t.seller_name)}</small><small>${esc(states[t.status]||t.status)}${t.on_account?' · Venta a crédito':''} · ${t.line_count} ${t.line_count===1?'partida':'partidas'}</small></span><strong>${money(t.total_cents)}</strong></button>`).join('')||'<p class="empty">No hay tickets en las fechas seleccionadas.</p>';
  $('ticketHistoryStatus').textContent=`${rows.length} ${rows.length===1?'ticket mostrado':'tickets mostrados'}${next?' · Hay más resultados':''}. ${scope==='own'?'Se muestran tus ventas según tus permisos.':'Se muestran las ventas de todos los vendedores.'}`;
 }
 async function load(more=false){
  const current=++version,owner=me?.user.id;if(!more){rows=[];next=null;$('ticketHistoryList').replaceChildren();}
  $('ticketHistoryDetail').hidden=true;$('ticketHistoryList').hidden=false;$('ticketHistoryStatus').textContent='Consultando tickets…';$('ticketHistoryMore').hidden=true;
  try{
   const q=new URLSearchParams({from:$('ticketFrom').value,to:$('ticketTo').value});if(more&&next)q.set('before',next);
   const r=await api('/tickets?'+q);if(current!==version||!dialog.open||me?.user.id!==owner)return;
   rows=more?[...rows,...r.items]:r.items;next=r.next_before;scope=r.scope;showList();
  }catch(e){if(current===version&&dialog.open){$('ticketHistoryStatus').textContent=e.message;$('ticketHistoryMore').hidden=true;}}
 }
 async function detail(id){
  const current=++version,owner=me?.user.id;$('ticketHistoryStatus').textContent='Consultando ticket…';
  try{
   const t=await api('/ticket?id='+id);if(current!==version||!dialog.open||me?.user.id!==owner)return;
   $('ticketHistoryList').hidden=true;$('ticketHistoryFilters').hidden=true;$('ticketHistoryMore').hidden=true;
   const received=t.payments.reduce((n,p)=>n+p.tendered_cents,0);
   $('ticketHistoryDetail').innerHTML=`<button type="button" id="ticketHistoryBack">← Volver a los tickets</button><h3>Ticket #${t.id}</h3><p>${esc(time(t.created_at))}<br>Vendedor: ${esc(t.seller_name)}<br>Cliente: ${esc(t.customer_name||'Público general')}<br>Estado: ${esc(states[t.status]||t.status)}</p>${t.on_account?'<p class="muted">Venta registrada a crédito. Los abonos posteriores se consultan en Clientes - Créditos; no son nuevos tickets de venta.</p>':''}${t.items.map(i=>`<article class="ticket-item"><strong>${i.quantity} × ${esc(i.product_name)}</strong><small>Precio unitario antes de descuento: ${money(i.unit_price_cents)} · Descuento de esta partida: ${money(i.discount_cents)}</small><strong>${money(i.total_cents)}</strong></article>`).join('')}<p>Descuento total: <strong>${money(t.discount_cents)}</strong><br>IVA incluido: <strong>${money(t.tax_cents)}</strong></p><h3>Total de la venta: ${money(t.total_cents)}</h3>${t.payments.map(p=>`<p>${esc(methods[p.method]||p.method)}: <strong>${money(p.amount_cents)}</strong>${p.method==='cash'?` · Recibido: ${money(p.tendered_cents)}`:''}</p>`).join('')}<p>Recibido al hacer la venta: <strong>${money(received)}</strong><br>Cambio entregado: <strong>${money(t.change_cents)}</strong></p>${t.status!=='completed'?'<p class="muted">Los importes corresponden a la compra original. Este ticket tiene devolución o anulación; consulta su movimiento en Historial.</p>':''}`;
   $('ticketHistoryDetail').hidden=false;$('ticketHistoryBack').onclick=()=>{version++;showList();dialog.scrollTop=0;};$('ticketHistoryStatus').textContent='Detalle de la compra original';dialog.scrollTop=0;
  }catch(e){if(current===version&&dialog.open)$('ticketHistoryStatus').textContent=e.message;}
 }
 $('ticketHistoryOpen').onclick=()=>{if(!me||currentView!=='checkout')return;const day=today();$('ticketFrom').value=$('ticketTo').value=day;$('ticketFrom').max=$('ticketTo').max=day;$('ticketHistoryFilters').hidden=false;dialog.showModal();dialog.scrollTop=0;load();};
 $('ticketHistoryClose').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{version++;rows=[];next=null;$('ticketHistoryList').replaceChildren();$('ticketHistoryDetail').replaceChildren();});
 $('ticketHistoryFilters').onsubmit=e=>{e.preventDefault();load();};$('ticketHistoryMore').onclick=()=>load(true);
 $('ticketHistoryList').onclick=e=>{const b=e.target.closest('[data-ticket-id]');if(b)detail(Number(b.dataset.ticketId));};
})();
