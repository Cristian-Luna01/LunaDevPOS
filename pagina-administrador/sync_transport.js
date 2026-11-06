// Partes pequeñas en D1: ningún catálogo depende de caber en una sola fila.
const enc=new TextEncoder(),MAX_RAW=32*1024*1024,PART=512*1024;
export const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
const from64=value=>Uint8Array.from(atob(value),c=>c.charCodeAt(0));
const to64=bytes=>{let s='';for(let i=0;i<bytes.length;i+=32768)s+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(s);};
async function limited(stream){
 const reader=stream.getReader(),parts=[];let size=0;
 try{while(true){const {value,done}=await reader.read();if(done)break;size+=value.length;if(size>MAX_RAW)throw Error('Actualización demasiado grande');parts.push(value);}}
 finally{await reader.cancel().catch(()=>{});}
 const result=new Uint8Array(size);let offset=0;for(const part of parts){result.set(part,offset);offset+=part.length;}return result;
}
export async function unpack(DB,branch,pointer){
 const {results}=await DB.prepare('SELECT part,data FROM sync_parts WHERE branch_id=? AND upload_id=? ORDER BY part').bind(branch,pointer.chunks).all();
 if(results.length!==pointer.count||results.some((p,i)=>p.part!==i))throw Error('Actualización incompleta');
 const chunks=results.map(p=>from64(p.data)),size=chunks.reduce((n,p)=>n+p.length,0);
 if(size>16*1024*1024)throw Error('Actualización demasiado grande');
 const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
 if(await digest(bytes)!==pointer.sha256)throw Error('Verificación de actualización fallida');
 const raw=await limited(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip')));
 return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw));
}
export async function loadPayload(DB,branch,value){
 const parsed=typeof value==='string'?JSON.parse(value):value;
 return parsed?.transport==='gzip-parts-v1'?unpack(DB,branch,parsed):parsed;
}
export async function savePayload(DB,branch,payload){
 const text=JSON.stringify(payload),raw=enc.encode(text);if(raw.length<=1500000)return text;
 if(raw.length>MAX_RAW)throw Error('Actualización demasiado grande');
 const packed=await limited(new Blob([raw]).stream().pipeThrough(new CompressionStream('gzip')));
 const hash=await digest(packed),storageId=await digest(enc.encode('storage-512:'+hash)),count=Math.ceil(packed.length/PART);if(count>32)throw Error('Actualización demasiado grande');
 for(let i=0;i<count;i++)await DB.prepare('INSERT OR IGNORE INTO sync_parts VALUES(?,?,?,?,?)').bind(branch,storageId,i,to64(packed.subarray(i*PART,(i+1)*PART)),Date.now()).run();
 return JSON.stringify({transport:'gzip-parts-v1',chunks:storageId,count,sha256:hash,history_storage:payload.history_storage});
}
export async function receivePart(r,env,readBody){
 const token=r.headers.get('Authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];if(!token)throw Error('Clave de sucursal requerida');
 const tokenHash=await digest(enc.encode(token)),b=await env.DB.prepare('SELECT id,device_id FROM branches WHERE token_hash=? AND active=1').bind(tokenHash).first();if(!b)throw Error('Sucursal no autorizada');
 const p=await readBody(r);
 if(!['snapshot','history'].includes(p.kind)||!Number.isSafeInteger(p.revision)||p.revision<1||!/^[a-f0-9]{32}$/.test(p.instance_id||'')||!/^[a-f0-9]{64}$/.test(p.sha256||'')||p.upload_id!==p.sha256||!Number.isInteger(p.parts)||p.parts<1||p.parts>32||!Number.isInteger(p.part)||p.part<0||p.part>=p.parts||typeof p.data!=='string'||p.data.length>700000||from64(p.data).length>PART)throw Error('Parte de actualización inválida');
 if(b.device_id&&b.device_id!==p.instance_id)throw Error('La clave pertenece a otra computadora');
 const old=await env.DB.prepare('SELECT * FROM sync_uploads WHERE branch_id=? AND upload_id=?').bind(b.id,p.upload_id).first();
 if(old&&(old.kind!==p.kind||old.revision!==p.revision||old.device_id!==p.instance_id||old.parts!==p.parts||old.sha256!==p.sha256))throw Error('Manifiesto incompatible');
 await env.DB.prepare('INSERT OR IGNORE INTO sync_uploads VALUES(?,?,?,?,?,?,?,?)').bind(b.id,p.upload_id,p.kind,p.revision,p.instance_id,p.parts,p.sha256,Date.now()).run();
 const existing=await env.DB.prepare('SELECT data FROM sync_parts WHERE branch_id=? AND upload_id=? AND part=?').bind(b.id,p.upload_id,p.part).first();
 if(existing&&existing.data!==p.data)throw Error('Parte incompatible');
 await env.DB.prepare('INSERT OR IGNORE INTO sync_parts VALUES(?,?,?,?,?)').bind(b.id,p.upload_id,p.part,p.data,Date.now()).run();
 const n=await env.DB.prepare('SELECT COUNT(*) n FROM sync_parts WHERE branch_id=? AND upload_id=?').bind(b.id,p.upload_id).first();
 if(n.n!==p.parts)return {complete:false,ok:true,revision:p.revision,part:p.part};
 const payload=await unpack(env.DB,b.id,{chunks:p.upload_id,count:p.parts,sha256:p.sha256});
 if(payload.revision!==p.revision||payload.instance_id!==p.instance_id)throw Error('Identidad o revisión incompatible');
 return {complete:true,payload,kind:p.kind};
}
export async function cleanupParts(DB){
 await DB.prepare("DELETE FROM sync_parts WHERE created_at<? AND upload_id NOT IN (SELECT json_extract(payload,'$.chunks') FROM branches WHERE json_extract(payload,'$.chunks') IS NOT NULL UNION SELECT json_extract(payload,'$.chunks') FROM history_days WHERE json_extract(payload,'$.chunks') IS NOT NULL)").bind(Date.now()-86400000).run();
 await DB.prepare('DELETE FROM sync_uploads WHERE created_at<?').bind(Date.now()-86400000).run();
}
