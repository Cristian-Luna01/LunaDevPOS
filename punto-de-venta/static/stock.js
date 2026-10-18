'use strict';
let stockRows=[],stockLimit=100,stockPending=false;
async function refreshStockAfterWrite(){for(let i=0;stockPending&&i<150;i++)await new Promise(resolve=>setTimeout(resolve,20));await refreshStock();}
function renderStock(){
 const query=$('stockSearch').value.toLocaleLowerCase('es'),filter=$('stockFilter').value;
 const found=stockRows.filter(p=>(p.name+' '+p.barcode).toLocaleLowerCase('es').includes(query)&&(filter==='all'||(filter==='zero'?p.stock===0:p.stock>0&&p.stock<=p.reorder_point)));
 $('stockCount').textContent=`${found.length} productos · Mostrando ${Math.min(stockLimit,found.length)}`;
 const viewState=window.liveView?.capture(document);
 $('stockRows').innerHTML=found.slice(0,stockLimit).map(p=>`<article class="inventory-card" data-live-key="stock-${p.id}"><div><strong>${esc(p.name)}</strong><small>${esc(p.barcode)}</small></div><span class="pill ${p.stock===0?'inventory-empty':p.stock<=p.reorder_point?'inventory-low':''}">${p.stock===0?'Agotado':p.stock+' disponibles'}</span><div class="actions stock-actions">${me?.permissions.includes('products.edit')?`<button type="button" id="stock-edit-${p.id}" data-stock-edit="${p.id}">Editar producto</button>`:''}${me?.permissions.includes('inventory.adjust')?`<button type="button" id="stock-count-${p.id}" data-stock-count="${p.id}">Ajustar existencia</button>`:''}</div></article>`).join('')||'<p>No hay coincidencias.</p>';
 $('stockMore').hidden=found.length<=stockLimit;
 if(viewState)window.liveView.restore(viewState);
}
let stockActionPending=false;
$('stockRows').onclick=act(async event=>{
 const button=event.target.closest('[data-stock-edit],[data-stock-count]');if(!button||stockActionPending)return;stockActionPending=true;
 try{
  const id=Number(button.dataset.stockEdit||button.dataset.stockCount),info=await api('/inventory/product?id='+id);
  if(!me||currentView!=='stock')return;
  if(button.dataset.stockEdit){await productForm(info.product);return;}
  const lots=info.batches,multi=lots.length>1;
  const details=lots.map(b=>`<div class="count-lot"><strong>Lote #${b.id} · ${esc(b.lot_number)}</strong><small>Caducidad: ${esc(b.expires_on||'Sin fecha capturada')}${b.unit_cost_cents!==undefined?' · Costo conservado: '+money(b.unit_cost_cents):''}</small>${multi?`<label>Unidades contadas de este lote<input name="batch_${b.id}" type="number" min="0" max="1000000000" step="1" value="${b.quantity}" required></label>`:''}</div>`).join('');
  modal('Ajustar existencia · '+info.product.name,`<p>Código: ${esc(info.product.barcode)} · Disponible en sistema: <strong>${info.stock}</strong></p>${info.expired_quantity?`<p class="muted">Hay ${info.expired_quantity} unidades en lotes caducados. Se conservan aparte y no se incluyen en este conteo.</p>`:''}<label>Nueva existencia vendible total<input name="counted_quantity" type="number" min="0" max="1000000000" step="1" value="${info.stock}" required></label>${multi?'<p>Cuenta cada lote por separado. Sus cantidades deben sumar la nueva existencia total; se conservan sus costos y caducidades.</p>':''}${details}${!lots.length?'<label><input name="confirm_new_batch" type="checkbox" required> Confirmo que son unidades vendibles adicionales, sin incluir caducados o cuarentena. Se registrarán sin lote/caducidad capturados, con el costo vigente de referencia.</label>':''}<label>Motivo obligatorio<input name="reason" maxlength="500" placeholder="Ejemplo: corrección por conteo físico" required></label><p id="countPreview" role="status"></p>`,async d=>{
   const batch_counts=lots.map(b=>({id:b.id,quantity:multi?Number(d['batch_'+b.id]):Number(d.counted_quantity)}));
   const result=await api('/inventory/count',{product_id:id,version:info.version,counted_quantity:Number(d.counted_quantity),batch_counts,reason:d.reason,confirm_new_batch:d.confirm_new_batch==='on'});
   await refreshStockAfterWrite();await searchProducts();notify(`Existencia ajustada: ${result.stock_before} → ${result.stock_after} · Diferencia ${result.difference>0?'+':''}${result.difference}`);
  },'Registrar ajuste');
  const f=$('dialogForm');
  const preview=()=>{const target=Number(f.elements.counted_quantity.value),sum=lots.reduce((n,b)=>n+(multi?Number(f.elements['batch_'+b.id].value):target),0);$('countPreview').textContent=Number.isInteger(target)&&target>=0?`Antes: ${info.stock} · Después: ${target} · Diferencia: ${target-info.stock}${multi&&sum!==target?' · La suma de lotes todavía no coincide.':''}`:'Introduce unidades enteras.';$('dialogSubmit').disabled=!Number.isInteger(target)||target<0||(multi?!lots.some(b=>Number(f.elements['batch_'+b.id].value)!==b.quantity):target===info.stock)||(multi&&sum!==target);};
  $('dialogBody').oninput=event=>{if(multi&&event.target.name.startsWith('batch_'))f.elements.counted_quantity.value=lots.reduce((n,b)=>n+Number(f.elements['batch_'+b.id].value),0);preview();};preview();
 }finally{stockActionPending=false;}
});
async function refreshStock(){if(!me||currentView!=='stock'||stockPending||document.hidden)return;stockPending=true;const user=me.user.id;try{const r=await api('/inventory/overview');if(!me||me.user.id!==user)return;stockRows=r.products;$('stockValue').hidden=r.inventory_value_cents===undefined;$('stockValue').textContent='Total de valor de inventario (a costo de compra): '+money(r.inventory_value_cents||0);renderStock();$('stockStatus').textContent='Actualizado '+new Date().toLocaleTimeString('es-MX')+' · Revisión cada 10 segundos.';}catch(e){$('stockStatus').textContent='No se pudo actualizar. Los datos pueden estar desactualizados.';}finally{stockPending=false;}}
document.querySelector('[data-view="stock"]').addEventListener('click',refreshStock);
$('stockRefresh').onclick=refreshStock;$('stockSearch').oninput=()=>{stockLimit=100;renderStock();};$('stockFilter').onchange=()=>{stockLimit=100;renderStock();};$('stockMore').onclick=()=>{stockLimit+=100;renderStock();};
$('logout').addEventListener('click',()=>{stockRows=[];$('stockRows').replaceChildren();});
setInterval(refreshStock,10000);document.addEventListener('visibilitychange',refreshStock);
