import {loadPayload} from './sync_transport.js';
import {retained} from './retention.js';
const fields=['sales_cents','refunds_cents','net_cents','sold_units','returned_units','tickets','credit_cents','tax_cents','cost_cents','profit_cents','zero_cost_units','card_fee_cents','card_fee_unconfigured_cents'];
export const zeros=()=>({...Object.fromEntries(fields.map(k=>[k,0])),payments_by_method:{cash:0,card:0,transfer:0}});
const plus=(a,b)=>{for(const k of fields)a[k]+=(b[k]||0);for(const k of ['cash','card','transfer'])a.payments_by_method[k]+=b.payments_by_method?.[k]||0;a.after_fees_cents=a.net_cents-a.card_fee_cents;a.profit_after_fees_cents=a.profit_cents-a.card_fee_cents;};
export function selectBranches(rows,id){if(id!=='all'&&!rows.some(b=>b.id===id))throw Error('Local inexistente');return rows.filter(b=>id==='all'||b.id===id);}
const productId=(b,id)=>b.id+':'+id;
const name=(b,value,all)=>all?b.name+' Â· '+value:value;
export function summary(rows,user,all=true){
 all=all&&rows.length>1;
 const data={...zeros(),user,day:rows.map(b=>b.snapshot?.today).filter(Boolean).sort().at(-1)||new Date().toISOString().slice(0,10),updated_at:new Date().toISOString(),products:[],shifts:[],suppliers:[]};
 const missing=[];
 for(const b of rows){const d=b.snapshot?.direction;if(!d){missing.push(b.name);continue;}const today=d.day===data.day?d:b.snapshot.daily.find(r=>r.day===data.day);if(today)plus(data,today);else missing.push(b.name);
  data.products.push(...d.products.map(p=>({...p,id:productId(b,p.id),name:name(b,p.name,all)})));
  data.shifts.push(...d.shifts.filter(s=>!s.closed_at||d.day===data.day).map(s=>({...s,user:name(b,s.user,all)})));
  data.suppliers.push(...d.suppliers.map(s=>({...s,id:b.id+':'+s.id,business_name:name(b,s.business_name,all)})));
 }
 data.connections=rows.map(b=>({name:b.name,received_at:b.received_at,ready:!!b.snapshot?.direction}));
 data.coverage_warning=missing.length?'Faltan datos de: '+missing.join(', ')+'. El total visible estÃ¡ incompleto.':'';
 return data;
}
export function dates(from,to){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(from||'')||!/^\d{4}-\d{2}-\d{2}$/.test(to||''))throw Error('Selecciona fechas vÃ¡lidas');
 const a=new Date(from+'T00:00:00Z'),b=new Date(to+'T00:00:00Z');if(a.toISOString().slice(0,10)!==from||b.toISOString().slice(0,10)!==to||from<'2000-01-01'||b<a||(b-a)/86400000>365)throw Error('Consulta hasta 366 dÃ­as');
 return Array.from({length:(b-a)/86400000+1},(_,i)=>new Date(a.getTime()+i*86400000).toISOString().slice(0,10));
}
export function mergeHistory(rows,documents,from,to,all=true){
 all=all&&rows.length>1;
 const daily=dates(from,to).map(day=>({day,...zeros()})),byDay=new Map(daily.map(d=>[d.day,d])),products=new Map(),events=[],cash_movements=[],card_fees=[];
 const available=new Map(documents.map(r=>[r.branch_id+':'+r.day,r])),summaryDays=new Set(),adjustments=[];
 let adjustmentCount=0,adjustmentsReady=rows.every(b=>b.snapshot?.direction?.inventory_adjustments_supported===true);
 for(const d of daily){d.cash_in_cents=0;d.cash_out_cents=0;}
 for(const b of rows){
  if(!b.snapshot?.direction)throw Error('Este local todavÃ­a no ha enviado el panel completo: '+b.name);
  if(to>b.snapshot.today)throw Error('Sin informaciÃ³n posterior a '+b.snapshot.today+' para '+b.name+'. Consulta hasta esa fecha o espera la actualizaciÃ³n del local.');
  const manifest=new Set(b.snapshot.direction.history_days);
  for(const day of byDay.keys()){
   if(!manifest.has(day))continue;
   const doc=available.get(b.id+':'+day);if(!doc||doc.fingerprint!==b.snapshot.direction.history_fingerprints[day])throw Error('El historial de '+b.name+' se estÃ¡ sincronizando. Actualiza en unos segundos.');
   const r=retained(typeof doc.payload==='string'?JSON.parse(doc.payload):doc.payload,day);plus(byDay.get(day),r.totals);
   if(r.inventory_adjustments_available!==true)adjustmentsReady=false;
   adjustmentCount+=r.inventory_adjustment_count??r.inventory_adjustments?.length??0;
   adjustments.push(...(r.inventory_adjustments||[]).map(a=>({...a,id:b.id+':'+a.id,branch_name:b.name,product_id:productId(b,a.product_id)})));
   if(r.history_storage==='summary')summaryDays.add(day);
   const cash=r.cash_totals||{in:r.cash_movements.filter(m=>m.direction==='in').reduce((a,m)=>a+m.amount_cents,0),out:r.cash_movements.filter(m=>m.direction==='out').reduce((a,m)=>a+m.amount_cents,0)};
   byDay.get(day).cash_in_cents+=cash.in;byDay.get(day).cash_out_cents+=cash.out;
   for(const p of r.products){const id=productId(b,p.id),existing=products.get(id)||{...p,id,name:name(b,p.name,all),...zeros()};plus(existing,p);products.set(id,existing);}
   events.push(...r.events.map(e=>({...e,product_id:productId(b,e.product_id),ticket_id:all?name(b,String(e.ticket_id),true):e.ticket_id,name:name(b,e.name,all)})));
   card_fees.push(...(r.card_fees||[]).map(f=>({...f,source_id:all?name(b,String(f.source_id),true):f.source_id})));
   cash_movements.push(...r.cash_movements.map(m=>({...m,id:all?b.id+':'+m.id:m.id,shift_id:all?name(b,String(m.shift_id),true):m.shift_id,user_name:name(b,m.user_name,all)})));
  }
 }
 const totals=zeros();daily.forEach(d=>plus(totals,d));events.sort((a,b)=>a.happened_at.localeCompare(b.happened_at));cash_movements.sort((a,b)=>b.happened_at.localeCompare(a.happened_at));
 return {from,to,daily,inventory_adjustments:{available:adjustmentsReady,count:adjustmentCount,items:adjustments.sort((a,b)=>b.happened_at.localeCompare(a.happened_at))},products:[...products.values()],events,totals,cash_movements,card_fees:card_fees.sort((a,b)=>b.happened_at.localeCompare(a.happened_at)),cash_totals:{in:daily.reduce((a,d)=>a+d.cash_in_cents,0),out:daily.reduce((a,d)=>a+d.cash_out_cents,0)},detail_coverage:{retention_days:30,summary_days:[...summaryDays].sort(),message:summaryDays.size?'Este periodo incluye fechas conservadas solo como resumen. Los totales y mÃ©tricas incluyen todas las fechas; las listas de tickets, movimientos y comisiones solo muestran el detalle disponible. Consulta el punto de venta del local para el detalle histÃ³rico completo.':''}};
}
export function metrics(result,previous,rows,all=true){
 all=all&&rows.length>1;
 const count=result.daily.length,activity=new Map(result.products.map(p=>[p.id,p]));
 for(const b of rows)for(const p of b.snapshot.direction.products){const id=productId(b,p.id),row=activity.get(id)||{id,name:name(b,p.name,all),barcode:p.barcode,...zeros()};row.stock=p.stock;activity.set(id,row);}
 for(const b of rows)for(const [id,stock]of Object.entries(b.snapshot.direction.metric_stock||{})){const row=activity.get(productId(b,id));if(row)row.stock=stock;}
 for(const p of activity.values()){p.stock??=0;p.net_units=p.sold_units-p.returned_units;p.daily_units=Math.round(Math.max(0,p.net_units)/count*10000)/10000;p.coverage_days=p.net_units>0?Math.round(p.stock*count/p.net_units*10)/10:null;}
 result.products=[...activity.values()].sort((a,b)=>b.net_units-a.net_units||a.name.localeCompare(b.name));result.previous={from:previous.from,to:previous.to,totals:previous.totals};result.days=count;
 result.weekdays=['Lunes','Martes','MiÃ©rcoles','Jueves','Viernes','SÃ¡bado','Domingo'].map(name=>({name,days:0,net_cents:0,units:0}));
 for(const d of result.daily){const w=result.weekdays[(new Date(d.day+'T00:00:00Z').getUTCDay()+6)%7];w.days++;w.net_cents+=d.net_cents;w.units+=d.sold_units-d.returned_units;}
 delete result.events;return result;
}
export async function history(DB,rows,from,to,all=true,metric=false){
 dates(from,to);const count=(new Date(to)-new Date(from))/86400000+1,previousTo=new Date(new Date(from)-86400000).toISOString().slice(0,10),previousFrom=new Date(new Date(from)-(count+0)*86400000).toISOString().slice(0,10);
 const docs=[];for(const b of rows){const q=await DB.prepare('SELECT branch_id,day,fingerprint,payload FROM history_days WHERE branch_id=? AND day BETWEEN ? AND ? ORDER BY day').bind(b.id,metric?previousFrom:from,to).all();for(const doc of q.results)docs.push({...doc,payload:await loadPayload(DB,doc.branch_id,doc.payload)});}
 const result=mergeHistory(rows,docs,from,to,all);
 return metric?metrics(result,mergeHistory(rows,docs,previousFrom,previousTo,all),rows,all):result;
}
