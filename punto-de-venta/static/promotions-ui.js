'use strict';
let promotionRows=[];
const promoDays=['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'];
function promotionSchedule(p){return p.schedule_type==='permanent'?'Permanente':p.schedule_type==='recurring'?promoDays.filter((_,i)=>p.weekday_mask&(1<<i)).join(', ')+(p.starts_on!=='0001-01-01'?' · Desde '+p.starts_on:'')+(p.ends_on!=='9999-12-31'?' · Hasta '+p.ends_on:''):p.starts_on+' al '+p.ends_on;}
async function loadPromotions(){
 promotionRows=await api('/promotions');
 const canEdit=me.permissions.includes('products.edit');$('promotionCreate').hidden=!canEdit;
 $('promotionRows').innerHTML=promotionRows.map(p=>`<article class="inventory-card"><div><strong>${esc(p.name)}</strong><small>${esc(p.product_name)} · ${esc(p.barcode)}</small><small>${esc(promotionSchedule(p))} · ${p.active?(p.is_current?'Vigente hoy':'Hoy no aplica'):'Desactivada'}</small></div><b>${p.bundle_quantity} por ${money(p.price_cents)}</b><button data-promo-search="${p.id}">Buscar para vender</button>${canEdit?`<button data-promo-edit="${p.id}">Editar</button>${p.active?`<button data-promo-disable="${p.id}">Desactivar</button>`:''}`:''}</article>`).join('')||'<p>No hay promociones. Quien tenga permiso de editar productos puede crear la primera.</p>';
}
function promotionForm(p={}){
 const now=new Date(),today=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
 modal('Configurar promoción',fields([{name:'name',label:'Nombre de la promoción',value:p.name},{name:'barcode',label:'Código exacto del producto',value:p.barcode}])+`<label>Tipo de promoción<select name="schedule_type">${[['permanent','Permanente'],['temporary','Temporal'],['recurring','Recurrente: días de la semana']].map(([v,t])=>`<option value="${v}" ${v===(p.schedule_type||'permanent')?'selected':''}>${t}</option>`).join('')}</select></label><div id="promoDates">`+fields([{name:'starts_on',label:'Desde (incluido)',type:'date',optional:true,value:p.starts_on==='0001-01-01'?'':p.starts_on||''},{name:'ends_on',label:'Hasta (incluido)',type:'date',optional:true,value:p.ends_on==='9999-12-31'?'':p.ends_on||''}])+`<small>En recurrentes, ambas fechas son opcionales.</small></div><fieldset id="promoWeekdays"><legend>Días en que aplica</legend>${promoDays.map((day,i)=>`<label><input type="checkbox" name="day${i}" ${(p.weekday_mask||0)&(1<<i)?'checked':''}>${day}</label>`).join('')}</fieldset>`+fields([{name:'bundle_quantity',label:'Unidades del mismo producto por paquete (1 para precio individual)',type:'number',value:p.bundle_quantity||1},{name:'price',label:'Precio TOTAL del paquete en pesos',value:p.price_cents!==undefined?(p.price_cents/100).toFixed(2):''}])+'<p>Ejemplo: 2 unidades por $15. Cada paquete completo recibe la oferta; las unidades sobrantes se cobran a precio normal. Una promoción por producto. Se aplica el mejor precio entre promoción y descuento del cliente, sin acumularlos.</p>',async d=>{const found=await api('/products?q='+encodeURIComponent(d.barcode));const product=found.find(r=>r.barcode===d.barcode.trim());if(!product)throw Error('No se encontró ese código exacto');const mask=promoDays.reduce((n,_,i)=>n+(d['day'+i]?1<<i:0),0);if(d.schedule_type==='recurring'&&!mask)throw Error('Selecciona al menos un día');await api('/promotions/save',{product_id:product.id,name:d.name,price_cents:cents(d.price),bundle_quantity:Number(d.bundle_quantity),schedule_type:d.schedule_type,weekday_mask:mask||127,starts_on:d.starts_on,ends_on:d.ends_on});await loadPromotions();await searchProducts();notify('Promoción guardada');});
 const type=$('dialogBody').querySelector('[name="schedule_type"]');
 const update=()=>{const temporal=type.value==='temporary';$('promoDates').hidden=type.value==='permanent';$('promoWeekdays').hidden=type.value!=='recurring';for(const input of $('promoDates').querySelectorAll('input')){input.required=temporal;input.disabled=type.value==='permanent';if(temporal&&!input.value)input.value=today;}};
 type.onchange=update;update();
 const qty=$('dialogBody').querySelector('[name="bundle_quantity"]');qty.min=1;qty.max=10000;
}
$('promotionCreate').onclick=()=>promotionForm();
$('promotionRefresh').onclick=act(loadPromotions);
document.querySelector('[data-view="promotions"]').addEventListener('click',act(loadPromotions));
$('promotionRows').onclick=act(async e=>{
 const b=e.target.closest('button');if(!b)return;
 const id=Number(b.dataset.promoSearch||b.dataset.promoEdit||b.dataset.promoDisable),p=promotionRows.find(r=>r.id===id);if(!p)return;
 if(b.dataset.promoEdit){promotionForm(p);return;}
 if(b.dataset.promoDisable){await api('/promotions/save',{product_id:p.product_id,disable:true});await loadPromotions();await searchProducts();return;}
 $('search').value=p.barcode;document.querySelector('[data-view="checkout"]').click();await searchProducts();
});
