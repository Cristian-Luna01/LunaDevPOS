import {readDocument,storeDocument} from './documents.js';
// Mantiene resúmenes históricos sin duplicar los movimientos detallados.
export function cutoffDay(now=new Date()){
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Mexico_City',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
 return new Date(Date.parse(today+'T00:00:00Z')-29*86400000).toISOString().slice(0,10);
}
export function compact(report){
 if(report.history_storage==='summary')return report;
 const cash=report.cash_totals||{in:report.cash_movements.filter(m=>m.direction==='in').reduce((a,m)=>a+m.amount_cents,0),out:report.cash_movements.filter(m=>m.direction==='out').reduce((a,m)=>a+m.amount_cents,0)};
 return {from:report.from,to:report.to,totals:report.totals,products:report.products,cash_totals:cash,events:[],cash_movements:[],card_fees:[],inventory_adjustments:[],inventory_adjustment_count:report.inventory_adjustments?.length||0,inventory_adjustments_available:report.inventory_adjustments_available===true,history_storage:'summary'};
}
export function retained(report,day,now=new Date()){
 return day<cutoffDay(now)?compact(report):report;
}
export async function cleanup(DB,now=new Date()){
 // Lotes pequeños y actualización condicionada: no pisa una revisión concurrente.
 const {results}=await DB.prepare("SELECT branch_id,day,fingerprint,revision,payload FROM history_days WHERE day<? AND COALESCE(json_extract(payload,'$.history_storage'),'detail')!='summary' ORDER BY day LIMIT 20").bind(cutoffDay(now)).all();
 if(!results.length)return 0;
 const updates=await Promise.all(results.map(async row=>{
  const report=await readDocument(DB,row.branch_id,row.payload);const reduced=compact(report);
  if(JSON.stringify(report.totals)!==JSON.stringify(reduced.totals)||JSON.stringify(report.products)!==JSON.stringify(reduced.products))throw Error('Resumen inconsistente');
  return DB.prepare('UPDATE history_days SET payload=? WHERE branch_id=? AND day=? AND revision=? AND fingerprint=? AND payload=?').bind(await storeDocument(DB,row.branch_id,reduced),row.branch_id,row.day,row.revision,row.fingerprint,row.payload);
 }));
 await DB.batch(updates);return results.length;
}
