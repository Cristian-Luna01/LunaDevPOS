# Verificación de 0.2.0-rc.1

Fecha: 21 de octubre de 2026. Comparación con la rama de respaldo `respaldo/antes-correcciones-2026-10-21`.

## Cambios comprobados

| Riesgo revisado | Corrección y evidencia |
| --- | --- |
| Vendedor accediendo al historial completo | JSON, CSV y Excel requieren `reports.view`; se comprueba rechazo 403 y consulta separada de tickets propios. |
| Cliente HTTP lento bloqueando otras operaciones | El cuerpo y la respuesta se transfieren fuera del bloqueo; una segunda consulta responde mientras la primera envía un cuerpo incompleto. Hay tiempos y tamaños máximos. |
| Respuesta perdida duplicando una operación | Venta, entrada/salida y recepción conservan clave y resultado. Un diario en SQLite sobrevive al cierre del navegador; reintento usa el mismo cuerpo y cancelación bloquea una ejecución tardía. |
| Corte cerrado cambiando por editar catálogos | Se utiliza el informe guardado al cierre; se comprueba que cambiar nombres posteriores no modifica el corte y que se respetan permisos de costos. |
| Envío grande rechazado o parcial | Transferencia reanudable, comprobación de integridad y documentos fragmentados. La copia anterior sigue visible hasta completar el envío. Se prueban más de 2 MB y 7,000 productos, corrupción y separación entre sucursales. |
| Único respaldo en el disco del equipo | Destino adicional configurable, escritura atómica y verificación; se advierte si falta el destino y se conserva la copia local. Se prueba restaurar datos, claves de reintento y operaciones pendientes. |
| Consultas y distribución difíciles de reproducir | Rangos UTC indexables conservan el día local; dependencias fijadas, receta única de compilación y flujo de pruebas en GitHub. |

## Resultados locales

- 223 pruebas Python aprobadas: punto de venta, permisos, matemáticas, importación/restauración, cierres, red y migraciones.
- 16 pruebas de interfaz aprobadas, incluyendo 3,000 combinaciones de descuento/promoción, limpieza del cliente, lector y recuperación.
- 16 pruebas del panel central aprobadas: múltiples locales, métricas, exportaciones, retención y transferencia fragmentada.
- Comprobación HTTP y navegador aislada: se interrumpió deliberadamente la respuesta después de guardar una venta. Al reabrir se recuperó la operación; la base conservó exactamente una venta y una partida, con la comprobación reconocida.
- Comprobación del ejecutable: motor Qt WebEngine y autoprueba con base nueva aprobados fuera del aislamiento de red. Se corrigió la inclusión de un recurso público de certificados requerido por el runtime de compilación. La instalación se comprueba en una carpeta temporal, conservando intacta la instalación del negocio.

Los conteos describen casos automatizados, no un porcentaje de fiabilidad estadística. No equivalen a una garantía de ausencia de errores.

## Límites y puesta en servicio

Actualizar primero el panel y después el punto de venta, siguiendo GUIA-ACTUALIZACION-0.2.md. Se conserva un respaldo previo a la migración al esquema 11; volver a la versión anterior requiere restaurar ese respaldo.

El transporte admite hasta 16 MB por documento y sigue sujeto a las cuotas del proveedor. Las pruebas del panel usan su entorno local de pruebas; verificar también recepción y fecha de actualización en la cuenta real después de publicar. Los respaldos externos no sustituyen una política de resguardo: otra carpeta del mismo disco no protege frente a la avería de ese disco. Las copias manuales no se eliminan por la retención automática de 30 días.

Queda la validación operativa con caja física, impresora, lector y computadora del establecimiento. La facturación continúa en entorno de pruebas; no se ha validado emisión real con PAC ni credenciales fiscales. El instalador es Windows x64; no se incluye versión x86. No se modificó la instalación ni la base de datos del negocio para realizar estas pruebas.
