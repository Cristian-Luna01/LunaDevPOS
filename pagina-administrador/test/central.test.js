import test from 'node:test';import assert from 'node:assert/strict';import {DatabaseSync}from'node:sqlite';import {readFileSync}from'node:fs';import {createHash,webcrypto}from'node:crypto';
import worker from '../worker.js';import {validateSnapshot,summarize}from'../domain.js';

const digest=x=>createHash('sha256').update(x).digest('hex'),secret='f'.repeat(64),origin='https://qa.workers.dev';
function environment(){const sqlite=new DatabaseSync(':memory:');sqlite.exec(readFileSync(new URL('../schema.sql',import.meta.url),'utf8'));sqlite.exec(readFileSync(new URL('../migrations/0002_full_direction.sql',import.meta.url),'utf8'));sqlite.exec(readFileSync(new URL('../migrations/0003_reliable_transfers.sql',import.meta.url),'utf8'));const DB={prepare(sql){return{values:[],bind(...values){this.values=values;return this;},async first(){return sqlite.prepare(sql).get(...this.values)||null;},async all(){return{results:sqlite.prepare(sql).all(...this.values)};},async run(){return{meta:sqlite.prepare(sql).run(...this.values)};}};},async batch(list){sqlite.exec('BEGIN');try{const r=await Promise.all(list.map(q=>q.run()));sqlite.exec('COMMIT');return r;}catch(e){sqlite.exec('ROLLBACK');throw e;}}};return{DB,OWNER_EMAIL:'owner@example.test',OWNER_PASSWORD_SHA256:digest(secret),sqlite};}
const req=(path,data,cookie='',token='')=>new Request(origin+'/api/'+path,{method:data?'POST':'GET',headers:{Origin:origin,Cookie:cookie,Authorization:token?'Bearer '+token:'','Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});
const payload=(revision=1,value=4000)=>({version:1,currency:'MXN',instance_id:'1'.repeat(32),revision,name:'Centro',generated_at:new Date().toISOString(),today:'2026-10-11',daily:Array.from({length:31},(_,i)=>({day:new Date(Date.UTC(2026,9,11-i)).toISOString().slice(0,10),sales_cents:i?0:value,refunds_cents:0,net_cents:i?0:value,cost_cents:i?0:1900,profit_cents:i?0:value-1900,tickets:i?0:1,credit_cents:0,payments_by_method:{cash:i?0:value,card:0,transfer:0}})),products:[{id:1,name:'Producto',barcode:'0001',stock:20,price_cents:4000,cost_cents:1900,reorder_point:5}]});
test('dos locales suman sin mezclar inventarios ni duplicar reintentos',()=>{const a=payload(),b=payload(1,2000);const branches=[{id:'a',snapshot:a},{id:'b',snapshot:b}];const r=summarize(branches,'2026-10-11');assert.equal(r.totals.net_cents,6000);assert.equal(r.totals.profit_cents,2200);assert.equal(summarize(branches,'2026-10-11','a').totals.net_cents,4000);assert.equal(r.branches[0].snapshot.products[0].stock,20);assert.equal(summarize(branches,'2020-01-01').missing.length,2);});
test('validación impide importes alterados y productos repetidos',()=>{validateSnapshot(payload());const p=payload();p.daily[0].net_cents++;assert.throws(()=>validateSnapshot(p));const q=payload();q.products.push(q.products[0]);assert.throws(()=>validateSnapshot(q));});
test('cuenta protegida, claves por sucursal, revisión y revocación',async()=>{const env=environment();assert.equal((await worker.fetch(req('branches'),env)).status,401);const login=await worker.fetch(req('login',{email:env.OWNER_EMAIL,secret}),env);assert.equal(login.status,200);const cookie=login.headers.get('Set-Cookie').split(';')[0];const a=await(await worker.fetch(req('branches',{name:'Centro'},cookie),env)).json(),b=await(await worker.fetch(req('branches',{name:'Norte'},cookie),env)).json();assert.notEqual(a.token,b.token);const first=payload();assert.equal((await worker.fetch(req('snapshot',first,'',a.token),env)).status,200);assert.equal((await worker.fetch(req('snapshot',first,'',a.token),env)).status,200);let r=await(await worker.fetch(req('branches',null,cookie),env)).json();assert.equal(r.branches.find(x=>x.id===a.id).snapshot.daily[0].net_cents,4000);assert.equal(r.branches.find(x=>x.id===b.id).snapshot,null);assert.equal((await worker.fetch(req('snapshot',payload(3),'',a.token),env)).status,200);assert.equal((await worker.fetch(req('snapshot',payload(2),'',a.token),env)).status,409);assert.equal((await worker.fetch(req('branches',null,'',a.token),env)).status,401);await worker.fetch(req('revoke',{id:a.id},cookie),env);assert.equal((await worker.fetch(req('snapshot',payload(4),'',a.token),env)).status,401);await worker.fetch(req('logout',{},cookie),env);assert.equal((await worker.fetch(req('branches',null,cookie),env)).status,401);});
test('bloqueo de intentos y protección de origen',async()=>{const env=environment();for(let i=0;i<5;i++)assert.equal((await worker.fetch(req('login',{email:env.OWNER_EMAIL,secret:'wrong'}),env)).status,401);assert.equal((await worker.fetch(req('login',{email:env.OWNER_EMAIL,secret}),env)).status,429);const r=req('login',{email:env.OWNER_EMAIL,secret});r.headers.set('Origin','https://evil.test');assert.equal((await worker.fetch(r,env)).status,403);});
test('resumen histórico recibido, reintentos y CSV de detalle protegido',async()=>{
 const env=environment();const login=await worker.fetch(req('login',{email:env.OWNER_EMAIL,secret}),env);const cookie=login.headers.get('Set-Cookie').split(';')[0];
 const b=await(await worker.fetch(req('branches',{name:'Centro'},cookie),env)).json();const p=payload();p.version=2;
 const day='2020-01-01',fingerprint='a'.repeat(64);p.direction={day:p.today,products:p.products,shifts:[],suppliers:[],history_days:[day],history_fingerprints:{[day]:fingerprint}};
 assert.equal((await worker.fetch(req('snapshot',p,'',b.token),env)).status,200);
 const report={from:day,to:day,totals:{...p.daily[0],sold_units:1,returned_units:0},products:[],events:[{ticket_id:1,cents:4000}],cash_movements:[],card_fees:[]};
 const data={version:2,instance_id:p.instance_id,revision:2,day,fingerprint,report};
 assert.equal((await worker.fetch(req('history-day',data,'',b.token),env)).status,200);
 assert.equal((await worker.fetch(req('history-day',data,'',b.token),env)).status,200);
 const saved=JSON.parse(env.sqlite.prepare('SELECT payload FROM history_days').get().payload);assert.equal(saved.history_storage,'summary');assert.deepEqual(saved.events,[]);assert.equal(saved.totals.net_cents,4000);
 const path='history?from='+day+'&to='+day;const h=await(await worker.fetch(req(path,null,cookie),env)).json();assert.equal(h.totals.net_cents,4000);assert.deepEqual(h.detail_coverage.summary_days,[day]);
 assert.equal((await worker.fetch(req('history.csv?from='+day+'&to='+day,null,cookie),env)).status,409);
 assert.equal((await worker.fetch(req('history.csv?from='+day+'&to='+day+'&summary=1',null,cookie),env)).status,200);
 assert.equal((await worker.fetch(req('history.xlsx?from='+day+'&to='+day,null,cookie),env)).status,200);
});

test('HTTPS y cabeceras de seguridad también protegen respuestas de rechazo',async()=>{
 const env=environment();const redirect=await worker.fetch(new Request('http://qa.workers.dev/api/branches'),env);
 assert.equal(redirect.status,308);assert.equal(redirect.headers.get('Location'),origin+'/api/branches');
 const r=await worker.fetch(req('branches'),env);assert.equal(r.status,401);
 assert.equal(r.headers.get('Strict-Transport-Security'),'max-age=31536000');assert.equal(r.headers.get('X-Frame-Options'),'DENY');
 assert.equal(r.headers.get('X-Content-Type-Options'),'nosniff');assert.match(r.headers.get('Content-Security-Policy'),/frame-ancestors 'none'/);
});
test('sesión inventada o vencida no permite leer datos ni administrar sucursales',async()=>{
 const env=environment();
 for(const path of ['summary','history','metrics','branches','inventory-adjustments'])assert.equal((await worker.fetch(req(path,null,'central_session='+'a'.repeat(64)),env)).status,401);
 const r=await worker.fetch(req('login',{email:env.OWNER_EMAIL,secret}),env),header=r.headers.get('Set-Cookie');
 for(const flag of ['Secure','HttpOnly','SameSite=Strict'])assert.ok(header.includes(flag));
 env.sqlite.prepare('UPDATE sessions SET expires=0').run();const cookie=header.split(';')[0];
 assert.equal((await worker.fetch(req('branches',{name:'Intruso'},cookie),env)).status,401);
 assert.equal(env.sqlite.prepare('SELECT count(*) n FROM branches').get().n,0);
});
test('falta de configuración, credenciales SQL y cuerpos enormes fallan cerrados',async()=>{
 const env=environment();assert.equal((await worker.fetch(req('branches'),{...env,OWNER_PASSWORD_SHA256:''})).status,503);
 assert.equal((await worker.fetch(req('login',{email:"' OR 1=1 --",secret:'wrong'}),env)).status,401);
 assert.equal(env.sqlite.prepare('SELECT count(*) n FROM sessions').get().n,0);
 const tooBig=req('login',{email:env.OWNER_EMAIL,secret:'x'.repeat(910000)});assert.equal((await worker.fetch(tooBig,env)).status,400);
 assert.equal(env.sqlite.prepare('SELECT count(*) n FROM sessions').get().n,0);
});
test('consultar un local no descarga ni procesa el inventario de los demás',async()=>{
 const env=environment(),login=await worker.fetch(req('login',{email:env.OWNER_EMAIL,secret}),env),cookie=login.headers.get('Set-Cookie').split(';')[0];
 const a=await(await worker.fetch(req('branches',{name:'A'},cookie),env)).json(),b=await(await worker.fetch(req('branches',{name:'B'},cookie),env)).json();
 const p=payload();p.version=2;p.direction={day:p.today,products:p.products,shifts:[],suppliers:[],history_days:[],history_fingerprints:{}};
 assert.equal((await worker.fetch(req('snapshot',p,'',a.token),env)).status,200);
 env.sqlite.prepare('UPDATE branches SET payload=? WHERE id=?').run('invalid-json',b.id);
 const own=await worker.fetch(req('summary?branch='+a.id,null,cookie),env);assert.equal(own.status,200);assert.equal((await own.json()).products.length,1);
 const combined=await worker.fetch(req('summary',null,cookie),env);
 assert.equal(combined.status,200);
 const view=await combined.json();assert.equal(view.products.length,1);assert.match(view.coverage_warning,/B/);
 assert.equal((await worker.fetch(req('snapshot',{...p,__chunked:'a'.repeat(64),parts:1},'',b.token),env)).status,400);
});

test('historial rechaza contadores HTML y neutraliza fórmulas de las columnas de texto',async()=>{
 const {exportCSV}=await import('../exports.js');
 const env=environment(),login=await worker.fetch(req('login',{email:env.OWNER_EMAIL,secret}),env),cookie=login.headers.get('Set-Cookie').split(';')[0];
 const b=await(await worker.fetch(req('branches',{name:'Centro'},cookie),env)).json(),p=payload(),day=p.today,fingerprint='a'.repeat(64);
 p.version=2;p.direction={day,products:p.products,shifts:[],suppliers:[],history_days:[day],history_fingerprints:{[day]:fingerprint}};
 assert.equal((await worker.fetch(req('snapshot',p,'',b.token),env)).status,200);
 const report={from:day,to:day,totals:{...p.daily[0],sold_units:'<strong>falso</strong>'},products:[],events:[],cash_movements:[]};
 const data={version:2,instance_id:p.instance_id,revision:2,day,fingerprint,report};
 assert.equal((await worker.fetch(req('history-day',data,'',b.token),env)).status,400);
 report.totals.sold_units=2;report.__chunked='b'.repeat(64);
 assert.equal((await worker.fetch(req('history-day',data,'',b.token),env)).status,400);
 delete report.__chunked;
 assert.equal((await worker.fetch(req('history-day',data,'',b.token),env)).status,200);
 const csv=exportCSV({events:[{day,kind:'=1+1',status:'@SUM(1)',cents:-50}]});
 assert.ok(csv.includes('"\'=1+1"'));assert.ok(csv.includes('"\'@SUM(1)"'));assert.ok(csv.includes('"-0.50"'));
 env.sqlite.close();
});
test('intentos de acceso concurrentes no eluden el contador de bloqueo',async()=>{
 const env=environment();
 const responses=await Promise.all(Array.from({length:12},()=>worker.fetch(req('login',{email:env.OWNER_EMAIL,secret:'wrong'}),env)));
 assert.ok(responses.every(r=>[401,429].includes(r.status)));
 const attempt=env.sqlite.prepare('SELECT * FROM attempts').get();assert.ok(attempt.failures>=5);assert.ok(attempt.until_at>Date.now());
 assert.equal((await worker.fetch(req('login',{email:env.OWNER_EMAIL,secret}),env)).status,429);
});
