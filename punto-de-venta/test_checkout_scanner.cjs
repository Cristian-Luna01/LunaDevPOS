const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/static/app.js','utf8');
function setup(failFirst=false){
 const added=[],lookups=[],messages=[];let selected=0;
 const input={value:'',select(){selected++;},focus(){}};
 const nodes={clearSearch:{hidden:true},search:input,dialog:{open:false},moreProducts:{hidden:false},workspace:{hidden:false},shiftGate:{hidden:true}};
 const state={$:id=>nodes[id],act:fn=>fn,setTimeout,clearTimeout,queryVersion:0,page:0,products:[],currentView:'checkout',me:{shift:{id:1}},document:{activeElement:input,body:{},querySelector(){return nodes.dialog.open?nodes.dialog:null;},addEventListener(type,fn){state.capture=fn;}},renderProducts(){},searchProducts(){},notify:m=>messages.push(m),async add(p){added.push(p.barcode);},async api(url){const code=new URL('http://local'+url).searchParams.get('q');lookups.push(code);await new Promise(r=>setTimeout(r,10));if(failFirst&&lookups.length===1)throw Error('Sin conexión');return code==='missing'?[]:[{id:code,barcode:code,stock:10}];}};
 const snippet=source.slice(source.indexOf('let searchTimer;'),source.indexOf("$('moreProducts').onclick"));vm.runInNewContext(snippet,state);
 const scan=code=>{input.value=code;return input.onkeydown({key:'Enter',preventDefault(){}});};
 return{input,added,lookups,messages,scan,state,selected:()=>selected};
}
test('lecturas consecutivas se vacían inmediatamente y se agregan en orden',async()=>{
 const s=setup();const first=s.scan('123456');assert.equal(s.input.value,'');const second=s.scan('654321');assert.equal(s.input.value,'');await Promise.all([first,second]);assert.deepEqual(s.lookups,['123456','654321']);assert.deepEqual(s.added,['123456','654321']);
});
test('fallo en una lectura no bloquea las siguientes',async()=>{
 const s=setup(true);await s.scan('123456');await s.scan('654321');assert.deepEqual(s.added,['654321']);assert.equal(s.messages.length,1);
});
test('búsqueda manual no se captura como escaneo; no roba foco de otro campo',async()=>{
 const s=setup();s.input.value='Paracetamol';await s.input.onkeydown({key:'l',preventDefault(){throw Error('No debe interceptar');}});assert.equal(s.input.value,'Paracetamol');assert.equal(s.lookups.length,0);s.input.onfocus();assert.equal(s.input.value,'');
 let focus=0;s.input.focus=()=>focus++;s.state.document.activeElement={id:'customerSearch'};await s.scan('123456');assert.equal(focus,0);
});
test('código inexistente avisa y deja lista otra lectura',async()=>{
 const s=setup();await s.scan('missing');assert.equal(s.input.value,'');assert.equal(s.added.length,0);assert.ok(s.messages[0].includes('No se encontró'));await s.scan('123456');assert.deepEqual(s.added,['123456']);
});
test('pistola sin foco en búsqueda captura ráfaga y agrega; fuera del mostrador no actúa',async()=>{
 const s=setup();const target={closest(){return null;}};const key=(key,timeStamp)=>s.state.capture({key,timeStamp,target,preventDefault(){},stopImmediatePropagation(){}});
 for(const [i,c]of [...'123456'].entries())key(c,1000+i*10);key('Enter',1065);await new Promise(r=>setTimeout(r,25));assert.deepEqual(s.added,['123456']);assert.equal(s.input.value,'');
 s.state.currentView='cash';for(const [i,c]of [...'654321'].entries())key(c,2000+i*10);key('Enter',2065);await new Promise(r=>setTimeout(r,20));assert.equal(s.added.length,1);
});
test('no captura escritura lenta, formularios ni ventanas emergentes',async()=>{
 const s=setup();let target={closest(){return null;}};const key=(key,timeStamp)=>s.state.capture({key,timeStamp,target,preventDefault(){},stopImmediatePropagation(){}});
 for(const [i,c]of [...'123456'].entries())key(c,1000+i*300);key('Enter',2600);
 target={closest(){return {tagName:'INPUT'};}};for(const [i,c]of [...'123456'].entries())key(c,3000+i*10);key('Enter',3070);
 target={closest(){return null;}};s.state.$('dialog').open=true;for(const [i,c]of [...'123456'].entries())key(c,4000+i*10);key('Enter',4070);
 await new Promise(r=>setTimeout(r,20));assert.equal(s.added.length,0);
});

function typeBurst(s,text,start,step=10){
 for(const [i,key] of [...text].entries()){
  let prevented=false;
  s.state.capture({key,timeStamp:start+i*step,target:s.input,preventDefault(){prevented=true;},stopImmediatePropagation(){}});
  if(!prevented)s.input.value+=key;
 }
 s.state.capture({key:'Enter',timeStamp:start+text.length*step+5,target:s.input,preventDefault(){},stopImmediatePropagation(){}});
}
test('lector dentro del buscador elimina el prefijo escrito y no concatena códigos',async()=>{
 const s=setup();s.input.value='paracetamol';typeBurst(s,'7501234567890',1000);
 assert.equal(s.input.value,'');await new Promise(r=>setTimeout(r,25));
 assert.deepEqual(s.lookups,['7501234567890']);assert.deepEqual(s.added,['7501234567890']);
 typeBurst(s,'7509876543210',2000);await new Promise(r=>setTimeout(r,25));
 assert.deepEqual(s.added,['7501234567890','7509876543210']);assert.equal(s.input.value,'');
});
test('el botón limpia cancela una búsqueda pendiente y conserva el carrito',()=>{
 const s=setup();s.input.value='Texto';s.input.oninput();s.state.$('clearSearch').onclick();
 assert.equal(s.input.value,'');assert.equal(s.state.$('clearSearch').hidden,true);assert.equal(s.added.length,0);
});
test('escritura manual pausada dentro del buscador no se borra al escribir',()=>{
 const s=setup();s.input.value='para';
 for(const [i,key]of [...'cetamol'].entries()){
  s.state.capture({key,timeStamp:1000+i*120,target:s.input,preventDefault(){throw Error('No interceptar escritura manual');}});s.input.value+=key;
 }
 assert.equal(s.input.value,'paracetamol');assert.equal(s.lookups.length,0);
});
