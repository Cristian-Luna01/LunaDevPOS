/* Recuperación durable en SQLite: una respuesta perdida no genera otra operación. */
(()=>{
 const paths={'/sales':'sale','/cash':'cash','/inventory/restock':'restock','/inventory/receive':'receive'};
 let active=null,busy=false;
 async function raw(path,data){try{const r=await fetch('/api'+path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json','X-POS-Request':'1'}:{},body:data?JSON.stringify(data):undefined});const v=await r.json();if(!r.ok)throw Error(v.error||'No se pudo comprobar la operación');return v;}catch(e){if(e instanceof TypeError||e instanceof SyntaxError)throw Error('No se pudo confirmar la respuesta del programa. Pulsa Comprobar antes de repetir el cobro o movimiento.');throw e;}}
 const banner=document.createElement('section');banner.className='panel';banner.hidden=true;banner.setAttribute('role','alert');
 banner.innerHTML='<strong>Operación pendiente de comprobar</strong><p>No vuelvas a cobrar ni repetir este movimiento hasta comprobar el resultado.</p><div class="actions"><button type="button" data-check>Comprobar</button><button type="button" data-retry>Reintentar la misma operación</button><button type="button" data-cancel>Cancelar si no se registró</button></div><p data-status></p>';
 document.getElementById('workspace').prepend(banner);
 function show(message=''){banner.hidden=!active;banner.querySelector('[data-status]').textContent=message;banner.querySelectorAll('button').forEach(b=>b.disabled=busy);}
 function confirmed(v){if(active?.kind==='sale'&&v.result?.id){document.dispatchEvent(new CustomEvent('recovered-sale',{detail:v.result}));}active=null;show();}
 async function check(){const v=await raw('/operations/pending');active=v.pending;show(active?'Resultado: '+({confirmed:'registrada; puedes confirmar la consulta',cancelled:'cancelada',not_found:'aún no registrada'})[active.state]:'');if(active&&active.state!=='not_found'){const done=await raw('/operations/ack',{kind:active.kind,key:active.key});confirmed(done);}return active;}
 async function run(path,data){
  if(busy)throw Error('Espera la comprobación anterior');busy=true;
  try{
   const kind=paths[path];if(!kind)return await raw(path,data);
   if(!active){const p=await raw('/operations/pending');active=p.pending;}
   const signature=o=>JSON.stringify({...o,request_key:undefined});
   if(active&&(active.path!==path||signature(active.body)!==signature(data)))throw Error('Hay otra operación pendiente. Compruébala o cancélala antes de continuar.');
   const body=active?active.body:{...data,request_key:data.request_key||crypto.randomUUID()};
   active={kind,path,key:body.request_key,body};show();
   await raw('/operations/prepare',{kind,key:active.key,body});
   const result=await raw(path,body);
   await raw('/operations/ack',{kind,key:active.key});active=null;show();return result;
  }catch(e){show(e.message);throw e;}finally{busy=false;show(banner.querySelector('[data-status]').textContent);}
 }
 async function action(fn){if(busy)return;busy=true;show();try{await fn();}catch(e){show(e.message);}finally{busy=false;show(banner.querySelector('[data-status]').textContent);}}
 banner.querySelector('[data-check]').onclick=()=>action(check);
 banner.querySelector('[data-retry]').onclick=async()=>{if(!active)return;try{const current=active,result=await run(current.path,current.body);if(current.kind==='sale')document.dispatchEvent(new CustomEvent('recovered-sale',{detail:result}));else location.reload();}catch(e){show(e.message);}};
 banner.querySelector('[data-cancel]').onclick=()=>action(async()=>{if(!active||!confirm('Se consultará el registro. Si ya se confirmó, se conservará; si no, se impedirá que se registre después. ¿Continuar?'))return;const done=await raw('/operations/cancel',{kind:active.kind,key:active.key});confirmed(done);});
 window.pendingOperations={run,recover:()=>action(check),handles:path=>!!paths[path]};
})();
