# Clientes a crédito y cambios de mostrador

## Uso
1. Reinicia el programa con Iniciar.cmd y actualiza la página del navegador.
2. En Menú → Clientes a crédito, registra el nombre y teléfono opcional del cliente.
3. En Mostrador agrega los medicamentos. En Cobrar pulsa Crédito, selecciona Cliente de la cuenta y confirma. También puedes seleccionar al cliente previamente en Mostrador. Se descuenta inventario y se suma el importe a su deuda.
4. En Clientes a crédito abre Ver cuenta / abonar. Registrar abono permite ingresar una cantidad en efectivo, tarjeta o transferencia. Debe haber un turno abierto. El abono reduce la deuda total, sin repartirlo por medicamento.
5. Puedes fiar nuevas compras aunque exista deuda pendiente. El historial conserva medicamentos, cantidades, cargos y abonos.

Ejemplo: $700 de medicamentos − $250 de abono + $200 de una nueva compra = $650 pendientes.

## Otros cambios
- Cobro: selecciona Efectivo, Tarjeta o Transferencia y captura un solo importe; el botón elegido queda sombreado. Crédito permite elegir el cliente y registrar la deuda sin recibir dinero. Los enteros se aceptan; un campo vacío equivale a cero. Solo efectivo entrega cambio; tarjeta y transferencia deben coincidir con el total.
- Configuración: vista previa de un ticket de ejemplo, logotipo PNG y mensaje personalizado. El logotipo también aparece en los tickets impresos.
- Dirección → Inventario → Todo: precio de venta y último costo de compra registrado por producto, visible con permiso de costos. No representa un costo promedio de todos los lotes.
- Favicon de farmacia en ambas páginas.

## Caja y datos
Las compras a crédito registran la entrega y el adeudo, pero no aumentan el total cobrado ni la ganancia cobrada hasta recibir abonos. Los abonos se incluyen en el cobro y la ganancia del día de pago; únicamente los de efectivo aumentan lo esperado en caja. No vuelven a sumar unidades ni crean otro ticket de compra. Consulta COBROS-Y-GANANCIA.md.

Para consultar la cartera y fiar se requiere Administrar clientes; para abonar también Realizar ventas. Los respaldos completos incluyen la cartera. Al iniciar se actualiza el esquema y se genera una copia SQLite previa a la migración, conservando los registros existentes.

Limitación: no se admiten devoluciones ni anulaciones de tickets fiados en esta versión; requieren un flujo que concilie la deuda con los abonos ya realizados. No se pueden capturar deudas antiguas sin registrar los medicamentos como una venta.

La verificación usa bases ficticias separadas, sin modificar la base operativa.

## Abonos en efectivo y ventanas
Si recibes más efectivo que la deuda pendiente, se aplica únicamente el saldo y se muestra el cambio. Ejemplo: deuda $257, recibido $260, aplicado $257 y cambio $3. Tarjeta y transferencia no permiten exceder la deuda. La cartera inicia con nombres y controles; Ver cuenta / abonar despliega una sola cuenta. Los encabezados de las ventanas permanecen visibles al desplazar, y pulsar fuera permite cerrar cuando no hay una operación guardándose.
