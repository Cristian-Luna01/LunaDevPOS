import {storeDocument,hydrateBranches,receivePart,cleanupDocuments} from './documents.js';
const assembledRequests=new WeakSet();
import {validateSnapshot} from './domain.js';
import {summary,selectBranches,history} from './reporting.js';
import {exportCSV,exportXLSX} from './exports.js';
import {retained,cleanup} from './retention.js';
const enc=new TextEncoder();
const hash=async v=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(v)))).map(v=>v.toString(16).padStart(2,'0')).join('');
const key=()=>Array.from(crypto.getRandomValues(new Uint8Array(32))).map(v=>v.toString(16).padStart(2,'0')).join('');
function json(v,status=200,extra={}){return new Response(JSON.stringify(v),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',...extra}});}
async function body(r){
 const limit=assembledRequests.has(r)?16000000:900000;
 if(Number(r.headers.get('Content-Length')||0)>limit)throw Error('Archivo demasiado grande');
 const reader=r.body?.getReader();if(!reader)throw Error('Solicitud sin contenido');
 let size=0;const parts=[];
 for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit){await reader.cancel();throw Error('Archivo demasiado grande');}parts.push(value);}
 const bytes=new Uint8Array(size);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.length;}
 return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
}
async function owner(r,env){const token=(r.headers.get('Cookie')||'').match(/(?:^|;\s*)central_session=([a-f0-9]{64})(?:;|$)/)?.[1];if(!token)return false;return !!await env.DB.prepare('SELECT 1 FROM sessions WHERE token_hash=? AND expires>?').bind(await hash(token),Date.now()).first();}
async function selectedRows(DB,id){
 const query=DB.prepare(id==='all'?'SELECT id,name,active,revision,received_at,payload FROM branches WHERE active=1 ORDER BY name':'SELECT id,name,active,revision,received_at,payload FROM branches WHERE active=1 AND id=? ORDER BY name');
 const {results}=await (id==='all'?query:query.bind(id)).all();
 return selectBranches(await hydrateBranches(DB,results),id);
}
const worker={async scheduled(event,env,ctx){ctx.waitUntil(Promise.all([cleanup(env.DB),cleanupDocuments(env.DB)]));},async fetch(r,env,ctx){
 const u=new URL(r.url),path=u.pathname.replace(/^\/direccion\/api\//,'/api/').replace(/^\/business-settings$/,'/api/business-settings').replace(/^\/business-logo.png$/,'/api/business-logo.png');
 try{
  if(!path.startsWith('/api/')){const res=await env.ASSETS.fetch(r);const headers=new Headers(res.headers);headers.set('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");headers.set('Referrer-Policy','no-referrer');if(headers.get('Content-Type')?.includes('text/html'))headers.set('Cache-Control','no-store');return new Response(res.body,{status:res.status,headers});}
  if(!env.OWNER_EMAIL||!env.OWNER_PASSWORD_SHA256)return json({error:'La cuenta central todavía no está configurada'},503);
  if(r.method==='POST'&&!['/api/snapshot','/api/history-day','/api/transfer'].includes(path)&&r.headers.get('Origin')!==u.origin)return json({error:'Origen no permitido'},403);
  if(path==='/api/login'&&r.method==='POST'){
   const address=await hash(r.headers.get('CF-Connecting-IP')||'local'),now=Date.now();
   const attempt=await env.DB.prepare('SELECT * FROM attempts WHERE key=?').bind(address).first();
   if(attempt?.until_at>now)return json({error:'Demasiados intentos. Espera 15 minutos.'},429);
   const p=await body(r);
   if(typeof p.secret!=='string'||p.secret.length>200||(p.email||p.username)?.toLowerCase()!==env.OWNER_EMAIL.toLowerCase()||await hash(p.secret)!==env.OWNER_PASSWORD_SHA256){
    // El incremento es atómico: peticiones paralelas no pierden intentos leídos a la vez.
    await env.DB.prepare(`INSERT INTO attempts(key,failures,until_at) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET
     failures=CASE WHEN attempts.until_at>? THEN attempts.failures+1 ELSE 1 END,
     until_at=CASE WHEN attempts.until_at>? THEN attempts.until_at WHEN attempts.until_at>? AND attempts.failures>=4 THEN ? ELSE ? END`).bind(address,now,now-900000,now,now-900000,now+900000,now).run();return json({error:'Correo o clave incorrectos'},401);
   }
   const token=key();await env.DB.batch([env.DB.prepare('DELETE FROM attempts WHERE key=?').bind(address),env.DB.prepare('DELETE FROM sessions WHERE expires<?').bind(now),env.DB.prepare('INSERT INTO sessions VALUES(?,?)').bind(await hash(token),now+43200000)]);
   return json({ok:true},200,{'Set-Cookie':`central_session=${token}; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200`});
  }
  if(path==='/api/transfer'&&r.method==='POST'){
   const token=r.headers.get('Authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];if(!token)return json({error:'Clave requerida'},401);
   const b=await env.DB.prepare('SELECT id FROM branches WHERE token_hash=? AND active=1').bind(await hash(token)).first();if(!b)return json({error:'Sucursal no autorizada'},401);
   const p=await body(r),part=await receivePart(env.DB,b.id,p);
   if(!part.complete)return json({ok:true,part:p.part,complete:false});
   const next=new Request(u.origin+'/api/'+p.kind,{method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:part.text});assembledRequests.add(next);
   const response=await worker.fetch(next,env,ctx);
   if(response.ok){if(ctx?.waitUntil)ctx.waitUntil(cleanupDocuments(env.DB));}
   return response;
  }
  if(path==='/api/history-day'&&r.method==='POST'){
   const token=r.headers.get('Authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];if(!token)return json({error:'Clave de sucursal requerida'},401);
   const tokenHash=await hash(token),b=await env.DB.prepare('SELECT id,device_id FROM branches WHERE token_hash=? AND active=1').bind(tokenHash).first();if(!b)return json({error:'Sucursal no autorizada'},401);
   const p=await body(r);
   if(p.version!==2||p.instance_id!==b.device_id||!Number.isSafeInteger(p.revision)||p.revision<1||!/^\d{4}-\d{2}-\d{2}$/.test(p.day)||!/^[a-f0-9]{64}$/.test(p.fingerprint||'')||p.report?.from!==p.day||p.report?.to!==p.day||!Array.isArray(p.report.events)||!Array.isArray(p.report.products)||!Array.isArray(p.report.cash_movements))return json({error:'Detalle de historial inválido'},400);
   const current=await env.DB.prepare('SELECT revision,fingerprint FROM history_days WHERE branch_id=? AND day=?').bind(b.id,p.day).first();if(current&&(current.revision>p.revision||(current.revision===p.revision&&current.fingerprint!==p.fingerprint)))return json({error:'Revisión antigua o incompatible'},409);
   p.report=retained(p.report,p.day);
   const storedReport=await storeDocument(env.DB,b.id,p.report);
   await env.DB.prepare('INSERT INTO history_days(branch_id,day,revision,fingerprint,payload) SELECT ?,?,?,?,? WHERE EXISTS(SELECT 1 FROM branches WHERE id=? AND token_hash=? AND active=1 AND device_id=?) ON CONFLICT(branch_id,day) DO UPDATE SET revision=excluded.revision,fingerprint=excluded.fingerprint,payload=excluded.payload WHERE history_days.revision<excluded.revision').bind(b.id,p.day,p.revision,p.fingerprint,storedReport,b.id,tokenHash,p.instance_id).run();
   const accepted=await env.DB.prepare('SELECT h.revision,h.fingerprint FROM history_days h JOIN branches b ON b.id=h.branch_id WHERE h.branch_id=? AND h.day=? AND b.token_hash=? AND b.active=1 AND b.device_id=?').bind(b.id,p.day,tokenHash,p.instance_id).first();
   if(!accepted||accepted.revision!==p.revision||accepted.fingerprint!==p.fingerprint)return json({error:'No se confirmó el detalle'},409);
   if(ctx?.waitUntil)ctx.waitUntil(cleanup(env.DB));
   return json({ok:true,revision:p.revision});
  }
  if(path==='/api/snapshot'&&r.method==='POST'){
   const token=r.headers.get('Authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];if(!token)return json({error:'Clave de sucursal requerida'},401);
   const tokenHash=await hash(token);
   const b=await env.DB.prepare('SELECT id,revision,device_id,payload FROM branches WHERE token_hash=? AND active=1').bind(tokenHash).first();if(!b)return json({error:'Sucursal no autorizada'},401);
   const p=validateSnapshot(await body(r));
   if(p.revision<b.revision)return json({error:'Vinculación antigua. Crea una nueva clave para esta computadora.'},409);
   if(b.device_id&&b.device_id!==p.instance_id)return json({error:'Esta clave pertenece a otra computadora. Crea una clave distinta por sucursal.'},409);
   const serialized=await storeDocument(env.DB,b.id,p);
   if(p.revision===b.revision&&b.payload!==serialized)return json({error:'La revisión ya fue registrada con otros datos'},409);
   await env.DB.prepare('UPDATE branches SET revision=?,received_at=?,payload=?,device_id=? WHERE id=? AND revision<? AND active=1 AND token_hash=? AND (device_id IS NULL OR device_id=?)').bind(p.revision,new Date().toISOString(),serialized,p.instance_id,b.id,p.revision,tokenHash,p.instance_id).run();
   const accepted=await env.DB.prepare('SELECT revision,device_id FROM branches WHERE id=? AND token_hash=? AND active=1').bind(b.id,tokenHash).first();
   if(!accepted||accepted.revision!==p.revision||accepted.device_id!==p.instance_id)return json({error:'La vinculación cambió. Vuelve a configurarla.'},409);
   return json({ok:true,revision:p.revision});
  }
  if(!await owner(r,env))return json({error:'Inicia sesión con la cuenta del dueño'},401);
  if(['/api/business-settings','/api/business-logo.png'].includes(path)&&r.method==='GET'){
   const rows=await selectedRows(env.DB,u.searchParams.get('branch')||'all'),settings=rows.find(b=>b.snapshot?.direction)?.snapshot.direction.settings||{name:'Dirección',receipt_footer:'',has_logo:false};
   if(path.endsWith('.png')){if(!settings.logo_base64)return json({error:'Sin logotipo'},404);return new Response(Uint8Array.from(atob(settings.logo_base64),c=>c.charCodeAt(0)),{headers:{'Content-Type':'image/png','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});}
   return json({name:settings.name,receipt_footer:settings.receipt_footer,has_logo:settings.has_logo});
  }
  if(['/api/summary','/api/history','/api/history.csv','/api/history.xlsx','/api/metrics','/api/inventory-adjustments'].includes(path)&&r.method==='GET'){
   const all=u.searchParams.get('branch')||'all',rows=await selectedRows(env.DB,all);
   if(path==='/api/summary')return json(summary(rows,'Administrador',all==='all'));
   let result;try{result=await history(env.DB,rows,u.searchParams.get('from'),u.searchParams.get('to'),all==='all',path==='/api/metrics');}catch(e){return json({error:e.message.startsWith('Sin información posterior')?e.message:'El historial de los locales seleccionados todavía se está sincronizando. Comprueba la conexión de cada punto de venta y actualiza en unos segundos.'},503);}
   if(path==='/api/inventory-adjustments')return json({from:result.from,to:result.to,...result.inventory_adjustments,detail_coverage:result.detail_coverage});
   if(path.endsWith('.csv')||path.endsWith('.xlsx')){const xlsx=path.endsWith('.xlsx');if(!xlsx&&result.detail_coverage?.summary_days.length&&u.searchParams.get('summary')!=='1')return json({error:'Este periodo incluye fechas conservadas como resumen. Descarga el resumen diario o Excel con cobertura; para el detalle completo usa el punto de venta del local.'},409);return new Response(xlsx?exportXLSX(result):exportCSV(result,u.searchParams.get('summary')==='1'),{headers:{'Content-Type':xlsx?'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':'text/csv; charset=utf-8','Content-Disposition':`attachment; filename="historial-${result.from}-${result.to}.${xlsx?'xlsx':'csv'}"`,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});}
   return json(result);
  }
  if(path==='/api/branches'&&r.method==='GET'){
   if(u.searchParams.get('list')==='1'){const {results}=await env.DB.prepare('SELECT id,name,received_at FROM branches WHERE active=1 ORDER BY name').all();return json({branches:results});}
   const {results}=await env.DB.prepare('SELECT id,name,active,revision,received_at,payload FROM branches WHERE active=1 ORDER BY name').all();
   return json({branches:(await hydrateBranches(env.DB,results)).map(b=>({...b,payload:undefined}))});
  }
  if(path==='/api/branches'&&r.method==='POST'){
   const p=await body(r);if(typeof p.name!=='string'||!p.name.trim()||p.name.length>100)throw Error('Escribe el nombre del local');
   const token=key(),id=crypto.randomUUID();await env.DB.prepare('INSERT INTO branches(id,name,token_hash) VALUES(?,?,?)').bind(id,p.name.trim(),await hash(token)).run();return json({id,token,name:p.name.trim()});
  }
  if(path==='/api/revoke'&&r.method==='POST'){
   const p=await body(r);await env.DB.prepare('UPDATE branches SET active=0 WHERE id=?').bind(p.id).run();return json({ok:true});
  }
  if(path==='/api/rotate'&&r.method==='POST'){
   const p=await body(r),token=key();const branch=await env.DB.prepare('SELECT id FROM branches WHERE id=? AND active=1').bind(p.id).first();if(!branch)return json({error:'Local inexistente'},404);
   await env.DB.batch([env.DB.prepare('UPDATE branches SET token_hash=?,device_id=NULL,revision=0 WHERE id=? AND active=1').bind(await hash(token),p.id),env.DB.prepare('UPDATE history_days SET revision=0 WHERE branch_id=?').bind(p.id)]);return json({id:p.id,token});
  }
  if(path==='/api/logout'&&r.method==='POST'){
   const token=(r.headers.get('Cookie')||'').match(/central_session=([a-f0-9]{64})/)?.[1];if(token)await env.DB.prepare('DELETE FROM sessions WHERE token_hash=?').bind(await hash(token)).run();return json({ok:true},200,{'Set-Cookie':'central_session=; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'});
  }
  return json({error:'Ruta inexistente'},404);
 }catch(e){return json({error:e instanceof SyntaxError?'Solicitud inválida':'No se pudo procesar la solicitud. Revisa los datos y la configuración.'},400);}
}};

const dispatch=worker.fetch.bind(worker);
worker.fetch=async(r,env,ctx)=>{
 const url=new URL(r.url);
 if(url.protocol!=='https:'){url.protocol='https:';return new Response(null,{status:308,headers:{Location:url.href,'Cache-Control':'no-store'}});}
 const response=await dispatch(r,env,ctx),headers=new Headers(response.headers);
 headers.set('Strict-Transport-Security','max-age=31536000');
 headers.set('X-Content-Type-Options','nosniff');
 headers.set('Referrer-Policy','no-referrer');
 headers.set('X-Frame-Options','DENY');
 headers.set('Permissions-Policy','camera=(), microphone=(), geolocation=()');
 headers.set('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
 return new Response(response.body,{status:response.status,statusText:response.statusText,headers});
};
export default worker;
