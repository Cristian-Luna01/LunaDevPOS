const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/static/direction.js','utf8');
const api=source.slice(source.indexOf('async function api('),source.indexOf('function clearPanel('));
let response;const context={fetch:async()=>response};vm.createContext(context);vm.runInContext(api,context);
(async()=>{
 response={ok:false,status:401,redirected:false,text:async()=>'Unauthorized'};
 await assert.rejects(context.api('login',{username:'admin',secret:'wrong'}),e=>e.remoteAccess&&e.status===401&&e.message.includes('verificación')&&!e.message.includes('Unexpected token'));
 response={ok:false,status:401,text:async()=>JSON.stringify({error:'Credenciales inválidas'})};
 await assert.rejects(context.api('login',{}),e=>e.message==='Credenciales inválidas'&&!e.remoteAccess);
 response={ok:true,status:200,redirected:true,text:async()=>'<html>Cloudflare login</html>'};
 await assert.rejects(context.api('summary'),e=>e.remoteAccess);
 response={ok:true,status:200,text:async()=>'{"ok":true}'};assert.equal((await context.api('summary')).ok,true);
 console.log('OK: rechazo externo, credenciales incorrectas, redirección y respuesta válida');
})().catch(e=>{console.error(e);process.exitCode=1;});
