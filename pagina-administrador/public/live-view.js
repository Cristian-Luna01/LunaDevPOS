/* Conserva lectura, foco y scroll al actualizar datos; no navega ni recarga. */
(()=>{
 let interaction=0;for(const event of ['wheel','touchstart','pointerdown','keydown'])document.addEventListener(event,()=>interaction++,{capture:true,passive:true});
 function capture(root=document){
  const section=document.querySelector('.direction-section:not([hidden])'),focus=document.activeElement;
  const candidates=[...root.querySelectorAll('[data-live-key]')];
  const anchor=candidates.find(node=>{const r=node.getBoundingClientRect();return r.bottom>90&&r.top<innerHeight;});
  return {x:scrollX,y:scrollY,interaction,section:section?.id,root,key:anchor?.dataset.liveKey,offset:anchor?.getBoundingClientRect().top,focus:focus?.id,start:focus?.selectionStart,end:focus?.selectionEnd};
 }
 function restore(state){
  requestAnimationFrame(()=>{
   if(interaction!==state.interaction)return;
   const section=document.querySelector('.direction-section:not([hidden])');if(section?.id!==state.section)return;
   let y=state.y;
   if(state.key){const anchor=[...state.root.querySelectorAll('[data-live-key]')].find(n=>n.dataset.liveKey===state.key);if(anchor)y=scrollY+anchor.getBoundingClientRect().top-state.offset;}
   scrollTo({left:state.x,top:y,behavior:'instant'});
   if(state.focus){const focus=document.getElementById(state.focus);if(focus&&document.activeElement?.id!==state.focus){focus.focus({preventScroll:true});if(focus.setSelectionRange&&state.start!==null)try{focus.setSelectionRange(state.start,state.end);}catch{}}}
  });
 }
 function html(target,value){if(target.innerHTML===value)return;const state=capture(target);target.innerHTML=value;restore(state);}
 window.liveView={capture,restore,html};
})();
