# Historial de tickets y búsqueda del mostrador

- El botón **Historial de tickets**, a la izquierda del turno, abre las ventas de hoy.
- Usa **Desde** y **Hasta** para consultar otro día o un intervalo de hasta 366 días.
- Los más recientes aparecen primero. **Ver más tickets** permite continuar la lista sin cargarla completa.
- Selecciona un ticket para ver productos y cantidades, fecha y hora, vendedor, cliente si se registró, descuentos, total, pago recibido y cambio.
- Los tickets a crédito, de total cero, devueltos y anulados se conservan. Los abonos posteriores no se confunden con compras nuevas.
- La consulta respeta los permisos existentes: el vendedor consulta sus tickets; los permisos de informes/devoluciones permiten consultar los demás.
- El botón × del buscador lo vacía. También se limpia al enfocarlo y después de confirmar una venta.
- Las lecturas rápidas del escáner terminadas en Enter no se mezclan con texto previo. No se capturan otros campos, diálogos ni secciones.

## Instalar esta actualización

Termina el turno, exporta un respaldo completo fuera de la computadora y cierra LunaDev POS. Ejecuta **Instalar-LunaDevPOS-Tickets.exe**. La actualización conserva los datos existentes.

Solo cambia el mostrador y sus consultas locales. No hace falta volver a publicar la página del administrador.

Validación: 207 pruebas Python y 22 pruebas JavaScript aprobadas. Se comprobó visualmente una venta de tres unidades, el pago con cambio, la limpieza del buscador, la consulta del ticket y un día sin tickets. Los escáneres físicos siguen requiriendo el piloto en el equipo real.

Después de guardar una venta, el cliente vuelve automáticamente a Público general y se vacía su búsqueda. Si el guardado falla, se conserva el cliente para reintentar. Se verificó que una segunda compra no herede el descuento anterior.
