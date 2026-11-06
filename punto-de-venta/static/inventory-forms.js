/* Selección por nombre y código; los identificadores se mantienen internos. */
(()=>{
 function choose(title,callback){
  let timer,version=0;
  modal(title,'<label>Nombre o código de barras<input id="chooseProductQuery" autocomplete="off" autofocus></label><div id="chooseProductRows" class="customer-results"></div>',null);
  const input=$('chooseProductQuery'),rows=$('chooseProductRows');input.focus();
  input.oninput=()=>{const current=++version;clearTimeout(timer);timer=setTimeout(async()=>{
   try{const found=await api('/products?q='+encodeURIComponent(input.value.trim()));if(current!==version||!$('dialog').open)return;
    rows.replaceChildren();for(const product of found){const b=document.createElement('button');b.type='button';b.textContent=product.name+' · '+product.barcode+' · '+product.stock+' disponibles';b.onclick=()=>{$('dialog').close();act(()=>callback(product))();};rows.append(b);}
    if(!found.length)rows.textContent='Sin coincidencias.';
   }catch(e){$('dialogError').textContent=e.message;}
  },160);};
 }
 $('productEdit').onclick=()=>choose('Editar un producto',productForm);
 $('productDelete').onclick=()=>choose('Dar de baja un producto',p=>{
  modal('Dar de baja · '+p.name,`<p>Código ${esc(p.barcode)}. Las ventas y el historial se conservan.</p><label><input name="confirmation" type="checkbox" required>Confirmo la baja del producto seleccionado</label>`,async()=>{await api('/products/deactivate',{id:p.id});notify('Producto dado de baja');});
 });
 $('adjust').onclick=()=>choose('Seleccionar producto para ajustar',async p=>{
  const batches=await api('/inventory/batches?product_id='+p.id);if(!batches.length)throw Error('Este producto no tiene lotes. Usa Ajustar existencia desde Inventario.');
  modal('Ajustar lote · '+p.name,`<label>Lote<select name="batch">${batches.map((b,i)=>`<option value="${i}">${esc(b.lot_number)} · ${esc(b.expires_on||'Sin caducidad')} · ${b.quantity} unidades</option>`).join('')}</select></label><label>Unidades contadas<input name="counted" type="number" min="0" step="1" value="${batches[0].quantity}" required></label><label>Motivo<input name="reason" required maxlength="500"></label>`,async d=>{const b=batches[Number(d.batch)];await api('/inventory/adjust',{batch_id:b.id,expected_quantity:b.quantity,counted_quantity:Number(d.counted),reason:d.reason});notify('Ajuste registrado');});
  $('dialogForm').elements.batch.onchange=e=>{$('dialogForm').elements.counted.value=batches[Number(e.target.value)].quantity;};
 });
 $('editBatch').onclick=()=>choose('Completar lote o caducidad',async p=>{
  const batches=await api('/inventory/batches?product_id='+p.id);if(!batches.length)throw Error('No hay lotes registrados');
  modal('Editar lote · '+p.name,`<label>Lote<select name="batch">${batches.map((b,i)=>`<option value="${i}">${esc(b.lot_number)} · ${b.quantity} unidades</option>`).join('')}</select></label>`+fields([{name:'lot_number',label:'Número de lote',value:batches[0].lot_number},{name:'expires_on',label:'Caducidad',type:'date',optional:true,value:batches[0].expires_on||''},{name:'reason',label:'Motivo'}]),async d=>{await api('/inventory/batch/edit',{batch_id:batches[Number(d.batch)].id,lot_number:d.lot_number,expires_on:d.expires_on,reason:d.reason});notify('Lote actualizado');});
  $('dialogForm').elements.batch.onchange=e=>{const b=batches[Number(e.target.value)],f=$('dialogForm');f.elements.lot_number.value=b.lot_number;f.elements.expires_on.value=b.expires_on||'';};
 });
 $('kardex').onclick=()=>choose('Consultar movimientos del producto',async p=>{
  const [batches,moves]=await Promise.all([api('/inventory/batches?product_id='+p.id),api('/inventory/kardex?product_id='+p.id)]);
  table(batches);const title=document.createElement('h3');title.textContent='Movimientos de '+p.name;$('adminResult').prepend(title);
  const list=document.createElement('div');for(const m of moves){const row=document.createElement('p');row.textContent=`${m.created_at} · ${m.kind} · ${m.quantity_delta>0?'+':''}${m.quantity_delta} unidades · ${m.reason}`;list.append(row);}$('adminResult').append(list);
 });
 const detailed=document.createElement('button');detailed.textContent='Recibir con lote, caducidad y costo';detailed.dataset.permission='inventory.receive';$('receive').after(detailed);
 detailed.onclick=()=>choose('Seleccionar mercancía recibida',async p=>{
  const suppliers=await api('/suppliers');
  modal('Recibir · '+p.name,fields([{name:'quantity',label:'Unidades recibidas',type:'number',value:1},{name:'cost',label:'Costo de compra por unidad',value:((p.cost_cents||0)/100).toFixed(2)},{name:'lot_number',label:'Lote',optional:true},{name:'expires_on',label:'Caducidad',type:'date',optional:true},{name:'reason',label:'Factura o motivo de recepción'}])+`<label>Proveedor<select name="supplier_id"><option value="">Sin proveedor</option>${suppliers.map(s=>`<option value="${s.id}">${esc(s.business_name)}</option>`).join('')}</select></label>`,async d=>{await api('/inventory/receive',{product_id:p.id,quantity:Number(d.quantity),unit_cost_cents:cents(d.cost),lot_number:d.lot_number,expires_on:d.expires_on,supplier_id:Number(d.supplier_id)||null,reason:d.reason});notify('Recepción registrada');});
 });
 window.chooseInventoryProduct=choose;
})();
