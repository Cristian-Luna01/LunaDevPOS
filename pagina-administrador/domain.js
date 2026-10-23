export function validateSnapshot(p){
 if(!p||![1,2].includes(p.version)||p.currency!=='MXN'||!Number.isSafeInteger(p.revision)||p.revision<1)throw Error('Actualización inválida');
 if(typeof p.instance_id!=='string'||!/^([a-f0-9]{32})$/.test(p.instance_id))throw Error('Computadora inválida');
 if(typeof p.name!=='string'||!p.name.trim()||p.name.length>100||typeof p.generated_at!=='string'||!Number.isFinite(Date.parse(p.generated_at)))throw Error('Sucursal inválida');
 const catalog=p.version===2?p.direction?.products:p.products;
 if(!/^\d{4}-\d{2}-\d{2}$/.test(p.today)||!Array.isArray(p.daily)||p.daily.length!==31||!Array.isArray(catalog)||catalog.length>50000)throw Error('Periodo o catálogo inválido');
 const dates=new Set(),ids=new Set();
 for(const d of p.daily){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(d.day)||dates.has(d.day))throw Error('Fecha inválida');dates.add(d.day);
  for(const k of ['sales_cents','refunds_cents','net_cents','tickets','credit_cents','cost_cents','profit_cents'])if(!Number.isSafeInteger(d[k])||Math.abs(d[k])>1e12)throw Error('Importe inválido');
  if(d.sales_cents-d.refunds_cents!==d.net_cents||d.net_cents-d.cost_cents!==d.profit_cents)throw Error('Resumen inconsistente');
  for(const k of ['cash','card','transfer'])if(!Number.isSafeInteger(d.payments_by_method?.[k]))throw Error('Medio de pago inválido');
  if(Object.values(d.payments_by_method).reduce((a,b)=>a+b,0)!==d.net_cents)throw Error('Medios de pago inconsistentes');
 }
 if(!dates.has(p.today))throw Error('Falta el día actual');
 for(const r of catalog){
  if(!Number.isSafeInteger(r.id)||r.id<1||ids.has(r.id))throw Error('Producto duplicado');ids.add(r.id);
  if(typeof r.name!=='string'||r.name.length>500||typeof r.barcode!=='string'||r.barcode.length>500)throw Error('Producto inválido');
  if(r.inventory_value_cents!==undefined&&(!Number.isSafeInteger(r.inventory_value_cents)||r.inventory_value_cents<0))throw Error('Valor de inventario inválido');
  for(const k of ['stock','price_cents','cost_cents','reorder_point'])if(!Number.isSafeInteger(r[k])||r[k]<0||r[k]>1e12)throw Error('Existencia inválida');
 }
 if(p.version===2){const d=p.direction;if(!d||d.day!==p.today||!Array.isArray(d.products)||!Array.isArray(d.shifts)||!Array.isArray(d.suppliers)||!Array.isArray(d.history_days)||!d.history_fingerprints)throw Error('Panel incompleto');for(const day of d.history_days)if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!/^[a-f0-9]{64}$/.test(d.history_fingerprints[day]||''))throw Error('Historial inválido');}
 return p;
}

export function summarize(branches, day, id='all'){
 const selected=branches.filter(b=>id==='all'||b.id===id),keys=['net_cents','profit_cents','cost_cents','sales_cents','refunds_cents','tickets','credit_cents'];
 const totals=Object.fromEntries(keys.map(k=>[k,0]));totals.payments_by_method={cash:0,card:0,transfer:0};
 const missing=[];
 for(const b of selected){const d=b.snapshot?.daily.find(r=>r.day===day);if(!d){missing.push(b.id);continue;}for(const k of keys)totals[k]+=d[k];for(const k of ['cash','card','transfer'])totals.payments_by_method[k]+=d.payments_by_method[k];}
 return {totals,missing,branches:selected};
}
