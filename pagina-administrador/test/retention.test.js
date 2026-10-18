import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {compact,cutoffDay,retained,cleanup} from '../retention.js';
import {mergeHistory,metrics,zeros} from '../reporting.js';
import {exportCSV,exportXLSX} from '../exports.js';
const now=new Date('2026-10-12T18:00:00Z');
function report(day){
 const totals={...zeros(),sales_cents:10000,refunds_cents:2000,net_cents:8000,cost_cents:4000,profit_cents:4000,tickets:2,sold_units:2,returned_units:1,credit_cents:3000,card_fee_cents:406,payments_by_method:{cash:4000,card:4000,transfer:0}};
 return {from:day,to:day,totals,products:[{...totals,id:1,name:'Producto',barcode:'001'}],events:[{day,happened_at:day+'T12:00:00',product_id:1,ticket_id:1,name:'Producto',cents:8000}],cash_movements:[{id:1,shift_id:1,user_name:'QA',direction:'in',amount_cents:5000,happened_at:day+'T12:00:00'},{id:2,shift_id:1,user_name:'QA',direction:'out',amount_cents:2000,happened_at:day+'T12:00:00'}],card_fees:[{happened_at:day+'T12:00:00',source_id:1,gross_cents:10000,net_cents:9594,fee_cents:406,tariff:{provider:'Prueba'},configured:true}]};
}
test('30 fechas locales incluyendo hoy; no depende de hora UTC',()=>{
 assert.equal(cutoffDay(now),'2026-09-13');
 assert.equal(cutoffDay(new Date('2026-10-12T03:00:00Z')),'2026-09-12');
 assert.equal(retained(report('2026-09-13'),'2026-09-13',now).events.length,1);
 assert.equal(retained(report('2026-09-12'),'2026-09-12',now).events.length,0);
});
test('compresión conserva importes exactos y caja; es idempotente y ocupa menos',()=>{
 const full=report('2020-01-01');for(let i=0;i<100;i++)full.events.push({...full.events[0],ticket_id:i+2});
 const reduced=compact(full);assert.deepEqual(reduced.totals,full.totals);assert.deepEqual(reduced.products,full.products);
 assert.deepEqual(reduced.cash_totals,{in:5000,out:2000});assert.deepEqual(compact(reduced),reduced);assert.ok(JSON.stringify(reduced).length<JSON.stringify(full).length/4);
});
test('mezcla fechas resumidas y detalladas de dos locales sin duplicar; métricas y exportación',()=>{
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Mexico_City'}).format(new Date());
 const days=['2020-01-01',today],rows=['a','b'].map(id=>({id,name:id,snapshot:{today,direction:{history_days:days,history_fingerprints:Object.fromEntries(days.map(d=>[d,'hash'])),products:[{id:1,name:'Producto',barcode:'001',stock:10}]}}}));
 // Rangos separados porque la consulta permite hasta 366 días.
 for(const day of days){
  const docs=rows.map(b=>({branch_id:b.id,day,fingerprint:'hash',payload:JSON.stringify(day===today?report(day):compact(report(day)))}));
  const r=mergeHistory(rows,docs,day,day);
  assert.equal(r.totals.net_cents,16000);assert.equal(r.totals.profit_cents,8000);assert.equal(r.products.length,2);assert.deepEqual(r.cash_totals,{in:10000,out:4000});
  assert.equal(r.events.length,day===today?2:0);assert.equal(r.detail_coverage.summary_days.length,day===today?0:1);
  assert.ok(exportCSV(r,true).includes('160.00'));assert.ok(exportXLSX(r).length>1000);
  if(day!==today)assert.ok(new TextDecoder().decode(exportXLSX(r)).includes('Cobertura del historial'));
  const m=metrics(r,{from:day,to:day,totals:zeros()},rows);assert.equal(m.weekdays.reduce((a,w)=>a+w.net_cents,0),16000);assert.equal(m.products.reduce((a,p)=>a+p.net_units,0),2);
 }
});
test('limpieza persistente reemplaza solo detalle antiguo y no elimina el resumen',async()=>{
 const sqlite=new DatabaseSync(':memory:');sqlite.exec(readFileSync(new URL('../schema.sql',import.meta.url),'utf8'));sqlite.exec(readFileSync(new URL('../migrations/0002_full_direction.sql',import.meta.url),'utf8'));
 sqlite.prepare("INSERT INTO branches(id,name,token_hash) VALUES('a','Centro','key')").run();
 for(const day of ['2026-09-12','2026-09-13'])sqlite.prepare('INSERT INTO history_days VALUES(?,?,?,?,?)').run('a',day,1,'hash',JSON.stringify(report(day)));
 const DB={prepare(sql){return{bind(...args){this.args=args;return this;},async all(){return{results:sqlite.prepare(sql).all(...this.args)};},async run(){return sqlite.prepare(sql).run(...this.args);}};},async batch(list){sqlite.exec('BEGIN');try{const results=[];for(const q of list)results.push(await q.run());sqlite.exec('COMMIT');return results;}catch(e){sqlite.exec('ROLLBACK');throw e;}}};
 assert.equal(await cleanup(DB,now),1);assert.equal(await cleanup(DB,now),0);
 const saved=JSON.parse(sqlite.prepare("SELECT payload FROM history_days WHERE day='2026-09-12'").get().payload);assert.equal(saved.history_storage,'summary');assert.equal(saved.totals.profit_cents,4000);assert.equal(saved.events.length,0);
 assert.equal(JSON.parse(sqlite.prepare("SELECT payload FROM history_days WHERE day='2026-09-13'").get().payload).events.length,1);sqlite.close();
});
test('ajustes por local se muestran una vez; versiones antiguas no se confunden con cero',()=>{
 const day=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Mexico_City'}).format(new Date());
 const rows=['a','b'].map(id=>({id,name:id,snapshot:{today:day,direction:{inventory_adjustments_supported:true,history_days:[day],history_fingerprints:{[day]:'hash'}}}}));
 const docs=rows.map(b=>{const r=report(day);r.inventory_adjustments_available=true;r.inventory_adjustments=[{id:1,product_id:1,name:'Producto',before:20,after:18,difference:-2,user_name:'QA',reason:'Conteo físico',happened_at:day+' 12:00:00'}];return{branch_id:b.id,day,fingerprint:'hash',payload:JSON.stringify(r)};});
 const result=mergeHistory(rows,docs,day,day);assert.equal(result.inventory_adjustments.available,true);assert.equal(result.inventory_adjustments.count,2);assert.equal(new Set(result.inventory_adjustments.items.map(a=>a.id)).size,2);assert.equal(result.inventory_adjustments.items[0].reason,'Conteo físico');
 delete rows[0].snapshot.direction.inventory_adjustments_supported;assert.equal(mergeHistory(rows,docs,day,day).inventory_adjustments.available,false);
 const compacted=compact({...report('2020-01-01'),inventory_adjustments_available:true,inventory_adjustments:[{id:1}]});assert.equal(compacted.inventory_adjustment_count,1);assert.deepEqual(compacted.inventory_adjustments,[]);
});
