import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {createHash,randomBytes} from 'node:crypto';
import {gzipSync} from 'node:zlib';
import worker from '../worker.js';
import {loadPayload,savePayload,cleanupParts} from '../sync_transport.js';
const hash=value=>createHash('sha256').update(value).digest('hex');
function environment(){
 const sqlite=new DatabaseSync(':memory:');
 for(const file of ['schema.sql','migrations/0002_full_direction.sql','migrations/0003_chunked_sync.sql'])sqlite.exec(readFileSync(new URL('../'+file,import.meta.url),'utf8'));
 const DB={prepare(sql){return {bind(...args){this.args=args;return this;},async first(){return sqlite.prepare(sql).get(...this.args)||null;},async all(){return {results:sqlite.prepare(sql).all(...this.args)};},async run(){return sqlite.prepare(sql).run(...this.args);}};},async batch(list){return Promise.all(list.map(p=>p.run()));}};
 return {DB,sqlite,OWNER_EMAIL:'owner@example.test',OWNER_PASSWORD_SHA256:hash('secret')};
}
function payload(){
 const products=Array.from({length:6000},(_,i)=>({id:i+1,name:randomBytes(160).toString('hex'),barcode:String(i),stock:1,price_cents:100,cost_cents:50,reorder_point:1}));
 return {version:1,currency:'MXN',instance_id:'1'.repeat(32),revision:1,name:'Local',generated_at:new Date().toISOString(),today:'2026-10-21',daily:Array.from({length:31},(_,i)=>({day:new Date(Date.UTC(2026,9,21-i)).toISOString().slice(0,10),sales_cents:0,refunds_cents:0,net_cents:0,tickets:0,credit_cents:0,cost_cents:0,profit_cents:0,payments_by_method:{cash:0,card:0,transfer:0}})),products};
}
test('catálogo mayor a 2 MB se publica completo solo al recibir todas las partes',async()=>{
 const env=environment(),token='a'.repeat(64);env.sqlite.prepare('INSERT INTO branches(id,name,token_hash) VALUES(?,?,?)').run('b','Local',hash(token));
 const p=payload(),raw=JSON.stringify(p);assert.ok(Buffer.byteLength(raw)>2000000);
 const bytes=gzipSync(raw),id=hash(bytes),parts=Math.ceil(bytes.length/262144);assert.ok(parts>1);
 let firstPart;
 for(let i=0;i<parts;i++){
  const part={kind:'snapshot',revision:1,instance_id:p.instance_id,upload_id:id,sha256:id,parts,part:i,data:bytes.subarray(i*262144,(i+1)*262144).toString('base64')};firstPart??=part;
  const request=new Request('https://qa.workers.dev/api/upload-part',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(part)});
  const response=await worker.fetch(request,env);assert.equal(response.status,200,await response.clone().text());
  const ack=await response.json();assert.equal(ack.revision,1);
  const row=env.sqlite.prepare('SELECT revision,payload FROM branches WHERE id=?').get('b');
  if(i<parts-1){assert.equal(row.revision,0);assert.equal(row.payload,null);}else assert.equal(ack.complete,true);
 }
 const row=env.sqlite.prepare('SELECT payload FROM branches WHERE id=?').get('b');
 assert.equal(JSON.parse(row.payload).transport,'gzip-parts-v1');
 assert.deepEqual(await loadPayload(env.DB,'b',row.payload),p);
 const retry=await worker.fetch(new Request('https://qa.workers.dev/api/upload-part',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(firstPart)}),env);
 assert.equal(retry.status,200);
 assert.equal(env.sqlite.prepare('SELECT revision FROM branches').get().revision,1);
});
test('una parte alterada o una sucursal ajena no reemplazan datos',async()=>{
 const env=environment();const pointer=await savePayload(env.DB,'a',{text:'x'.repeat(2100000)});
 const parsed=JSON.parse(pointer);assert.equal((await loadPayload(env.DB,'a',pointer)).text.length,2100000);
 await assert.rejects(loadPayload(env.DB,'b',pointer),/incompleta/);
 env.sqlite.prepare('UPDATE sync_parts SET data=? WHERE branch_id=? AND upload_id=?').run(Buffer.from('bad').toString('base64'),'a',parsed.chunks);
 await assert.rejects(loadPayload(env.DB,'a',pointer),/Verificación/);
});
test('la limpieza conserva partes referenciadas y elimina las abandonadas',async()=>{
 const env=environment(),pointer=await savePayload(env.DB,'a',{text:'x'.repeat(2100000)});
 env.sqlite.prepare('INSERT INTO branches(id,name,token_hash,payload) VALUES(?,?,?,?)').run('a','Local','hash',pointer);
 env.sqlite.prepare('UPDATE sync_parts SET created_at=0').run();
 env.sqlite.prepare('INSERT INTO sync_parts VALUES(?,?,?,?,?)').run('a','abandoned',0,'eA==',0);
 await cleanupParts(env.DB);assert.equal(env.sqlite.prepare('SELECT COUNT(*) n FROM sync_parts WHERE upload_id=?').get('abandoned').n,0);
 assert.equal((await loadPayload(env.DB,'a',pointer)).text.length,2100000);
});
test('heartbeat autenticado actualiza conexión y conserva el documento',async()=>{
 const env=environment(),token='c'.repeat(64),device='1'.repeat(32);
 env.sqlite.prepare('INSERT INTO branches(id,name,token_hash,device_id,revision,payload) VALUES(?,?,?,?,?,?)').run('b','Local',hash(token),device,1,'{"saved":true}');
 const send=(instance_id,revision)=>worker.fetch(new Request('https://qa.workers.dev/api/heartbeat',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({instance_id,revision})}),env);
 assert.equal((await send(device,2)).status,200);
 const row=env.sqlite.prepare('SELECT revision,payload,received_at FROM branches').get();assert.equal(row.revision,1);assert.equal(row.payload,'{"saved":true}');assert.ok(row.received_at);
 assert.equal((await send('2'.repeat(32),3)).status,409);
 assert.equal((await send(device,0)).status,409);
 env.sqlite.prepare('UPDATE branches SET active=0').run();assert.equal((await send(device,4)).status,401);
});
test('el detalle de un día grande también se conserva completo por partes',async()=>{
 const env=environment(),token='d'.repeat(64),device='3'.repeat(32),day=new Date().toISOString().slice(0,10);
 env.sqlite.prepare('INSERT INTO branches(id,name,token_hash,device_id,revision) VALUES(?,?,?,?,?)').run('b','Local',hash(token),device,1);
 const events=payload().products.map(p=>({product_id:p.id,name:p.name,ticket_id:p.id,cents:100}));
 const report={from:day,to:day,events,products:[],cash_movements:[],totals:{net_cents:600000}};
 const p={version:2,instance_id:device,revision:2,day,fingerprint:'a'.repeat(64),report};
 const raw=JSON.stringify(p);assert.ok(Buffer.byteLength(raw)>2000000);
 const bytes=gzipSync(raw),id=hash(bytes),parts=Math.ceil(bytes.length/524288);
 for(let i=0;i<parts;i++){
  const part={kind:'history',revision:2,instance_id:device,upload_id:id,sha256:id,parts,part:i,data:bytes.subarray(i*524288,(i+1)*524288).toString('base64')};
  const response=await worker.fetch(new Request('https://qa.workers.dev/api/upload-part',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(part)}),env);
  assert.equal(response.status,200,await response.clone().text());
 }
 const saved=env.sqlite.prepare('SELECT payload FROM history_days WHERE branch_id=? AND day=?').get('b',day);
 const loaded=await loadPayload(env.DB,'b',saved.payload);assert.equal(loaded.events.length,6000);assert.equal(loaded.totals.net_cents,600000);
});
