/* La base local guarda el cuerpo exacto antes del primer envío. */
(()=>{
 const paths=['/sales','/returns','/cash','/inventory/receive','/inventory/restock','/credit/payment'];
 const names={'/sales':'Cobro','/returns':'Devolución','/cash':'Movimiento de efectivo','/inventory/receive':'Recepción','/inventory/restock':'Recepción','/credit/payment':'Abono'};
 let request,refreshing=false,root;
 function panel(){if(!root){root=document.createElement('section');root.className='panel';root.hidden=true;root.setAttribute('aria-live','polite');document.getElementById('workspace').prepend(root);}return root;}
 async function refresh(){
  if(!request||refreshing)return;refreshing=true;
  try{
   const data=await request('/operations/pending');const node=panel();node.replaceChildren();node.hidden=!data.items.length;
   for(const item of data.items){
    const title=document.createElement('h2');title.textContent=names[item.path]+' pendiente de verificar';
    const note=document.createElement('p');note.textContent='Comprueba el resultado anterior antes de registrar otro movimiento. Recuperar utiliza la misma solicitud y evita duplicados.';
    const recover=document.createElement('button');recover.textContent='Recuperar resultado';
    const cancel=document.createElement('button');cancel.textContent='Descartar si no se confirmó';
    const status=document.createElement('p');status.setAttribute('role','status');
    recover.onclick=async()=>{recover.disabled=cancel.disabled=true;try{
     const result=await request('/operations/recover',{request_key:item.request_key});
     await request('/operations/ack',{request_key:item.request_key});
     if(item.path==='/sales'){if(typeof cart!=='undefined'){cart=[];pendingSale=null;resetCheckoutCustomer();renderCart();}renderReceipt(result);}
     notify('Resultado recuperado. Comprobante #'+result.id);await refreshAfter();
    }catch(e){status.textContent=e.message;}finally{recover.disabled=cancel.disabled=false;}};
    cancel.onclick=async()=>{recover.disabled=cancel.disabled=true;try{await request('/operations/cancel',{request_key:item.request_key});await refreshAfter();}catch(e){status.textContent=e.message;}finally{recover.disabled=cancel.disabled=false;}};
    node.append(title,note,recover,cancel,status);
   }
  }finally{refreshing=false;}
 }
 async function refreshAfter(){refreshing=false;await refresh();}
 window.safeOperations={paths,refresh,async submit(path,payload,transport){
  request=transport;
  payload={...payload,request_key:payload.request_key||crypto.randomUUID()};
  await transport('/operations/prepare',{path,payload});
  try{
   const result=await transport('/operations/recover',{request_key:payload.request_key});
   await transport('/operations/ack',{request_key:payload.request_key});
   await refresh();return result;
  }catch(error){await refresh().catch(()=>{});throw error;}
 },start(transport){request=transport;return refresh();}};
})();
