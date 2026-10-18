# Verificación de la entrega

Fecha: 6 de octubre de 2026.

Actualización de cobro: el cambio se muestra en vivo a la derecha del título de la ventana, antes de confirmar. Se verificaron en navegador efectivo, pago mixto y efectivo insuficiente sin registrar nuevas ventas. Ejemplo mixto: total $22, parte en efectivo $10, recibido $20, transferencia $12 y cambio $10. Con recibido $5 se muestra el faltante y no un cambio válido. Sintaxis JavaScript verificada.

- 11 pruebas automatizadas satisfactorias con Python y SQLite en Windows.
- Sintaxis de JavaScript comprobada con `node --check`.
- Prueba en navegador con datos ficticios: acceso, apertura de turno, venta mixta, actualización de stock, cálculo de cambio y corte Z.
- Ejemplo comprobado: fondo $500; venta $22 con $10 aplicados en efectivo y $12 por transferencia; $20 recibidos y $10 de cambio; corte esperado y contado $510; diferencia $0.
- Pantalla del mostrador revisada en vista de escritorio de 1280 × 900 y adaptación estrecha. Sin errores de consola en la revisión.

La suite verifica también reversión completa ante un fallo inyectado después del descuento de stock, competencia entre dos ventas, idempotencia, devoluciones en otro turno, cuarentena, corte congelado, ocultación de costos, consolidación por turnos, margen unitario y denegación de corte X a un cajero sin permiso.

No se verificaron impresora térmica o escáner físicos, integración bancaria/fiscal, recuperación ante corte eléctrico real, carga sostenida o rendimiento en un equipo con 4 GB de RAM. Las pruebas usan archivos temporales, no datos comerciales reales.


## Actualización: importación y mantenimiento

- 22 pruebas automatizadas aprobadas: se agregaron importación, claves repetidas, filtros, exclusión de filas inválidas, archivo corrupto, rollback de restauración, recuperación de ventas/turnos/usuarios, permisos, migración y caducidad opcional.
- Archivo real probado en bases aisladas: 6,137 filas, 1,100 productos con existencia positiva y 7,565 unidades importadas. Exportación JSON y reimportación comparadas con igualdad exacta del inventario.
- Navegador: selección del XLS original, vista previa y confirmación en base de prueba; descarga de respaldo completo; revisión y restauración de ese archivo en otra base vacía; acceso posterior y productos visibles.
- El archivo original y la instalación que usa el usuario no se modificaron durante estas pruebas. No se realizó un formateo físico ni una prueba sobre memoria USB.
