import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync}from'node:fs';import vm from'node:vm';import{summary}from'../reporting.js';
test('Inventario central conserva costos de lote por sucursal y suma todos sin filtrar búsqueda',()=>{
 const branch=(id,value)=>({id,name:id,snapshot:{today:'2026-10-18',direction:{day:'2026-10-18',products:[{id:1,name:'A',inventory_value_cents:value,stock:2,reorder_point:1,price_cents:1000,barcode:'1'}],shifts:[],suppliers:[]}}});
 const a=branch('a',1500),b=branch('b',2700);
 assert.equal(summary([a],'Admin').products[0].inventory_value_cents,1500);
 assert.equal(summary([a,b],'Admin').products.reduce((n,p)=>n+p.inventory_value_cents,0),4200);
 const source=readFileSync(new URL('../public/direccion/panel.js',import.meta.url),'utf8');
 const render=source.slice(source.indexOf('function render(){'),source.indexOf('async function update(){'));
 const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,{value:'A',classList:{toggle(){}},setAttribute(){}});return nodes.get(id)};
 const context={$,directionHTML:(node,markup)=>{node.innerHTML=markup;},rows:summary([a,b],'Admin').products,filter:'all',limit:100,money:c=>String(c),esc:String};vm.createContext(context);vm.runInContext(render+';render();',context);
 assert.match($('directionInventoryValue').textContent,/4200/);
 context.rows=[{...context.rows[0],inventory_value_cents:undefined}];vm.runInContext('render()',context);assert.match($('directionInventoryValue').textContent,/pendiente/);
});
