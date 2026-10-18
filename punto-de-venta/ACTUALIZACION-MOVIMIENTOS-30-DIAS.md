# Movimientos de productos y conservación de 30 días

Entrega del 14 de octubre de 2026, Windows x64.

## Instalar

Haz un respaldo manual, termina el turno y cierra LunaDev POS. Ejecuta Instalar-LunaDevPOS-Movimientos30Dias.exe. La actualización conserva inventario, ventas, clientes, cuentas y configuración. Abre el programa, comprueba que la vinculación central sigue conectada y espera a que termine de sincronizar las fechas. No hace falta crear otra sucursal ni cambiar la clave.

La página central de pruebas ya fue publicada. Recarga la página del dueño y abre **Movimientos de productos**, debajo de Ventas y caja. Empieza en la fecha de hoy y permite consultar otro día. Respeta la sucursal elegida o Todos los locales. Se presentan tarjetas, no una tabla extensa.

## Qué se registra

- Ajustar existencia: unidades anteriores, nuevas, diferencia, motivo, usuario, fecha y local. Se muestra un solo ajuste de producto aunque afecte varios lotes.
- Editar producto y cambiar precio de venta o costo de compra configurado: valores anteriores y nuevos, motivo obligatorio, usuario, fecha y local. Un cambio de ambos precios genera una tarjeta con ambos campos.
- El costo configurado no sustituye retroactivamente los costos históricos de ventas o lotes.

No se registran como correcciones manuales todas las ventas ni cada recepción de mercancía: esas operaciones conservan sus registros normales. Un cambio de nombre por sí solo no genera tarjeta. La recepción de un lote con otro costo es distinta de editar el costo configurado y no se presenta como tal.

El historial de ajustes anteriores hechos con Ajustar existencia puede sincronizarse porque ya estaba guardado. Los cambios de precios antiguos que no guardaron valores anteriores ni motivo no se pueden reconstruir. Para generar el nuevo registro de cambios de precio es necesario utilizar esta actualización.

Si un local aún no usa una versión que envía movimientos o no terminó de sincronizar el día, la página indicará información incompleta o pendiente. No lo interpreta como que no hubo cambios. Cuando hay confirmación y no existen registros, indica que no hubo modificaciones ese día.

## Plazos

**Nube:** detalle de hoy y los 29 días anteriores según la fecha de México. Para fechas más antiguas se conservan resúmenes financieros y por producto y el conteo de modificaciones cuando está disponible; los motivos y valores de cada cambio requieren consultar el punto de venta local. No se elimina el historial completo del mostrador.

**Respaldos automáticos locales:** cada archivo se elimina individualmente al cumplir 30 días desde su creación, mediante la limpieza del programa. Con el equipo apagado la eliminación se hace al volver a abrirlo. La regla también afecta las copias automáticas anteriores que todavía existan: se conservan hasta cumplir 30 días. No recupera archivos que ya se borraron con el plazo anterior.

**Respaldos manuales:** siguen permitiendo elegir nombre y carpeta, y no se eliminan automáticamente. Los respaldos locales no se suben a Cloudflare. Conserva alguna copia en otra unidad para protegerte de una falla de disco.

Ampliar el plazo no recupera automáticamente detalles ya reducidos en la nube. Si el mostrador conserva el historial y una fecha vuelve a enviarse, se aplica el nuevo plazo. Los cambios de precio no registrados originalmente no pueden recuperarse mediante sincronización.

Se eligieron 30 días como margen inicial. Noventa días podrían caber, pero no se garantiza sin medir volumen de ventas, movimientos, tamaño por fecha y crecimiento real de la base. Los resúmenes también consumen espacio y siguen creciendo con el tiempo.

## Reposición

Se mantiene sin cambios. El punto de reorden determina cuándo aparece un producto. La sugerencia es existencia máxima menos existencia actual, no mínimo menos actual. Si quedan 3, el punto de reorden es 20 y el máximo es 40, la sugerencia es 37. No se envían pedidos al proveedor; las pestañas y Ver más son de consulta.

## Publicar para otro negocio

Utiliza el kit nuevo completo para crear una página nueva. Para una página existente, conserva su carpeta configurada y datos privados y actualiza worker.js, reporting.js, retention.js, public/index.html, public/style.css y agrega public/product-movements.js con las versiones del kit. Ejecuta Actualizar-pagina.cmd de esa carpeta; no uses Crear-pagina para actualizar. No compartas una carpeta ya configurada como paquete limpio.

## Validación

Pruebas realizadas: registro y sincronización de un día con solo ajuste sin ventas; motivo obligatorio y cambio atómico de precios; conservación de costos de ventas anteriores; huellas de sincronización coherentes; mezcla de sucursales sin duplicados; cortes de fecha para 30 días; respaldos locales y restauración; tarjetas de precios y motivos, información incompleta y fechas resumidas.

Quedan las pruebas con la computadora, impresora y pistola reales y una jornada de operación. Esta entrega no sustituye Qt WebEngine ni garantiza corregir toda la lentitud observada en un equipo antiguo.
