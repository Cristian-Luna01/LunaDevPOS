/* Gestión por nombre: los identificadores internos nunca se teclean. */
(()=>{
 const management=(kind,title)=>act(async()=>{
  const supplier=kind==='suppliers',rows=await api('/entities/'+kind),name=r=>supplier?r.business_name:r.name;
  modal(title,`<label>Qué deseas hacer<select name="action"><option value="create">Crear ${supplier?'proveedor':'cliente'}</option><option value="edit">Editar existente</option><option value="delete">Eliminar / dar de baja</option><option value="restore">Reactivar una baja</option></select></label><div id="entityPicker" hidden><label>Buscar por nombre o teléfono<input name="search" autocomplete="off"></label><label>Seleccionar ${supplier?'proveedor':'cliente'}<select name="existing"></select></label></div><div id="entityFields"></div><p id="entityNotice" class="muted"></p>`,async d=>{
   const id=Number(d.existing),action=d.action;
   if(action!=='create'&&!id)throw Error('Selecciona un registro por su nombre');
   if(action==='delete'||action==='restore'){await api('/entities/'+kind+'/status',{id,active:action==='restore'?1:0,reason:action==='restore'?'Reactivación desde administración':'Baja solicitada desde administración'});}
   else if(supplier)await api('/suppliers/save',{id:action==='create'?undefined:id,business_name:d.business_name,contact:d.contact||'',phone:d.phone||'',credit_days:Number(d.credit_days||0)});
   else await api('/customers/save',{id:action==='create'?undefined:id,name:d.name,phone:d.phone||'',discount_bps:cents(d.discount||'0')});
   if(!supplier){await loadCustomers();if(currentView==='credit')await loadCredit();}
   notify(action==='delete'?'Registro dado de baja; su historial se conserva.':action==='restore'?'Registro reactivado.':'Datos guardados.');
  });
  const f=$('dialogForm'),picker=$('entityPicker'),target=$('entityFields');
  function options(){const q=f.elements.search.value.toLocaleLowerCase('es'),action=f.elements.action.value,old=f.elements.existing.value;const matches=rows.filter(r=>(name(r)+' '+r.phone).toLocaleLowerCase('es').includes(q)&&(action==='restore'?!r.active:action==='delete'?r.active:true));f.elements.existing.innerHTML='<option value="">Selecciona por nombre</option>'+matches.map(r=>`<option value="${r.id}">${esc(name(r))}${r.phone?' · '+esc(r.phone):''}${r.active?'':' · Baja'}</option>`).join('');if(matches.some(r=>String(r.id)===old))f.elements.existing.value=old;render();}
  function render(){const action=f.elements.action.value,creating=action==='create',record=rows.find(r=>r.id===Number(f.elements.existing.value)),editing=action==='edit',remove=action==='delete';picker.hidden=creating;f.elements.existing.disabled=creating;f.elements.existing.required=!creating;
   target.innerHTML=creating||editing?fields(supplier?[{name:'business_name',label:'Nombre del proveedor o empresa',value:record?.business_name||''},{name:'contact',label:'Persona de contacto (opcional)',value:record?.contact||'',optional:true},{name:'phone',label:'Teléfono (opcional)',value:record?.phone||'',optional:true}]:[{name:'name',label:'Nombre del cliente',value:record?.name||''},{name:'phone',label:'Teléfono (opcional)',value:record?.phone||'',optional:true}])+`<details ${supplier?(record?.credit_days?'open':''):(record?.discount_bps?'open':'')}><summary>${supplier?'Plazo de crédito opcional':'Descuento opcional'}</summary>${supplier?fields([{name:'credit_days',label:'Días de crédito',type:'number',value:record?.credit_days||0}]):fields([{name:'discount',label:'Descuento (%)',value:(record?.discount_bps||0)/100}])}</details>`:'';
   $('entityNotice').textContent=remove?'La baja conserva ventas, compras y movimientos anteriores. Un cliente con deuda pendiente no puede darse de baja.':action==='restore'?'El registro volverá a estar disponible para operaciones nuevas.':record&&!record.active?'Este registro está de baja. Editar su ficha no lo reactiva; usa Reactivar una baja.':supplier?'Escribe el nombre con el que ubicas al proveedor. El número interno lo genera el programa.':'El descuento es opcional; usa cero si no corresponde.';
   $('dialogSubmit').textContent=remove?'Dar de baja':action==='restore'?'Reactivar':creating?'Crear':'Guardar cambios';$('dialogSubmit').disabled=!creating&&!record;
  }
  f.elements.action.onchange=()=>{f.elements.existing.value='';options();};f.elements.search.oninput=options;f.elements.existing.onchange=render;options();
 });
 $('supplier').textContent='Proveedores';$('supplier').onclick=management('suppliers','Crear, editar o dar de baja proveedor');
 $('customerCreate').textContent='Clientes';$('customerCreate').onclick=management('customers','Crear, editar o dar de baja cliente');
 // La edición reutiliza el formulario completo de permisos ya existente.
 const editUsers=$('users').onclick;
 $('users').onclick=act(async()=>{
  modal('Usuarios y permisos','<p>Crear o editar conserva las plantillas de vendedor, supervisor y administrador.</p><div class="actions"><button type="button" id="manageUserEdit">Crear / editar usuario y permisos</button><button type="button" id="manageUserDelete">Eliminar / dar de baja usuario</button></div>',null);
  $('manageUserEdit').onclick=()=>{$('dialog').close();editUsers();};
  $('manageUserDelete').onclick=act(async()=>{const users=(await api('/users')).filter(u=>u.id!==me.user.id&&u.active);modal('Dar de baja usuario','<label>Usuario<select name="id" required><option value="">Selecciona un usuario</option>'+users.map(u=>`<option value="${u.id}">${esc(u.display_name)} · ${esc(u.username)}</option>`).join('')+'</select></label><label>Motivo<input name="reason" required maxlength="500"></label><p>Se conserva su historial. El usuario no podrá iniciar sesión. Primero debe cerrar su turno. Para reactivarlo, usa Editar usuario y marca Activo.</p>',async d=>{await api('/entities/users/status',{id:Number(d.id),active:0,reason:d.reason});notify('Usuario dado de baja. Su historial se conserva.');},'Dar de baja');});
 });
 $('productEdit').onclick=act(async()=>{
  let generation=0,timer;modal('Seleccionar producto para editar','<label>Buscar por nombre o código<input name="product_search" autocomplete="off" placeholder="Escribe para buscar"></label><div id="editProductResults" class="customer-results"></div><p>Selecciona el producto que deseas editar; no es necesario escribir su código exacto.</p>',null);
  const query=$('dialogForm').elements.product_search;
  const search=async()=>{const version=++generation,q=query.value.trim();if(!q){$('editProductResults').replaceChildren();return;}try{const rows=await api('/products?q='+encodeURIComponent(q));if(version!==generation||!$('dialog').open||!$('editProductResults'))return;$('editProductResults').innerHTML=rows.map((p,i)=>`<button type="button" data-edit-product="${i}">${esc(p.name)} · ${esc(p.barcode)} · ${money(p.price_cents)}</button>`).join('')||'<p>No hay coincidencias.</p>';$('editProductResults').onclick=act(async e=>{const b=e.target.closest('[data-edit-product]');if(!b)return;generation++;$('dialog').close();await productForm(rows[Number(b.dataset.editProduct)]);});}catch(error){if(version===generation)$('dialogError').textContent=error.message;}};
  query.oninput=()=>{clearTimeout(timer);timer=setTimeout(search,180);};query.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();clearTimeout(timer);search();}};
 });
})();
