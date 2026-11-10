import test from 'node:test';import assert from 'node:assert/strict';import {DatabaseSync}from'node:sqlite';import {readFileSync}from'node:fs';import {createHash,webcrypto}from'node:crypto';
import worker from '../worker.js';import {validateSnapshot,summarize}from'../domain.js';

const digest=x=>createHash('sha256').update(x).digest('hex'),secret='f'.repeat(64),origin='https://qa.workers.dev';
function environment(){const sqlite=new DatabaseSync(':memory:');sqlite.exec(readFileSync(new URL('../schema.sql',import.meta.url),'utf8'));sqlite.exec(readFileSync(new URL('../migrations/0002_full_direction.sql',import.meta.url),'utf8'));sqlite.exec(readFileSync(new URL('../migrations/0003_reliable_transfers.sql',import.meta.url),'utf8'));const DB={prepare(sql){return{values:[],bind(...values){this.values=values;return this;},async first(){return sqlite.prepare(sql).get(...this.values)||null;},async all(){return{results:sqlite.prepare(sql).all(...this.values)};},async run(){return{meta:sqlite.prepare(sql).run(...this.values)};}};},async batch(list){sqlite.exec('BEGIN');try{const r=await Promise.all(list.map(q=>q.run()));sqlite.exec('COMMIT');return r;}catch(e){sqlite.exec('ROLLBACK');throw e;}}};return{DB,OWNER_EMAIL:'owner@example.test',OWNER_PASSWORD_SHA256:digest(secret),sqlite};}
const req=(path,data,cookie='',token='')=>new Request(origin+'/api/'+path,{method:data?'POST':'GET',headers:{Origin:origin,Cookie:cookie,Authorization:token?'Bearer '+token:'','Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});
const payload=(revision=1,value=4000)=>({version:1,currency:'MXN',instance_id:'1'.repeat(32),revision,name:'Centro',generated_at:new Date().toISOString(),today:'2026-10-11',daily:Array.from({length:31},(_,i)=>({day:new Date(Date.UTC(2026,9,11-i)).toISOString().slice(0,10),sales_cents:i?0:value,refunds_cents:0,net_cents:i?0:value,cost_cents:i?0:1900,profit_cents:i?0:value-1900,tickets:i?0:1,credit_cents:0,payments_by_method:{cash:i?0:value,card:0,transfer:0}})),products:[{id:1,name:'Producto',barcode:'0001',stock:20,price_cents:4000,cost_cents:1900,reorder_point:5}]});

async function setup(){const env=environment();const login=await worker.fetch(req('login',{email:env.OWNER_EMAIL,secret}),env);const cookie=login.headers.get('Set-Cookie').split(';')[0];const branch=await(await worker.fetch(req('branches',{name:'QA'},cookie),env)).json();return {env,cookie,branch};}
function packets(value){const bytes=Buffer.from(JSON.stringify(value)),id=digest(bytes),chunks=[];for(let i=0;i<bytes.length;i+=250000)chunks.push(bytes.subarray(i,i+250000).toString('base64'));return chunks.map((data,part)=>({kind:'snapshot',part,total:chunks.length,digest:id,upload_id:id,data}));}
test('envío mayor a dos MB se almacena en bloques y se publica completo una sola vez',async()=>{
 const {env,cookie,branch}=await setup(),p=payload();p.products=Array.from({length:7000},(_,i)=>({...p.products[0],id:i+1,barcode:String(i),name:'Medicamento 💊 '+('x'.repeat(350))+i}));
 const parts=packets(p);assert.ok(parts.length>8);
 for(const part of parts.slice(0,-1)){const r=await worker.fetch(req('transfer',part,'',branch.token),env);assert.equal(r.status,200);assert.equal((await r.json()).complete,false);}
 assert.equal(env.sqlite.prepare('SELECT revision FROM branches WHERE id=?').get(branch.id).revision,0);
 const last=parts.at(-1);assert.equal((await worker.fetch(req('transfer',last,'',branch.token),env)).status,200);
 const repeated=await worker.fetch(req('transfer',last,'',branch.token),env);assert.deepEqual(await repeated.json(),{ok:true,revision:p.revision});
 assert.equal(env.sqlite.prepare('SELECT count(*) n FROM upload_parts WHERE part>=0').get().n,0);
 const result=await(await worker.fetch(req('branches',null,cookie),env)).json();assert.deepEqual(result.branches[0].snapshot,p);
 const stored=JSON.parse(env.sqlite.prepare('SELECT payload FROM branches WHERE id=?').get(branch.id).payload);assert.ok(stored.__chunked);assert.ok(env.sqlite.prepare('SELECT max(length(CAST(data AS BLOB))) n FROM document_chunks').get().n<2000000);
 env.sqlite.close();
});
test('el límite de cargas pendientes de un local no bloquea las de otro',async()=>{
 const {env,cookie,branch}=await setup(),other=await(await worker.fetch(req('branches',{name:'Otro'},cookie),env)).json();
 const insert=env.sqlite.prepare('INSERT INTO upload_parts VALUES(?,?,0,2,?,?,?,?)');
 for(let i=0;i<128;i++){const id=digest(String(i));insert.run(branch.id,id,'snapshot',id,'AA==',Date.now());}
 const id=digest('new'),packet={kind:'snapshot',part:0,total:2,digest:id,upload_id:id,data:'AA=='};
 assert.equal((await worker.fetch(req('transfer',packet,'',branch.token),env)).status,400);
 assert.equal((await worker.fetch(req('transfer',packet,'',other.token),env)).status,200);
 env.sqlite.close();
});
test('bloques incompletos, corruptos o de otro local nunca publican una instantánea parcial',async()=>{
 const {env,cookie,branch}=await setup(),other=await(await worker.fetch(req('branches',{name:'Otro'},cookie),env)).json();const p=payload();p.products[0].name='x'.repeat(450);p.padding='x'.repeat(900000);const parts=packets(p);
 assert.equal((await worker.fetch(req('transfer',parts[0]),env)).status,401);
 await worker.fetch(req('transfer',parts[0],'',branch.token),env);
 for(const part of parts.slice(1))await worker.fetch(req('transfer',part,'',other.token),env);
 assert.equal(env.sqlite.prepare('SELECT sum(revision) n FROM branches').get().n,0);
 const broken={...parts.at(-1),data:Buffer.from('corrupt').toString('base64')};
 for(const part of parts.slice(1,-1))await worker.fetch(req('transfer',part,'',branch.token),env);
 assert.equal((await worker.fetch(req('transfer',broken,'',branch.token),env)).status,400);
 assert.equal(env.sqlite.prepare('SELECT sum(revision) n FROM branches').get().n,0);env.sqlite.close();
});
test('documentos de historial fragmentados conservan la compactación y referencias activas',async()=>{
 const {storeDocument,readDocument,cleanupDocuments}=await import('../documents.js');const {cleanup}=await import('../retention.js');
 const env=environment();env.sqlite.prepare("INSERT INTO branches(id,name,token_hash) VALUES('b','QA','t')").run();
 const report={from:'2020-01-01',to:'2020-01-01',totals:{net_cents:0},products:[],daily:[],events:[{note:'💊'.repeat(300000)}],cash_movements:[],card_fees:[],inventory_adjustments:[],inventory_adjustments_available:true};
 const stored=await storeDocument(env.DB,'b',report);assert.ok(JSON.parse(stored).__chunked);
 env.sqlite.prepare('INSERT INTO history_days(branch_id,day,revision,fingerprint,payload) VALUES(?,?,?,?,?)').run('b',report.from,1,'a'.repeat(64),stored);
 await cleanup(env.DB,new Date('2026-10-21T12:00:00Z'));
 const pointer=env.sqlite.prepare('SELECT payload FROM history_days').get().payload;const summary=await readDocument(env.DB,'b',pointer);assert.equal(summary.history_storage,'summary');assert.deepEqual(summary.events,[]);assert.deepEqual(summary.totals,report.totals);
 const active=await storeDocument(env.DB,'b',{data:'z'.repeat(900000)});env.sqlite.prepare('UPDATE branches SET payload=?').run(active);env.sqlite.prepare('UPDATE document_chunks SET created_at=0').run();await cleanupDocuments(env.DB);assert.equal((await readDocument(env.DB,'b',active)).data.length,900000);env.sqlite.close();
});
