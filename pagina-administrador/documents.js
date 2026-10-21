// Documentos grandes en filas acotadas; el puntero se publica solamente al completar.
const enc=new TextEncoder();
export const digest=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(text)))).map(v=>v.toString(16).padStart(2,'0')).join('');
export async function storeDocument(DB,branch,value){
 const text=JSON.stringify(value);if(enc.encode(text).length<=700000)return text;
 const blob=await digest(text),parts=[];
 for(let start=0;start<text.length;){let end=Math.min(start+100000,text.length);if(end<text.length&&/[\uD800-\uDBFF]/.test(text[end-1]))end--;parts.push(text.slice(start,end));start=end;}
 for(let i=0;i<parts.length;i+=20)await DB.batch(parts.slice(i,i+20).map((data,k)=>DB.prepare('INSERT OR IGNORE INTO document_chunks(branch_id,blob_id,part,data,created_at) VALUES(?,?,?,?,?)').bind(branch,blob,i+k,data,Date.now())));
 return JSON.stringify({__chunked:blob,parts:parts.length,history_storage:value.history_storage||'detail'});
}
export async function readDocument(DB,branch,text){
 if(!text)return null;const value=JSON.parse(text);if(!value.__chunked)return value;
 const {results}=await DB.prepare('SELECT part,data FROM document_chunks WHERE branch_id=? AND blob_id=? ORDER BY part').bind(branch,value.__chunked).all();
 if(results.length!==value.parts||results.some((p,i)=>p.part!==i))throw Error('Documento pendiente de completar. Actualiza en unos segundos.');
 const joined=results.map(p=>p.data).join('');if(await digest(joined)!==value.__chunked)throw Error('No coincide la verificación del documento');return JSON.parse(joined);
}
export async function hydrateBranches(DB,rows){return Promise.all(rows.map(async b=>({...b,snapshot:await readDocument(DB,b.id,b.payload)})));}
export async function cleanupDocuments(DB){
 await DB.batch([
 DB.prepare('DELETE FROM upload_parts WHERE rowid IN (SELECT rowid FROM upload_parts WHERE created_at<? LIMIT 200)').bind(Date.now()-3600000),
 DB.prepare(`DELETE FROM document_chunks WHERE rowid IN (SELECT c.rowid FROM document_chunks c WHERE c.created_at<? AND NOT EXISTS(SELECT 1 FROM branches b WHERE b.id=c.branch_id AND json_extract(b.payload,'$.__chunked')=c.blob_id) AND NOT EXISTS(SELECT 1 FROM history_days h WHERE h.branch_id=c.branch_id AND json_extract(h.payload,'$.__chunked')=c.blob_id) LIMIT 200)`).bind(Date.now()-60000)]);
}
export async function receivePart(DB,branch,p){
 if(!p||!['snapshot','history-day'].includes(p.kind)||!Number.isInteger(p.part)||!Number.isInteger(p.total)||p.part<0||p.part>=p.total||p.total<1||p.total>64||!/^[a-f0-9]{64}$/.test(p.digest||'')||p.upload_id!==p.digest||typeof p.data!=='string'||p.data.length>350000||!/^[A-Za-z0-9+/]*={0,2}$/.test(p.data))throw Error('Bloque de sincronización inválido');
 const old=await DB.prepare('SELECT total,kind,digest,data FROM upload_parts WHERE branch_id=? AND upload_id=? AND part=?').bind(branch,p.upload_id,p.part).first();
 if(old&&(old.total!==p.total||old.kind!==p.kind||old.digest!==p.digest||old.data!==p.data))throw Error('Bloque incompatible con el envío anterior');
 await DB.prepare('INSERT OR IGNORE INTO upload_parts(branch_id,upload_id,part,total,kind,digest,data,created_at) VALUES(?,?,?,?,?,?,?,?)').bind(branch,p.upload_id,p.part,p.total,p.kind,p.digest,p.data,Date.now()).run();
 const {results}=await DB.prepare('SELECT part,total,kind,digest,data FROM upload_parts WHERE branch_id=? AND upload_id=? ORDER BY part').bind(branch,p.upload_id).all();
 if(results.some(r=>r.total!==p.total||r.kind!==p.kind||r.digest!==p.digest))throw Error('Metadatos incompatibles');
 if(results.length!==p.total)return {complete:false};
 const bytes=results.map((r,i)=>{if(r.part!==i)throw Error('Falta un bloque');return Uint8Array.from(atob(r.data),c=>c.charCodeAt(0));});
 const size=bytes.reduce((n,b)=>n+b.length,0);if(size>16000000)throw Error('Documento superior al límite de 16 MB');
 const joined=new Uint8Array(size);let offset=0;for(const b of bytes){joined.set(b,offset);offset+=b.length;}
 const text=new TextDecoder('utf-8',{fatal:true}).decode(joined);if(await digest(text)!==p.digest)throw Error('No coincide la verificación de bloques');
 return {complete:true,text};
}
