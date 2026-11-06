# LunaDevPOS mejorado · 0.2.0-beta.1

La copia se encuentra en copia del proyecto.
El proyecto original permanece intacto.

## Cambios

- Historial financiero reservado a reportes; tickets propios disponibles para cajeros.
- Cortes Z conservados desde su reporte congelado.
- Red fuera del bloqueo de restauración; manejo acotado de peticiones rechazadas.
- Diario durable de cobros, abonos, devoluciones y movimientos: registra el cuerpo
  antes del envío y permite recuperar el resultado tras reiniciar.
- Idempotencia de ventas, devoluciones, abonos, movimientos, recepción detallada y
  reposición sencilla. Un reintento confirmado no vuelve a descontar inventario.
- Respaldos externos configurables, cada 30 minutos y bajo demanda; validación de
  archivo y restauración de prueba en una base temporal.
- Sincronización comprimida por partes, con verificación, revisión y publicación
  únicamente cuando se recibe el documento completo.
- Búsquedas por código y por subcadenas mediante índices/FTS5, y rangos históricos
  indexables; cálculo de abonos limitado a clientes relevantes.
- Selección de productos y lotes por nombre/código; recepción con caducidad/costo.
- Pantalla de comprobación de impresora y escáner sin movimientos comerciales.
- Compilación centralizada, dependencias bloqueadas con hashes y manifiesto por archivo.
- Pruebas automáticas, prueba real de Qt WebEngine y medición con datos ficticios.

## Uso

Para uso diario abre **Abrir LunaPOS**. Para desarrollar utiliza `herramientas/Ejecutar-codigo.cmd`; utiliza la misma carpeta `datos`, por lo que debes cerrar antes el programa compilado.
El instalador y el paquete portátil generados no necesitan Python instalado.
Para probar el ejecutable portátil con datos separados, utiliza --data-dir con
una carpeta nueva. El instalador de actualización conserva la ubicación habitual
por usuario; antes de usarlo en el negocio, exporta un respaldo y prueba la copia.

Mantenimiento → Respaldos automáticos externos permite elegir la carpeta y
comprobar restauración. El destino actual es `LunaPOS/respaldos`. Guardar en el mismo disco no protege de su avería.

Los límites y los pasos de compilación están en docs/COMPILACION-Y-OPERACION.md.
El protocolo presencial está en docs/VALIDACION-EQUIPO.md.

## Límites

Esta entrega sigue en beta. El programa optimizado de esta carpeta está preparado para uso local; no se ha publicado una entrega nueva en internet. No se han probado periféricos físicos ni un corte eléctrico real.
La facturación sigue en sandbox. El nuevo transporte requiere actualizar el
Worker central; no se ha publicado en una cuenta real desde esta revisión.
Los respaldos externos requieren seleccionar destino y se comprueban localmente;
si es una carpeta sincronizada, la subida al proveedor debe verificarse aparte.

## Verificación final

La entrega mejorada anterior aprobó 223 pruebas Python y 30 JavaScript. El motor depurado pasó las comprobaciones de interfaz y PDF descritas en README.md. Las verificaciones históricas del instalador y de restauración corresponden a aquella entrega, no a un instalador nuevo creado durante esta reorganización.
Las pruebas físicas y la publicación central se realizan aparte.


## Programa optimizado

La aplicación compilada ocupa unos 467 MB. Conserva Qt Widgets, WebEngine, impresión, español/inglés y conector remoto; excluye QML, Tkinter y traducciones no utilizadas. El código de esta carpeta incorpora esa receta de compilación y el diagnóstico `--runtime-check`.
