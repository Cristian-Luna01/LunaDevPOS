(()=>{
 const button=document.createElement('button');button.textContent='Comprobar impresora y escáner';document.getElementById('maintenanceOptions').append(button);
 button.onclick=()=>{
  transferScreen('Prueba del equipo',`<p>Esta prueba no registra ventas ni cambia existencias.</p><label>Escanea un código<input id="equipmentCode" autocomplete="off" placeholder="Escanea y termina con Enter"></label><p id="equipmentScanStatus" role="status">Esperando lectura.</p><button id="equipmentPrint">Imprimir ticket de prueba</button><p>Comprueba que el código aparece completo y una sola vez. En la impresión revisa ancho 58/80 mm, acentos, importes y corte de papel.</p><p>Para energía y recuperación utiliza el protocolo de pruebas incluido en docs/VALIDACION-EQUIPO.md.</p>`);
  let reads=0;const input=document.getElementById('equipmentCode');input.focus();input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();reads++;document.getElementById('equipmentScanStatus').textContent=`Lectura ${reads}: ${input.value} · ${input.value.length} caracteres`;input.value='';}};
  document.getElementById('equipmentPrint').onclick=()=>{
   const receipt=document.getElementById('receipt');receipt.replaceChildren();const title=document.createElement('h2');title.textContent='PRUEBA · SIN VALOR DE VENTA';const detail=document.createElement('p');detail.textContent='LunaDev POS\nCódigo: 7501234567890\n2 productos · $123.45\nRecibido: $200.00\nCambio: $76.55\nAcentos: á é í ó ú ñ\n'+new Date().toLocaleString('es-MX');detail.style.whiteSpace='pre-line';receipt.append(title,detail);window.print();
  };
 };
})();
