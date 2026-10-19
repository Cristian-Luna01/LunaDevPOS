import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

test('actualizaciones idénticas conservan las tarjetas y la posición de lectura',()=>{
 let writes=0,scrolls=0,markup='';
 const doc={activeElement:null,querySelector:()=>({id:'inventory'}),querySelectorAll:()=>[],addEventListener(){}};
 const context={document:doc,window:{},scrollX:0,scrollY:500,innerHeight:800,requestAnimationFrame:fn=>fn(),scrollTo:()=>scrolls++};
 vm.runInNewContext(readFileSync(new URL('../public/live-view.js',import.meta.url),'utf8'),context);
 const target={querySelectorAll:()=>[],get innerHTML(){return markup;},set innerHTML(value){markup=value;writes++;}};
 for(let i=0;i<100;i++)context.window.liveView.html(target,'<article>Stock: 20</article>');
 assert.equal(writes,1);assert.equal(scrolls,1);
 context.window.liveView.html(target,'<article>Stock: 19</article>');assert.equal(writes,2);
});

test('panel local y central usan el mismo criterio de evitar reconstrucciones idénticas',()=>{
 for(const path of ['../public/direccion/panel.js','../../punto-de-venta/static/direction.js']){
  const source=readFileSync(new URL(path,import.meta.url),'utf8');
  const snippet=source.slice(source.indexOf('function directionHTML'),source.indexOf('function renderPurchases'));
  let writes=0,value='';const node={get innerHTML(){return value;},set innerHTML(v){writes++;value=v;}};
  const c={window:{}};vm.runInNewContext(snippet,c);
  for(let i=0;i<100;i++)c.directionHTML(node,'sin cambios');assert.equal(writes,1);
  c.directionHTML(node,'nueva venta');assert.equal(writes,2);
  assert.equal((source.match(/directionHTML\(\$\('/g)||[]).length,6);
 }
});
