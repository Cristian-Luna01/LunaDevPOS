'use strict';
const $ = id => document.getElementById(id);
const money = c => (c/100).toLocaleString('es-MX',{style:'currency',currency:'MXN'});
const esc = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cents = value => { const s=(String(value??'0').trim()||'0'); if(!/^\d+(\.\d{1,2})?$/.test(s)) throw Error('Usa un importe positivo con hasta 2 decimales'); const [a,b='']=s.split('.'); const n=Number(a)*100+Number(b.padEnd(2,'0'));if(!Number.isSafeInteger(n))throw Error('Importe demasiado grande');return n; };
let me, products=[], customers=[], cart=[], page=0, currentView='checkout', dialogCallback, busy=false, pendingSale=null, queryVersion=0, customerVersion=0;
function notify(message){$('notice').textContent=message;$('notice').hidden=false;clearTimeout(notify.timer);notify.timer=setTimeout(()=>$('notice').hidden=true,6500);}
async function api(path,data){const r=await fetch('/api'+path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json','X-POS-Request':'1'}:{},body:data?JSON.stringify(data):undefined});const body=await r.json();if(!r.ok){if(r.status===401){$('workspace').hidden=true;$('login').hidden=false;}throw Error(body.error||'No se pudo completar la operación');}return body;}
const act = fn => async (...args) => {try{await fn(...args);}catch(e){notify(e.message);}};
async function refresh(requireOpening=false){me=await api('/me');await window.refreshCardFees?.();document.dispatchEvent(new CustomEvent('brand-permission',{detail:me.permissions.includes('users.manage')}));$('identity').textContent=me.user.display_name;$('shiftStatus').textContent=me.shift?(me.shift.shift_number?`Turno ${me.shift.shift_number}`:'Turno abierto'):'Sin turno abierto';$('gateAdmin').hidden=!me.permissions.includes('users.manage');$('openShift').disabled=!!me.shift;$('closeForm').hidden=!me.shift;document.querySelectorAll('[data-permission]').forEach(b=>b.hidden=!me.permissions.includes(b.dataset.permission));$('workspace').hidden=false;$('login').hidden=true;await Promise.all([searchProducts(),loadCustomers()]);if(requireOpening&&me.permissions.includes('sell')&&!me.shift)showShiftGate();}
$('loginForm').onsubmit=act(async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));await api('/login',d);document.dispatchEvent(new CustomEvent('login-user-confirmed',{detail:d.username}));$('notice').hidden=true;e.target.reset();await refresh(true);});
$('logout').onclick=act(async()=>{me=await api('/me');if(me?.shift){$('shiftGate').hidden=true;$('workspace').hidden=false;document.querySelector('[data-view="cash"]').click();notify('Antes de salir, cuenta el efectivo y confirma el cierre de turno.');$('closeForm').elements.counted.focus();return;}await api('/logout',{});$('shiftGate').hidden=true;cart=[];pendingSale=null;me=null;currentView='checkout';document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!=='checkout');$('pageTitle').textContent='Mostrador';$('workspace').classList.add('checkout-mode');$('notice').hidden=true;renderCart();$('dialog').close();$('workspace').hidden=true;$('login').hidden=false;$('report').innerHTML='<h2>Resumen del corte</h2>';$('adminResult').replaceChildren();$('receipt').replaceChildren();});
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{if(b.dataset.view==='checkout'&&me?.permissions.includes('sell')&&!me.shift){showShiftGate();return;}currentView=b.dataset.view;document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==currentView);document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('selected',x===b));$('pageTitle').textContent=b.textContent;$('workspace').classList.toggle('checkout-mode',currentView==='checkout');});
function renderProducts(){
 $('products').innerHTML=products.map((p,i)=>{const reserved=cart.find(l=>l.product.id===p.id)?.quantity||0;return `<button class="product" data-index="${i}"><strong>${esc(p.name)}</strong><small>${esc(p.generic_name||p.barcode)}</small><b>${promotionLabel(p)}</b><span class="stock">${Math.max(0,p.stock-reserved)} disponibles · ${reserved} en carrito</span></button>`;}).join('')||`<p class="empty">${$('search').value.trim()?'No hay coincidencias.':'Busca un producto o escanea su código para comenzar. Consulta las ofertas en Promociones.'}</p>`;
}
async function searchProducts(more=false){const version=++queryVersion;if(!more)page=0;const q=$('search').value.trim();if(!q){products=[];$('moreProducts').hidden=true;renderProducts();return;}const result=await api('/products?q='+encodeURIComponent(q)+'&offset='+page*40);if(version!==queryVersion)return;products=more?[...products,...result]:result;$('moreProducts').hidden=result.length<40;renderProducts();if(result.some(p=>p.barcode===q)&&document.activeElement===$('search'))$('search').select();}
let searchTimer;
function updateSearchClear(){if($('clearSearch'))$('clearSearch').hidden=!$('search').value;}
function clearCheckoutSearch(focus=false){
 clearTimeout(searchTimer);scanBuffer='';scanLast=0;scanTarget=null;$('search').value='';queryVersion++;page=0;products=[];$('moreProducts').hidden=true;renderProducts();updateSearchClear();
 if(focus)$('search').focus();
}
$('search').oninput=()=>{updateSearchClear();clearTimeout(searchTimer);searchTimer=setTimeout(act(()=>searchProducts()),160);};
if($('clearSearch'))$('clearSearch').onclick=()=>clearCheckoutSearch(true);
let barcodeQueue=Promise.resolve();
$('search').onfocus=()=>clearCheckoutSearch();
$('search').onkeydown=act(async e=>{
 if(e.key!=='Enter'&&!(e.key==='Tab'&&/^\d{6,}$/.test($('search').value.trim())))return;
 e.preventDefault();const code=$('search').value.trim();if(!code)return;
 const owner=me?.user?.id,shift=me?.shift?.id;
 clearCheckoutSearch();const version=queryVersion;
 barcodeQueue=barcodeQueue.then(async()=>{
  if(!me?.shift||me.shift.id!==shift||me.user?.id!==owner)return;
  const found=await api('/products?q='+encodeURIComponent(code)+'&offset=0');
  if(!me?.shift||me.shift.id!==shift||me.user?.id!==owner)return;
  const exact=found.find(p=>p.barcode===code);
  if(exact)await add(exact);
  else if(version===queryVersion&&!$('search').value){products=found;$('moreProducts').hidden=found.length<40;renderProducts();if(!found.length)notify('No se encontró el producto con código o nombre: '+code);}
  if(currentView==='checkout'&&!$('dialog').open&&(!document.activeElement||document.activeElement===$('search')||document.activeElement===document.body))$('search').focus();
 }).catch(error=>notify(error.message||'No se pudo buscar el producto. Escanea nuevamente.'));
 await barcodeQueue;
});
// El lector HID se reconoce por una ráfaga rápida terminada en Enter.
// Dentro del buscador se descarta el prefijo anterior solo al reconocer la lectura completa.
let scanBuffer='',scanLast=0,scanTarget=null;
document.addEventListener('keydown',e=>{
 const reset=()=>{scanBuffer='';scanLast=0;scanTarget=null;};
 if(!me?.shift||currentView!=='checkout'||$('workspace').hidden||document.querySelector('dialog[open]')||!$('shiftGate').hidden||e.ctrlKey||e.altKey||e.metaKey){reset();return;}
 const target=e.target,inSearch=target===$('search');
 if(!inSearch&&target?.closest?.('input,textarea,select,[contenteditable="true"]')){reset();return;}
 const now=e.timeStamp||Date.now(),gap=inSearch?35:80;
 if(e.key==='Enter'){
  const code=scanBuffer,valid=scanTarget===target&&code.length>=4&&now-scanLast<=(inSearch?75:100);reset();
  if(valid){e.preventDefault();e.stopImmediatePropagation();$('search').value=code;$('search').onkeydown(e);}
  return;
 }
 if(e.key.length===1&&!/\s/.test(e.key)&&!e.repeat){
  if(scanTarget!==target||now-scanLast>gap)scanBuffer='';scanBuffer=(scanBuffer+e.key).slice(-500);scanLast=now;scanTarget=target;
  if(!inSearch)e.preventDefault();
 }else if(e.key!=='Shift')reset();
},true);
$('moreProducts').onclick=act(async()=>{page++;await searchProducts(true);});
$('products').onclick=act(async e=>{const button=e.target.closest('[data-index]');if(button)await add(products[Number(button.dataset.index)]);});
async function add(product){
  if(!me?.shift){showShiftGate();return;}
  const line=cart.find(l=>l.product.id===product.id);
  if((line?.quantity||0)>=product.stock){notify(`Solo hay ${product.stock} unidades disponibles de ${product.name}`);return;}
  pendingSale=null;
  if(line){line.product.stock=product.stock;line.quantity++;renderCart();return;}
  if(product.requires_prescription){modal('Datos de receta',fields([{name:'doctor_name',label:'Nombre del médico'},{name:'license_number',label:'Cédula'},{name:'prescription_ref',label:'Folio de receta'}]),async d=>{cart.push({product,quantity:1,prescription:d});renderCart();});}
  else{cart.push({product,quantity:1});renderCart();}
}
async function checkCartStock(){
  if(!cart.length)return true;
  const stock=await api('/inventory/availability?ids='+cart.map(l=>l.product.id).join(','));
  let changed=false;
  for(const line of cart){const fresh=stock.find(p=>p.id===line.product.id);if(fresh&&(line.product.price_cents!==fresh.price_cents||JSON.stringify(line.product.promotion)!==JSON.stringify(fresh.promotion))){Object.assign(line.product,fresh);changed=true;}line.product.stock=fresh?.stock||0;if(line.quantity>line.product.stock){line.quantity=line.product.stock;changed=true;}}
  cart=cart.filter(l=>l.quantity>0);
  if(changed){pendingSale=null;renderCart();notify('Cambió la existencia o el precio. Actualizamos la venta; revisa la venta antes de cobrar.');}
  return !changed;
}
function customer(){return customers.find(c=>c.id===Number($('customer').value));}
function promotionLabel(p){const offer=p.promotion;return offer?`${offer.bundle_quantity} por ${money(offer.price_cents)} · Promoción`:money(p.price_cents)+' / unidad';}
function promotionTotal(p,qty){const offer=p.promotion;return offer?Math.min(p.price_cents*qty,Math.floor(qty/offer.bundle_quantity)*offer.price_cents+(qty%offer.bundle_quantity)*p.price_cents):p.price_cents*qty;}
function totals(){let total=0,discount=0;const rate=customer()?.discount_bps||0;for(const l of cart){const gross=l.product.price_cents*l.quantity;const d=Math.max(Math.floor((gross*rate+5000)/10000),gross-promotionTotal(l.product,l.quantity));discount+=d;total+=gross-d;}return {total,discount};}
function renderCart(){renderProducts();const t=totals();$('cart').innerHTML=cart.map((l,i)=>`<div class="cart-row"><div><strong>${esc(l.product.name)}</strong><small>${promotionLabel(l.product)}</small></div><input aria-label="Cantidad de ${esc(l.product.name)}" type="number" min="1" max="${l.product.stock}" value="${l.quantity}" data-qty="${i}"><button data-remove="${i}" aria-label="Quitar ${esc(l.product.name)}">×</button></div>`).join('')||'<p class="empty">Agrega un producto para comenzar</p>';$('discount').textContent=money(t.discount);$('total').textContent=money(t.total);}
$('cart').oninput=e=>{
  if(e.target.dataset.qty===undefined)return;
  const line=cart[Number(e.target.dataset.qty)],q=Number(e.target.value);
  if(!Number.isInteger(q)||q<1)return;
  line.quantity=Math.min(q,line.product.stock);pendingSale=null;
  if(q>line.product.stock){e.target.value=line.quantity;notify(`Solo hay ${line.product.stock} unidades disponibles de ${line.product.name}`);}
  renderProducts();const t=totals();$('discount').textContent=money(t.discount);$('total').textContent=money(t.total);
};
$('cart').onchange=()=>renderCart();
$('cart').onclick=e=>{const b=e.target.closest('[data-remove]');if(b){cart.splice(Number(b.dataset.remove),1);pendingSale=null;renderCart();}};
$('clearCart').onclick=()=>{cart=[];pendingSale=null;renderCart();};
function renderCustomerResults(){
 const query=$('customerSearch').value.trim().toLocaleLowerCase('es-MX');
 const found=customers.filter(c=>c.name.toLocaleLowerCase('es-MX').includes(query)||String(c.phone||'').toLocaleLowerCase('es-MX').includes(query));
 $('customerResults').hidden=!query;
 $('customerResults').innerHTML=query?(found.map(c=>`<button type="button" data-customer-id="${c.id}">${esc(c.name)}${c.phone?' · '+esc(c.phone):''}</button>`).join('')||'<p class="muted">No se encontraron clientes.</p>'):'';
}
async function loadCustomers(){
 const version=++customerVersion,selected=$('customer').value;
 const found=await api('/customers');
 if(version!==customerVersion)return;
 customers=found;
 $('customer').innerHTML='<option value="">Público general</option>'+customers.map(c=>`<option value="${c.id}">${esc(c.name)} · ${c.discount_bps/100}%</option>`).join('');
 $('customer').value=customers.some(c=>String(c.id)===selected)?selected:'';
 renderCustomerResults();renderCart();
}
$('customerSearch').oninput=renderCustomerResults;
$('customerResults').onclick=e=>{const button=e.target.closest('[data-customer-id]');if(!button)return;$('customer').value=button.dataset.customerId;pendingSale=null;$('customerResults').hidden=true;$('customerSearch').value='';renderCart();};
$('customer').onchange=()=>{pendingSale=null;renderCart();};
function fields(spec){return spec.map(f=>`<label>${esc(f.label)}<input name="${esc(f.name)}" type="${f.type||'text'}" value="${esc(f.value??'')}" ${f.optional?'':'required'} ${f.type==='number'?'step="1"':''}></label>`).join('');}
function modal(title,html,callback,label='Confirmar'){if(busy)return;$('changePreview').hidden=true;$('dialogBody').oninput=null;$('dialogTitle').textContent=title;$('dialogBody').innerHTML=html;$('dialogError').textContent='';$('dialogSubmit').textContent=label;$('dialogSubmit').disabled=false;$('dialogSubmit').hidden=!callback;dialogCallback=callback;$('dialog').showModal();$('dialog').scrollTop=0;}
$('closeDialog').onclick=()=>{if(!busy)$('dialog').close();};$('dialog').addEventListener('cancel',e=>{if(busy)e.preventDefault();});
$('dialogForm').onsubmit=async e=>{e.preventDefault();if(busy||!dialogCallback)return;busy=true;$('dialogSubmit').disabled=true;try{const d=Object.fromEntries(new FormData(e.target));await dialogCallback(d);$('dialog').close();}catch(err){$('dialogError').textContent=err.message;}finally{busy=false;$('dialogSubmit').disabled=false;}};
$('pay').onclick=act(async()=>{
 if(!me.shift)throw Error('Abre un turno en Caja y corte');
 if(!cart.length)throw Error('Agrega un producto');
 if(!await checkCartStock())return;
 const canCredit=me.permissions.includes('customers.manage');
 const creditCustomers=canCredit?await api('/credit'):[];
 let paymentTotal=totals().total;
 modal('Cobrar '+money(paymentTotal),`<p>Selecciona la forma de pago.</p><div class="actions payment-methods" role="group" aria-label="Forma de pago"><button type="button" data-method="cash" aria-pressed="false">Efectivo</button><button type="button" data-method="debit" aria-pressed="false">Tarjeta</button><button type="button" data-method="transfer" aria-pressed="false">Transferencia</button>${canCredit?'<button type="button" data-method="on_account" aria-pressed="false">Crédito</button>':''}</div><div id="cardFeePreview" class="abono-summary" hidden></div><input type="hidden" name="method"><p id="paymentSelection" class="muted" role="status">Selecciona una modalidad para continuar.</p><label id="receivedLabel">Importe recibido<input name="received" inputmode="decimal" value="0.00" disabled></label>${canCredit?`<div id="creditCustomerPanel" hidden><label>Cliente de la cuenta<select name="credit_customer" disabled><option value="">Selecciona un cliente</option>${creditCustomers.map(c=>`<option value="${c.id}" ${c.id===customer()?.id?'selected':''}>${esc(c.name)}${c.phone?' · '+esc(c.phone):''}</option>`).join('')}</select></label><p id="creditBalance" class="muted"></p><p>El total se agregará a la deuda del cliente. Los abonos se registran en Clientes - Créditos.</p>${creditCustomers.length?'':'<p>No hay clientes registrados. Registra uno en Clientes - Créditos antes de confirmar.</p>'}</div>`:''}`,async d=>{
  if(!updatePaymentPreview(paymentTotal))throw Error('Revisa la modalidad, el cliente y el importe');
  const on_account=d.method==='on_account';
  const payments=on_account||paymentTotal===0?[]:[{method:d.method,amount_cents:paymentTotal,...(d.method==='cash'?{tendered_cents:cents(d.received)}:{})}];
  const body={on_account,customer_id:on_account?Number(d.credit_customer):customer()?.id||null,items:cart.map(l=>({product_id:l.product.id,quantity:l.quantity,...(l.prescription?{prescription:l.prescription}:{})})),payments};
  const signature=JSON.stringify(body);if(!pendingSale||pendingSale.signature!==signature)pendingSale={signature,key:crypto.randomUUID()};
  const ticket=await api('/sales',{...body,request_key:pendingSale.key});cart=[];pendingSale=null;renderCart();clearCheckoutSearch();renderReceipt(ticket);notify(`Ticket #${ticket.id} ${on_account?'registrado a crédito':'confirmado · Cambio '+money(ticket.change_cents)}`);await searchProducts();
 },'Confirmar venta');
 $('changePreview').hidden=false;
 const form=$('dialogForm');
 function syncCreditCustomer(){
  const id=Number(form.elements.credit_customer?.value)||null;
  const selected=creditCustomers.find(c=>c.id===id);
  const current=customers.find(c=>c.id===id);if(selected&&current)Object.assign(current,selected);
  if(selected&&!customers.some(c=>c.id===id)){
   customers.push(selected);const option=document.createElement('option');option.value=String(id);option.textContent=selected.name+' · '+selected.discount_bps/100+'%';$('customer').append(option);
  }
  $('customer').value=id?String(id):'';pendingSale=null;renderCart();paymentTotal=totals().total;
  $('dialogTitle').textContent='Cobrar '+money(paymentTotal);
  $('creditBalance').textContent=selected?`Deuda actual: ${money(selected.balance_cents)} · Saldo después de esta compra: ${money(selected.balance_cents+paymentTotal)}`:'Selecciona al cliente que recibirá el crédito.';
 }
 $('dialogBody').onclick=e=>{
  const button=e.target.closest('[data-method]');if(!button)return;
  const method=button.dataset.method;form.elements.method.value=method;
  const onAccount=method==='on_account';
  $('dialogBody').querySelectorAll('[data-method]').forEach(b=>{const active=b===button;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active));});
  $('paymentSelection').textContent='Modalidad seleccionada: '+button.textContent;
  $('receivedLabel').hidden=onAccount;form.elements.received.disabled=onAccount;form.elements.received.value=onAccount?'0.00':(paymentTotal/100).toFixed(2);
  if(canCredit){$('creditCustomerPanel').hidden=!onAccount;form.elements.credit_customer.disabled=!onAccount;form.elements.credit_customer.required=onAccount;if(onAccount)syncCreditCustomer();}
  $('dialogSubmit').textContent=onAccount?'Confirmar venta a crédito':'Confirmar venta';updatePaymentPreview(paymentTotal);
 };
 $('dialogBody').oninput=()=>{if(form.elements.method.value==='on_account')syncCreditCustomer();updatePaymentPreview(paymentTotal);};
 if(canCredit)form.elements.credit_customer.onchange=()=>{syncCreditCustomer();updatePaymentPreview(paymentTotal);};
 updatePaymentPreview(paymentTotal);
});
function updatePaymentPreview(total){
 const f=$('dialogForm');try{
  const method=f.elements.method.value;const debt=method==='on_account';const received=cents(f.elements.received.value);
  window.showCardFeePreview?.(method,total);
  const issue=debt?(total<=0?'Una venta a crédito debe tener un total mayor que cero.':f.elements.credit_customer?.value?'':'Selecciona un cliente para registrar la venta a crédito.'):!method?'Selecciona una forma de pago.':total===0&&received!==0?'El total es cero: no se debe recibir dinero.':method==='cash'&&received<total?'El importe recibido no cubre el total.':method!=='cash'&&received!==total?'Tarjeta y transferencia deben cubrir el total exacto.':'';
  $('changeAmount').textContent=money(!debt&&method==='cash'?Math.max(0,received-total):0);$('dialogError').textContent=issue;return !issue;
 }catch(e){$('dialogError').textContent=e.message;$('changeAmount').textContent='—';return false;}
}
function renderReceipt(t){$('receipt').innerHTML=`<img class="receipt-logo" src="/business-logo.png" alt="Logotipo" ${window.businessSettings?.has_logo?'':'hidden'}><h2>${esc(window.businessSettings?.name||'Punto de venta')}</h2><p>Ticket #${t.id}<br>${esc(t.created_at)}<br>Estado: ${t.on_account?'Crédito · pendiente en cartera':esc(t.status)}</p>`+t.items.map(i=>`<div class="report-line"><span>${i.quantity} × ${esc(i.product_name)}</span><b>${money(i.total_cents)}</b></div>`).join('')+`<p>Descuento: ${money(t.discount_cents)}<br>IVA incluido: ${money(t.tax_cents)}</p><h2>Total ${money(t.total_cents)}</h2>`+t.payments.map(p=>`<p>${esc(({cash:'Efectivo',debit:'Tarjeta',credit:'Tarjeta',transfer:'Transferencia'})[p.method]||p.method)}: ${money(p.amount_cents)}</p>`).join('')+`<p>Cambio: ${money(t.change_cents)}</p><p>${esc(window.businessSettings?.receipt_footer||'')}</p><small>Comprobante de venta. No es factura fiscal.</small>`;
 const box=document.createElement('div');box.className='print-actions';box.innerHTML='<p>Último ticket confirmado</p><button data-width="80">Imprimir 80 mm</button> <button data-width="58">Imprimir 58 mm</button>';(currentView==='manage'?$('adminResult'):$('cart')).append(box);box.onclick=e=>{if(e.target.dataset.width){$('receipt').classList.toggle('narrow',e.target.dataset.width==='58');window.print();}};}
$('openShift').onclick=()=>modal('Abrir turno','<label>Turno<select name="shift_number"><option value="1">Turno 1</option><option value="2">Turno 2</option></select></label>'+fields([{name:'opening',label:'Fondo inicial',value:'0.00'}]),async d=>{await api('/shifts/open',{shift_number:Number(d.shift_number),opening_cents:cents(d.opening)});await refresh();notify('Turno abierto');});
function renderReport(r){const rows=[['Fondo inicial',r.opening_cents],...Object.entries(r.sales_by_method).map(([k,v])=>['Ventas · '+({cash:'Efectivo',debit:'Débito',credit:'Crédito',transfer:'Transferencia'}[k]),v]),...Object.entries(r.refunds_by_method).map(([k,v])=>['Devoluciones · '+({cash:'Efectivo',debit:'Débito',credit:'Crédito',transfer:'Transferencia'}[k]),-v]),['Crédito registrado (fuera de las ventas totales)',r.on_account_cents||0],...Object.entries(r.collections_by_method||{}).map(([k,v])=>['Abonos · '+({cash:'Efectivo',debit:'Tarjeta',transfer:'Transferencia'}[k]),v]),['Entradas extraordinarias',r.incoming_cents],['Salidas de caja',-r.outgoing_cents],['Efectivo esperado',r.expected_cents]];if(r.profit_cents!==undefined)rows.push(['Ventas totales del turno',r.net_sales_cents],['Costo correspondiente a lo cobrado',r.cost_cents],['Ganancia real',r.profit_cents]);if(r.counted_cents!==undefined)rows.push(['Efectivo contado',r.counted_cents],['Sobrante / faltante',r.difference_cents]);$('report').innerHTML=`<h2>Corte ${esc(r.type)} · Turno #${r.shift_id}</h2>`+rows.map(([label,value])=>`<div class="report-line"><span>${esc(label)}</span><b>${money(value)}</b></div>`).join('')+(r.profit_cents!==undefined?'<p class="muted">Ganancia real = cobros menos el costo correspondiente de los productos, considerando devoluciones. No descuenta gastos del negocio.'+(r.zero_cost_units?' Hay movimientos con costo cero; revisa tus costos.':'')+'</p>':'')+'<h2>Cobros netos por departamento</h2>'+r.departments.map(d=>`<div class="report-line"><span>${esc(d.name)}</span><b>${money(d.net_cents)}</b></div>`).join('')+'<h2>Movimientos y proveedores</h2>'+r.movements.map(m=>`<p>${esc(m.category)} · ${money(m.amount_cents)}<br>${esc(m.supplier_name||'')} ${esc(m.invoice_ref||'')} · ${esc(m.concept)}</p>`).join('');}
$('closeForm').onsubmit=act(async e=>{e.preventDefault();if(!me.shift||busy)return;const payload={shift_id:me.shift.id,counted_cents:cents(new FormData(e.target).get('counted'))};busy=true;const b=e.target.querySelector('button');b.disabled=true;try{const r=await api('/shifts/close',payload);renderReport(r);if(r.automatic_backup){const note=document.createElement('p');note.className=r.automatic_backup.ok?'muted':'error';note.textContent=r.automatic_backup.ok?'Respaldo completo automático guardado (conservación: 30 días). Carpeta: '+r.automatic_backup.path:r.automatic_backup.warning;$('report').append(note);}await refresh();}finally{busy=false;b.disabled=false;}});
$('reportX').onclick=act(async()=>{if(!me.shift)throw Error('No hay turno abierto');renderReport(await api('/shifts/report?id='+me.shift.id));});
async function cashForm(direction){const suppliers=await api('/suppliers');modal(direction==='in'?'Entrada extraordinaria':'Salida de efectivo',fields([{name:'amount',label:'Importe'},{name:'concept',label:'Concepto'}])+(direction==='out'?'<label>Categoría<select name="category"><option value="supplier">Pago a proveedor</option><option value="expense">Gasto operativo</option><option value="safekeeping">Retiro / resguardo</option></select></label><label>Proveedor<select name="supplier_id"><option value="">Seleccionar</option>'+suppliers.map(s=>`<option value="${s.id}">${esc(s.business_name)}</option>`).join('')+'</select></label>'+fields([{name:'invoice_ref',label:'Folio de factura / nota (obligatorio para proveedor)',optional:true}]):''),async d=>{await api('/cash',{direction,category:direction==='in'?'change':d.category,amount_cents:cents(d.amount),concept:d.concept,supplier_id:d.category==='supplier'?Number(d.supplier_id)||null:null,invoice_ref:d.invoice_ref||null});notify('Movimiento registrado');});}
$('cashIn').onclick=act(()=>cashForm('in'));$('cashOut').onclick=act(()=>cashForm('out'));
function table(rows){if(!rows.length){$('adminResult').innerHTML='<p>Sin registros.</p>';return;}const keys=Object.keys(rows[0]);$('adminResult').innerHTML='<table><thead><tr>'+keys.map(k=>`<th>${esc(({net_sales_cents:'Ventas netas',expected_cents:'Efectivo esperado',counted_cents:'Efectivo contado',difference_cents:'Diferencia',opening_cents:'Fondo inicial',total_cents:'Total',price_cents:'Precio',cost_cents:'Costo',unit_price_cents:'Precio unitario',unit_cost_cents:'Costo unitario',amount_cents:'Importe',discount_cents:'Descuento',tax_cents:'Impuestos',unit_margin_cents:'Margen',id:'Folio',register_id:'Caja',opened_at:'Apertura',closed_at:'Cierre'})[k]||k.replace(/_cents$/,' (MXN)'))}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+keys.map(k=>`<td>${esc(k.endsWith('_cents')?(r[k]===null?'Pendiente':money(r[k])):(typeof r[k]==='object'?JSON.stringify(r[k]):r[k]))}</td>`).join('')+'</tr>').join('')+'</tbody></table>';}
async function productForm(p={}){const categories=await api('/categories');modal(p.id?'Editar producto #'+p.id:'Nuevo producto',fields([{name:'barcode',label:'Código de barras',value:p.barcode},{name:'name',label:'Nombre comercial',value:p.name},{name:'generic_name',label:'Sustancia activa',value:p.generic_name,optional:true},{name:'price',label:'Precio con impuestos',value:((p.price_cents||0)/100).toFixed(2)},...(me.permissions.includes('costs.view')||!p.id?[{name:'cost',label:'Costo',value:((p.cost_cents||0)/100).toFixed(2)}]:[]),...(p.id?[{name:'reason',label:'Motivo del cambio de precio o costo (obligatorio si cambian)',optional:true}]:[]),{name:'tax',label:'IVA (%)',value:(p.tax_bps||0)/100},{name:'min_stock',label:'Stock mínimo',type:'number',value:p.min_stock??0},{name:'max_stock',label:'Stock máximo',type:'number',value:p.max_stock??100},{name:'reorder_point',label:'Punto de reorden',type:'number',value:p.reorder_point??5}])+'<label>Departamento<select name="category_id">'+categories.map(c=>`<option value="${c.id}" ${c.id===p.category_id?'selected':''}>${esc(c.name)}</option>`).join('')+'</select></label><label><input type="checkbox" name="requires_prescription" '+(p.requires_prescription?'checked':'')+'>Requiere receta</label>',async d=>{await api('/products/save',{id:p.id,reason:d.reason,barcode:d.barcode,name:d.name,generic_name:d.generic_name,category_id:Number(d.category_id),price_cents:cents(d.price),cost_cents:cents(d.cost||'0'),tax_bps:cents(d.tax),min_stock:Number(d.min_stock),max_stock:Number(d.max_stock),reorder_point:Number(d.reorder_point),requires_prescription:d.requires_prescription?1:0});await searchProducts();if(currentView==='stock')await refreshStockAfterWrite();notify('Producto guardado');});}
$('productCreate').onclick=act(()=>productForm());
$('productEdit').onclick=()=>modal('Buscar producto para editar',fields([{name:'q',label:'Código exacto o nombre'}]),async d=>{const results=await api('/products?q='+encodeURIComponent(d.q));if(!results.length)throw Error('Sin resultados');table(results);setTimeout(()=>{const chosen=results.find(p=>p.barcode===d.q)||(results.length===1?results[0]:null);if(chosen)act(()=>productForm(chosen))();else notify('Usa el código exacto del producto mostrado');},0);});
$('productDelete').onclick=()=>modal('Dar de baja producto',fields([{name:'id',label:'ID de producto',type:'number'}]),async d=>{await api('/products/deactivate',{id:Number(d.id)});await searchProducts();notify('Producto dado de baja');});
$('receive').onclick=()=>{
 let selected=null,version=0,timer;
 modal('Recibir mercancía',`<label>Buscar producto existente<input name="product_query" placeholder="Nombre o código de barras" autocomplete="off"></label><div id="receiveResults" class="customer-results"></div><div id="receiveProduct" class="muted">Selecciona el producto que llegó.</div><label>Unidades que llegaron<input name="quantity" type="number" min="1" max="1000000" step="1" value="1" required disabled></label><p id="receivePreview" role="status"></p><p class="muted">Se conserva la ficha del producto y el último costo de recepción; si no hay recepciones, se usa el costo registrado del producto. No se captura lote ni caducidad.</p>`,async d=>{
  if(!selected)throw Error('Busca y selecciona un producto existente');
  const r=await api('/inventory/restock',{product_id:selected.id,quantity:Number(d.quantity)});
  await searchProducts();notify(`Mercancía recibida: ${r.stock_before} → ${r.stock_after} unidades disponibles`);
 },'Agregar al stock');
 const f=$('dialogForm'),query=f.elements.product_query,qty=f.elements.quantity,submit=$('dialogSubmit');submit.disabled=true;
 const preview=()=>{const n=Number(qty.value),valid=Number.isInteger(n)&&n>0&&n<=1000000;submit.disabled=!selected||!valid;$('receivePreview').textContent=selected&&valid?`Stock disponible: ${selected.stock} · Después de recibir: ${selected.stock+n}`:'';};
 const choose=p=>{selected=p;version++;$('receiveResults').replaceChildren();qty.disabled=false;$('receiveProduct').textContent=`${p.name} · Código: ${p.barcode} · Precio: ${money(p.price_cents)} · Stock disponible: ${p.stock}`;query.value=p.barcode;preview();qty.focus();};
 const search=async()=>{const current=++version,q=query.value.trim();if(!q){$('receiveResults').replaceChildren();return;}try{const rows=await api('/products?q='+encodeURIComponent(q));if(current!==version||!$('dialog').open)return;const exact=rows.find(p=>p.barcode===q);if(exact){choose(exact);return;}$('receiveResults').innerHTML=rows.map((p,i)=>`<button type="button" data-receive-index="${i}">${esc(p.name)} · ${esc(p.barcode)} · ${p.stock} disponibles</button>`).join('')||'<p>No hay coincidencias. Los productos nuevos se registran en Nuevo producto.</p>';$('receiveResults').onclick=e=>{const b=e.target.closest('[data-receive-index]');if(b)choose(rows[Number(b.dataset.receiveIndex)]);};}catch(e){if(current===version)$('dialogError').textContent=e.message;}};
 query.oninput=()=>{selected=null;version++;qty.disabled=true;submit.disabled=true;$('receiveProduct').textContent='Selecciona el producto que llegó.';$('receivePreview').textContent='';clearTimeout(timer);timer=setTimeout(search,180);};
 query.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();clearTimeout(timer);search();}};qty.oninput=preview;
};
$('adjust').onclick=()=>modal('Ajuste por conteo, merma o caducidad',fields([{name:'batch_id',label:'ID lote (consulta lotes primero)',type:'number'},{name:'expected_quantity',label:'Existencia del sistema observada',type:'number'},{name:'counted_quantity',label:'Nueva existencia física',type:'number'},{name:'reason',label:'Justificación obligatoria'}]),async d=>{await api('/inventory/adjust',{batch_id:Number(d.batch_id),expected_quantity:Number(d.expected_quantity),counted_quantity:Number(d.counted_quantity),reason:d.reason});await searchProducts();notify('Ajuste registrado');});
$('supplier').onclick=act(async()=>{table(await api('/suppliers'));modal('Guardar proveedor',fields([{name:'id',label:'ID (vacío para crear)',type:'number',optional:true},{name:'business_name',label:'Razón social'},{name:'contact',label:'Contacto',optional:true},{name:'phone',label:'Teléfono',optional:true},{name:'credit_days',label:'Días de crédito',type:'number',value:0}]),async d=>{const r=await api('/suppliers/save',{...d,id:d.id?Number(d.id):null,credit_days:Number(d.credit_days)});notify('Proveedor #'+r.id+' guardado');table(await api('/suppliers'));});});
function customerForm(existing=null){modal(existing?'Editar cliente':'Registrar cliente',fields([{name:'name',label:'Nombre',value:existing?.name||''},{name:'phone',label:'Teléfono',value:existing?.phone||'',optional:true},{name:'discount',label:'Descuento (%)',value:(existing?.discount_bps||0)/100}]),async d=>{const result=await api('/customers/save',{id:existing?.id||null,name:d.name,phone:d.phone,discount_bps:cents(d.discount)});await loadCustomers();if(currentView==='credit')await loadCredit();notify('Cliente #'+result.id+' guardado');},existing?'Guardar cambios':'Registrar cliente');}
$('customerCreate').onclick=()=>customerForm();
const userPermissionTemplates={
 seller:['sell','customers.manage'],
 supervisor:['sell','customers.manage','products.create','products.edit','inventory.receive','cash.in','cash.out','sales.return','sales.void','reports.view','suppliers.manage'],
 administrator:null
};
function userTemplatePermissions(role){return role==='administrator'?Object.keys(me.permission_labels):(userPermissionTemplates[role]||[]);}
$('users').onclick=act(async()=>{
 const users=await api('/users');
 const editable=users.filter(u=>u.id!==me.user.id);
 const html='<label>Crear / editar usuario<select id="userAction"><option value="create">Crear un nuevo usuario</option><option value="edit">Editar usuario existente</option></select></label>'+
 '<label id="existingUserLabel" hidden>Usuario existente<select id="editUser"><option value="">Selecciona un usuario</option>'+editable.map(u=>`<option value="${u.id}">${esc(u.display_name)} (${esc(u.username)})${u.active?'':' · Inactivo'}</option>`).join('')+'</select></label>'+
 '<p id="userEditNote" class="muted" hidden>Para modificar tu propia cuenta, entra con otro administrador. Al guardar los cambios, el usuario editado deberá iniciar sesión nuevamente.</p>'+
 fields([{name:'username',label:'Nombre de acceso'},{name:'display_name',label:'Nombre visible'},{name:'secret',label:'PIN de al menos 6 dígitos o contraseña de 8 caracteres',type:'password',optional:true}])+
 '<p id="userPasswordNote" class="muted">La contraseña es obligatoria para crear la cuenta.</p><label><input type="checkbox" name="active" checked>Activo</label>'+
 '<label>Plantilla de permisos<select id="userRole"><option value="seller">Vendedor</option><option value="supervisor">Encargado / supervisor</option><option value="administrator">Administrador</option><option value="custom" hidden>Permisos personalizados</option></select></label>'+
 '<p class="muted">Elegir una plantilla marca sus permisos. Después puedes activar o desactivar cada permiso de forma independiente.</p><h2>Permisos</h2>'+
 Object.entries(me.permission_labels).map(([p,label])=>`<label class="permission"><input type="checkbox" name="perm:${esc(p)}">${esc(label)}</label>`).join('');
 modal('Usuarios y permisos',html,async d=>{
  const editing=$('userAction').value==='edit';const id=editing?Number($('editUser').value):undefined;
  if(editing&&!id)throw Error('Selecciona el usuario que deseas editar');
  await api('/users/save',{id,username:d.username,display_name:d.display_name,secret:d.secret,active:d.active?1:0,permissions:Object.keys(d).filter(k=>k.startsWith('perm:')).map(k=>k.slice(5))});
  table(await api('/users'));notify(editing?'Usuario y permisos actualizados':'Usuario creado');
 });
 const form=$('dialogForm');
 function markPermissions(permissions){Object.keys(me.permission_labels).forEach(p=>form.elements['perm:'+p].checked=permissions.includes(p));}
 function syncUser(){
  const editing=$('userAction').value==='edit';const user=editing?users.find(u=>u.id===Number($('editUser').value)):null;
  $('existingUserLabel').hidden=!editing;$('userEditNote').hidden=!editing;
  $('editUser').required=editing;$('editUser').disabled=!editing;
  form.elements.username.value=user?.username||'';form.elements.username.readOnly=editing;
  form.elements.display_name.value=user?.display_name||'';form.elements.secret.value='';form.elements.secret.required=!editing;
  form.elements.active.checked=user?!!user.active:true;
  $('userPasswordNote').textContent=editing?'Deja la contraseña vacía para conservar la actual.':'La contraseña es obligatoria para crear la cuenta.';
  $('userRole').value=editing?'custom':'seller';markPermissions(user?.permissions||(!editing?userTemplatePermissions('seller'):[]));
  $('dialogSubmit').disabled=editing&&!user;$('dialogSubmit').textContent=editing?'Guardar cambios':'Crear usuario';
  $('dialogError').textContent=editing&&!editable.length?'No hay otras cuentas para editar. Crea una cuenta primero.':'';
 }
 $('userAction').onchange=()=>{$('editUser').value='';syncUser();};$('editUser').onchange=syncUser;
 $('userRole').onchange=()=>{if($('userRole').value!=='custom')markPermissions(userTemplatePermissions($('userRole').value));};
 Object.keys(me.permission_labels).forEach(p=>form.elements['perm:'+p].onchange=()=>{$('userRole').value='custom';});
 syncUser();
});
function returnForm(kind){let requestKey=crypto.randomUUID(),lastSignature=null;modal(kind==='void'?'Anular ticket completo':'Devolver producto de un ticket',fields([{name:'sale_id',label:'Número de ticket',type:'number'},...(kind==='return'?[{name:'sale_item_id',label:'ID partida (consulta el ticket primero)',type:'number'},{name:'quantity',label:'Cantidad',type:'number',value:1}]:[]),{name:'reason',label:'Motivo'}])+(kind==='return'?'<label>Destino<select name="disposition"><option value="restock">Reingresar al lote original</option><option value="quarantine">Cuarentena (no vendible)</option></select></label>':'')+'<p>Los reembolsos se registran en los medios originales, primero efectivo. Ejecuta la devolución de tarjeta o transferencia en su terminal o banco.</p>',async d=>{const payload={sale_id:Number(d.sale_id),kind,reason:d.reason,...(kind==='return'?{items:[{sale_item_id:Number(d.sale_item_id),quantity:Number(d.quantity),disposition:d.disposition}]}:{})};const sig=JSON.stringify(payload);if(lastSignature&&lastSignature!==sig)requestKey=crypto.randomUUID();lastSignature=sig;const r=await api('/returns',{...payload,request_key:requestKey});await searchProducts();notify('Devolución registrada: '+money(r.total_cents));});}
$('returnSale').onclick=()=>returnForm('return');$('voidSale').onclick=()=>returnForm('void');
$('reprint').onclick=()=>modal('Consultar ticket',fields([{name:'id',label:'Número de ticket',type:'number'}]),async d=>{const t=await api('/ticket?id='+Number(d.id));table(t.items);renderReceipt(t);notify('Ticket listo para imprimir');});
$('history').onclick=()=>modal('Historial de compras',fields([{name:'id',label:'ID cliente',type:'number'}]),async d=>table(await api('/customers/history?id='+Number(d.id))));
$('generalReport').onclick=()=>modal('Corte general por turnos',fields([{name:'from_id',label:'Turno inicial',type:'number',value:1},{name:'to_id',label:'Turno final (máximo 366 turnos)',type:'number',value:100}]),async d=>{const r=await api('/reports/general?from_id='+Number(d.from_id)+'&to_id='+Number(d.to_id));table(r.shifts);const p=document.createElement('p');p.textContent='Ventas netas consolidadas: '+money(r.net_sales_cents)+'. Importes en pesos mexicanos (MXN). No se suman fondos de turnos sucesivos.';$('adminResult').prepend(p);});
$('kardex').onclick=()=>modal('Lotes y kardex',fields([{name:'product_id',label:'ID de producto',type:'number'}]),async d=>{const [b,m]=await Promise.all([api('/inventory/batches?product_id='+Number(d.product_id)),api('/inventory/kardex?product_id='+Number(d.product_id))]);table(b);const section=document.createElement('pre');section.textContent='KARDEX\n'+JSON.stringify(m,null,2);$('adminResult').append(section);});
$('alerts').onclick=act(async()=>table(await api('/inventory/alerts')));
document.addEventListener('keydown',e=>{if(!me||document.querySelector('dialog[open]'))return;if(e.key==='F1'){e.preventDefault();if(!$('dialog').open){document.querySelector('[data-view="checkout"]').click();$('search').focus();}}if(e.key==='F5'){e.preventDefault();if(!$('dialog').open)$('pay').click();}if(e.key==='Escape'&&!$('dialog').open&&currentView==='checkout')$('clearCart').click();});
api('/me').then(()=>refresh(true)).catch(()=>{});


function showShiftGate(){
 if(!me?.permissions.includes('sell')){notify('Tu cuenta no tiene permiso para abrir turnos.');return;}
 $('workspace').hidden=true;$('shiftGate').hidden=false;$('gateError').textContent='';
}
$('gateForm').onsubmit=act(async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;try{const d=Object.fromEntries(new FormData(e.target));await api('/shifts/open',{shift_number:Number(d.shift_number),opening_cents:cents(d.opening)});$('shiftGate').hidden=true;await refresh();document.querySelector('[data-view="checkout"]').click();}catch(error){$('gateError').textContent=error.message;}finally{button.disabled=false;}});
$('gateAdmin').onclick=act(async()=>{await refresh();$('shiftGate').hidden=true;document.querySelector('[data-view="manage"]').click();notify('Administración abierta. Abre un turno en Caja y corte para vender.');});
$('gateLogout').onclick=()=> $('logout').click();
window.addEventListener('beforeunload',e=>{if(me?.shift){e.preventDefault();e.returnValue='';}});

let stockSyncBusy=false;
async function syncVisibleStock(){
 if(!me||currentView!=='checkout'||document.hidden||$('dialog').open||stockSyncBusy)return;
 const ids=[...new Set([...cart.map(l=>l.product.id),...products.map(p=>p.id)])].slice(0,500);if(!ids.length)return;
 stockSyncBusy=true;
 try{const fresh=await api('/inventory/availability?ids='+ids.join(','));if(!me)return;for(const p of [...products,...cart.map(l=>l.product)]){if(ids.includes(p.id))p.stock=fresh.find(r=>r.id===p.id)?.stock||0;}renderProducts();$('cart').querySelectorAll('[data-qty]').forEach(input=>input.max=cart[Number(input.dataset.qty)].product.stock);}catch(error){notify('No se pudo actualizar la existencia. Revisa la conexión.');}finally{stockSyncBusy=false;}
}
setInterval(syncVisibleStock,5000);document.addEventListener('visibilitychange',syncVisibleStock);


const creditView=document.createElement('section');creditView.id='credit';creditView.className='view panel';creditView.hidden=true;creditView.innerHTML='<h2>Clientes - Créditos</h2><div class="actions"><button id="creditCreate">Registrar cliente</button><button id="creditRefresh">Actualizar</button></div><label>Buscar cliente<input id="creditSearch" placeholder="Nombre o teléfono"></label><div id="creditRows"></div><div id="creditAccount"></div>';document.querySelector('#manage').before(creditView);
const creditButton=document.createElement('button');creditButton.textContent='Clientes - Créditos';creditButton.dataset.permission='customers.manage';creditButton.dataset.view='credit';document.querySelector('header nav').append(creditButton);
let creditGeneration=0,expandedCreditId=null,accountGeneration=0;
async function loadCredit(){const generation=++creditGeneration;const rows=await api('/credit?q='+encodeURIComponent($('creditSearch').value));if(generation!==creditGeneration)return;const account=$('creditAccount');creditView.append(account);account.replaceChildren();account.hidden=true;expandedCreditId=null;accountGeneration++;$('creditRows').innerHTML=rows.map(c=>`<article class="credit-customer" data-customer-row="${c.id}"><div class="credit-customer-heading"><strong>${esc(c.name)}</strong><div class="actions"><button data-edit-customer="${c.id}">Editar cliente</button><button data-account="${c.id}" data-name="${esc(c.name)}" aria-expanded="false">Ver cuenta / abonar</button></div></div></article>`).join('')||'<p>No hay clientes registrados.</p>';}
creditButton.onclick=act(async()=>{currentView='credit';document.querySelectorAll('[data-view]').forEach(button=>button.classList.toggle('selected',button===creditButton));document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!=='credit');$('workspace').classList.remove('checkout-mode');$('pageTitle').textContent='Clientes - Créditos';await loadCredit();});$('creditRefresh').onclick=act(loadCredit);$('creditSearch').oninput=act(loadCredit);$('creditCreate').onclick=()=>$('customerCreate').click();
async function openCreditAccount(cid,name){
 const generation=++accountGeneration;const data=await api('/credit?id='+cid);if(generation!==accountGeneration)return;
 expandedCreditId=cid;$('creditRows').querySelectorAll('[data-account]').forEach(b=>{const active=Number(b.dataset.account)===cid;b.setAttribute('aria-expanded',String(active));b.textContent=active?'Ocultar cuenta':'Ver cuenta / abonar';});
 const account=$('creditAccount');$('creditRows').querySelector(`[data-customer-row="${cid}"]`).append(account);account.hidden=false;
 account.innerHTML=`<h3>${esc(name)} · Debe ${money(data.balance_cents)}</h3><button id="creditPay" ${data.balance_cents<=0?'disabled':''}>Registrar abono</button>`+data.movements.map(m=>`<article class="inventory-card"><div><strong>${m.amount_cents>0?'Crédito · Ticket #'+m.sale_id:'Abono · '+({cash:'Efectivo',debit:'Tarjeta',transfer:'Transferencia'}[m.method]||'')}</strong><small>${esc(m.created_at)}</small>${m.items.map(i=>`<small>${i.quantity} × ${esc(i.product_name)} · ${money(i.total_cents)}</small>`).join('')}</div><strong>${money(Math.abs(m.amount_cents))}</strong></article>`).join('');
 $('creditPay').onclick=()=>{let key=crypto.randomUUID(),signature;modal('Abonar a '+name,`<p>Deuda actual: ${money(data.balance_cents)}.</p><label>Dinero recibido / importe del abono<input name="amount" value="0.00" inputmode="decimal"></label><label>Forma de pago<select name="method"><option value="cash">Efectivo</option><option value="debit">Tarjeta</option><option value="transfer">Transferencia</option></select></label><div id="cardFeePreview" class="abono-summary" hidden></div><div class="abono-summary"><p>Abono aplicado: <strong id="abonoApplied">$0.00</strong></p><p>Cambio a entregar: <strong id="abonoChange">$0.00</strong></p><p>Saldo pendiente: <strong id="abonoRemaining">${money(data.balance_cents)}</strong></p></div>`,async d=>{
  const received=cents(d.amount);const fresh=await api('/credit?id='+cid);
  if(fresh.balance_cents<=0)throw Error('El cliente ya no tiene deuda pendiente. Actualiza su cuenta.');
  const applied=d.method==='cash'?Math.min(received,fresh.balance_cents):received;
  const body={customer_id:cid,amount_cents:applied,received_cents:received,method:d.method};const sig=JSON.stringify(body);if(signature&&sig!==signature)key=crypto.randomUUID();signature=sig;
  const result=await api('/credit/payment',{...body,request_key:key});await loadCredit();if($('creditRows').querySelector(`[data-customer-row="${cid}"]`))await openCreditAccount(cid,name);notify(`Abono registrado: ${money(result.applied_cents??applied)} · Cambio a entregar: ${money(result.change_cents??(d.method==='cash'?received-applied:0))}`);
 });
 const preview=()=>{try{const f=$('dialogForm'),received=cents(f.elements.amount.value),cash=f.elements.method.value==='cash';const applied=Math.min(received,data.balance_cents);window.showCardFeePreview?.(f.elements.method.value,applied);$('abonoApplied').textContent=money(applied);$('abonoChange').textContent=money(cash?Math.max(0,received-applied):0);$('abonoRemaining').textContent=money(data.balance_cents-applied);$('dialogError').textContent=!cash&&received>data.balance_cents?'Tarjeta y transferencia no permiten cambio. Ajusta el importe al saldo pendiente.':'';}catch(e){$('dialogError').textContent=e.message;}};
 $('dialogBody').oninput=preview;$('dialogBody').querySelector('[name="method"]').onchange=preview;preview();
 };
}
$('creditRows').onclick=act(async e=>{const edit=e.target.closest('[data-edit-customer]');if(edit){const rows=await api('/credit');const existing=rows.find(c=>c.id===Number(edit.dataset.editCustomer));if(!existing)throw Error('El cliente ya no está disponible. Actualiza la lista.');customerForm(existing);return;}const b=e.target.closest('[data-account]');if(!b)return;const cid=Number(b.dataset.account);if(expandedCreditId===cid){accountGeneration++;expandedCreditId=null;$('creditAccount').hidden=true;b.setAttribute('aria-expanded','false');b.textContent='Ver cuenta / abonar';return;}await openCreditAccount(cid,b.dataset.name);});

$('logout').addEventListener('click',()=>{if(me?.shift)return;creditGeneration++;$('creditRows').replaceChildren();$('creditAccount').replaceChildren();$('creditSearch').value='';});

// Normaliza pesos y porcentajes al terminar de escribir, antes de validar el formulario.
const moneyInputNames=new Set(['opening','counted','amount','received','price','cost','tax','discount']);
document.addEventListener('blur',event=>{const input=event.target;if(!(input instanceof HTMLInputElement)||!moneyInputNames.has(input.name))return;try{input.value=(cents(input.value)/100).toFixed(2);}catch{}},true);

function attachOutsideClose(dialog,canClose){let startedOutside=false;const outside=e=>{const r=dialog.getBoundingClientRect();return e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom;};dialog.addEventListener('pointerdown',e=>{startedOutside=e.target===dialog&&outside(e);});dialog.addEventListener('click',e=>{if(startedOutside&&e.target===dialog&&outside(e)&&canClose())dialog.close();startedOutside=false;});}
attachOutsideClose($('dialog'),()=>!busy);attachOutsideClose($('inventoryDialog'),()=>!transferBusy);
