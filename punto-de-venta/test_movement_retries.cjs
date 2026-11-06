const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/static/app.js','utf8');
function setup(){
 const sent=[];let sequence=0,fail=true;
 const context={crypto:{randomUUID:()=>String(++sequence)},JSON,Map,$:()=>({}),fetch:async(path,options)=>{
  sent.push(JSON.parse(options.body));
  if(fail){fail=false;throw Error('Respuesta perdida');}
  return {ok:true,json:async()=>({id:1})};
 }};
 vm.createContext(context);
 vm.runInContext(source.slice(source.indexOf('let movementRequestKeys='),source.indexOf('const act =')),context);
 return {api:context.api,sent};
}
test('un reintento reutiliza clave y una operación confirmada obtiene otra',async()=>{
 for(const route of ['/cash','/inventory/receive']){
  const s=setup(),body={amount_cents:100};
  await assert.rejects(s.api(route,body),/Respuesta perdida/);
  await s.api(route,body);
  assert.equal(s.sent[0].request_key,s.sent[1].request_key);
  await s.api(route,body);
  assert.notEqual(s.sent[1].request_key,s.sent[2].request_key);
  assert.equal(body.request_key,undefined);
 }
});
