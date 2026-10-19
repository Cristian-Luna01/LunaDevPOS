# Historial de versiones

## Cambios preparados — 2026-10-18

- Al confirmar una venta, el cliente vuelve a Público general para impedir que la siguiente compra herede descuentos. Si el cobro falla, se conserva el cliente para reintentar.

- Historial de tickets del mostrador, junto al turno, con fechas y detalle de la compra original.
- Consulta paginada y permisos coherentes con la consulta de tickets existente.
- Botón para limpiar el buscador; limpieza al enfocarlo y después de cobrar.
- Corrección de códigos concatenados cuando se escanea sobre una búsqueda previa.
- Pruebas de fechas, pagos, créditos, total cero, anulaciones y lecturas consecutivas.

## 0.1.0-beta — 2026-10-18

Primera versión registrada en este repositorio; agrupa el desarrollo previo sin atribuirle un historial de commits inexistente.

- Aplicación de escritorio, ventas, caja, inventario y gestión de clientes/créditos.
- Panel central de consulta para una o varias sucursales.
- Valor del inventario a costo de cada lote en mostrador y administrador.
- Respaldos automáticos con conservación de 30 días; respaldos manuales independientes.
- Auditoría de modificaciones de existencias y precios.
- Exportaciones del historial y actualización del panel conservando la posición.
- Empaquetado Windows x64 y asistente de publicación separados del código.

Validación local de referencia: 201 pruebas Python y 22 de interfaz/servicio central aprobadas. Facturación únicamente en pruebas; revisar límites en README antes del piloto.
