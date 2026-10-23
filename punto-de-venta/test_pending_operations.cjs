const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto');
const source=fs.readFileSync(__dirname+'/static/pending-operations.js','utf8');
function server(){return {pending:null,records:new Map(),mutations:0,lose:true,async request(path,data){
 if(path==='/operations/pending')return {pending:this.pending?{...this.pending,...(this.records.has(this.pending.key)?{state:'confirmed',result:this.records.get(this.pending.key)}:{state:'not_found'})}:null};
 if(path==='/operations/prepare'){this.pending={kind:data.kind,key:data.key,body:data.body,path:{sale:'/sales',cash:'/cash'}[data.kind]};return {state:'not_found'};}
 if(path==='/operations/ack'){const result=this.records.get(data.key);this.pending=null;return {state:'confirmed',result};}
 if(path==='/operations/cancel'){const result=this.records.get(data.key);this.pending=null;return result?{state:'confirmed',result}:{state:'cancelled'};}
 if(path==='/cash'||path==='/sales'){if(!this.records.has(data.request_key)){this.mutations++;this.records.set(data.request_key,{id:this.mutations,total_cents:100,change_cents:0});}if(this.lose){this.lose=false;throw Error('Respuesta perdida');}return this.records.get(data.request_key);}
 throw Error(path);
}};}
function ui(backend){const events=[],nodes=new Map(),banner={hidden:true,querySelector(key){if(!nodes.has(key))nodes.set(key,{textContent:'',disabled:false});return nodes.get(key);},querySelectorAll(){return ['[data-check]','[data-retry]','[data-cancel]'].map(x=>this.querySelector(x));},setAttribute(){}};
 const context={window:{},crypto,confirm:()=>true,location:{reload(){}},CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},document:{createElement:()=>banner,getElementById:()=>({prepend(){}}),dispatchEvent:e=>events.push(e)},fetch:async(url,options)=>({ok:true,json:()=>backend.request(url.replace('/api',''),options?.body?JSON.parse(options.body):null)})};
 vm.runInNewContext(source,context);return {api:context.window.pendingOperations,events,banner};}
test('respuesta perdida y recarga recuperan la misma entrada sin duplicarla',async()=>{
 const backend=server(),first=ui(backend);await assert.rejects(first.api.run('/cash',{amount_cents:100,direction:'in',category:'change',concept:'QA'}),/perdida/);assert.equal(backend.mutations,1);assert.equal(first.banner.hidden,false);
 const reopened=ui(backend);await reopened.api.recover();assert.equal(backend.mutations,1);assert.equal(reopened.banner.hidden,true);assert.equal(backend.pending,null);
});
test('venta ya confirmada se recupera con el ticket original',async()=>{
 const backend=server(),first=ui(backend);await assert.rejects(first.api.run('/sales',{request_key:'same-sale',items:[],payments:[]}),/perdida/);
 const reopened=ui(backend);await reopened.api.recover();assert.equal(backend.mutations,1);assert.equal(reopened.events[0].type,'recovered-sale');assert.equal(reopened.events[0].detail.id,1);
});
test('una operación incierta impide enviar un movimiento distinto',async()=>{
 const backend=server(),page=ui(backend);await assert.rejects(page.api.run('/cash',{amount_cents:100}),/perdida/);await assert.rejects(page.api.run('/cash',{amount_cents:200}),/otra operación pendiente/);assert.equal(backend.mutations,1);
});
