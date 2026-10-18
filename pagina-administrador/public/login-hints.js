/* Recuerda únicamente usuarios que iniciaron sesión correctamente en este dispositivo. */
(()=>{
 const key='pos-known-users-v1',inputs=[...document.querySelectorAll('#loginForm input[name="username"],#directionLoginForm input[name="username"]')];
 const read=()=>{try{const value=JSON.parse(localStorage.getItem(key)||'[]');return Array.isArray(value)?value.filter(v=>typeof v==='string'&&v.length<=254).slice(0,20):[];}catch{return [];}};
 function options(){for(const input of inputs){const list=document.getElementById(input.getAttribute('list'));if(list){list.replaceChildren();for(const value of read()){const option=document.createElement('option');option.value=value;list.append(option);}}}}
 for(const [i,input]of inputs.entries()){
  const list=document.createElement('datalist');list.id='known-users-'+i;input.setAttribute('list',list.id);input.setAttribute('autocomplete','off');input.after(list);
  input.addEventListener('keydown',event=>{if(event.key!=='Tab'||event.shiftKey)return;const prefix=input.value.trim().toLocaleLowerCase();if(!prefix)return;const match=read().find(v=>v.toLocaleLowerCase().startsWith(prefix));if(match)input.value=match;});
 }
 for(const input of document.querySelectorAll('#loginForm input[name="secret"],#directionLoginForm input[name="secret"]'))input.setAttribute('autocomplete','new-password');
 document.addEventListener('login-user-confirmed',event=>{const name=String(event.detail||'').trim();if(!name||name.length>254)return;try{const users=[name,...read().filter(v=>v.toLocaleLowerCase()!==name.toLocaleLowerCase())].slice(0,20);localStorage.setItem(key,JSON.stringify(users));options();}catch{}});options();
})();
