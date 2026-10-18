(()=>{
 const explanations={
  'Ventas totales':'Dinero cobrado por ventas y abonos, menos devoluciones y anulaciones. Un crédito pendiente no se suma. Ejemplo: cobras $80 y devuelves $10: total $70.',
  'Ganancia real':'Ventas totales menos el costo de compra de los productos que ya cobraste. Ejemplo: cobras $80 y esos productos te costaron $38.66: ganas $41.34. No descuenta gastos del negocio.',
  'Cobros antes de devoluciones':'Todo lo recibido por ventas pagadas y abonos, antes de restar devoluciones y anulaciones. No incluye el fondo inicial ni entradas extraordinarias de caja.',
  'Devoluciones y anulaciones':'Importes devueltos por devoluciones y anulaciones en la fecha consultada. Se restan de los cobros para calcular las ventas totales.',
  'Costo correspondiente a lo cobrado':'Lo que a la farmacia le costaron los productos que ya cobró. En abonos parciales se reconoce el costo proporcional; al saldar, el costo completo. No es deuda pendiente.',
  'Tickets registrados':'Cantidad de tickets de venta creados en las fechas consultadas, incluidas las compras a crédito. Un abono no crea otro ticket de venta.',
  'Tickets registrados hoy':'Cantidad de tickets de venta creados hoy, incluidas las compras a crédito. Un abono no crea otro ticket de venta.',
  'Efectivo':'Ventas y abonos cobrados en efectivo, menos devoluciones en efectivo. No incluye el fondo inicial ni entradas o salidas extraordinarias. El efectivo esperado del cajón se consulta en el corte.',
  'Tarjeta':'Ventas y abonos cobrados con tarjeta de débito o crédito, menos devoluciones por tarjeta. Este dinero no está en el cajón de efectivo.',
  'Transferencia / depósito':'Ventas y abonos cobrados por transferencia o depósito, menos devoluciones por ese medio. Este dinero se recibe en la cuenta bancaria.'
 };
 const tooltip=document.createElement('div');tooltip.id='metricExplanation';tooltip.className='metric-tooltip';tooltip.setAttribute('role','tooltip');tooltip.hidden=true;document.body.append(tooltip);
 let active=null;
 function hide(){tooltip.hidden=true;active=null;}
 function show(card){active=card;tooltip.textContent=card.dataset.explanation;tooltip.hidden=false;const rect=card.getBoundingClientRect(),box=tooltip.getBoundingClientRect();const left=Math.max(8,Math.min(rect.left,innerWidth-box.width-8));let top=rect.bottom+8;if(top+box.height>innerHeight-8)top=Math.max(8,rect.top-box.height-8);tooltip.style.left=left+'px';tooltip.style.top=top+'px';}
 function attach(){document.querySelectorAll('.direction-metrics article,.payment-summary-grid article').forEach(card=>{
  if(card.dataset.explanation)return;
  const label=Array.from(card.childNodes).filter(node=>node.nodeName!=='STRONG').map(node=>node.textContent).join('').trim();const explanation=explanations[label];if(!explanation)return;
  card.dataset.explanation=explanation;card.classList.add('metric-explained');card.tabIndex=0;card.setAttribute('aria-describedby',tooltip.id);
  card.addEventListener('mouseenter',()=>show(card));card.addEventListener('mouseleave',()=>{if(document.activeElement!==card)hide();});card.addEventListener('focus',()=>show(card));card.addEventListener('blur',hide);card.addEventListener('click',()=>show(card));
 });if(active&&!active.isConnected)hide();}
 document.addEventListener('keydown',event=>{if(event.key==='Escape')hide();});document.addEventListener('click',event=>{if(active&&!active.contains(event.target))hide();});window.addEventListener('scroll',hide,true);window.addEventListener('resize',hide);
 attach();new MutationObserver(attach).observe(document.body,{childList:true,subtree:true});
})();
