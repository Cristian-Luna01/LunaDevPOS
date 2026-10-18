# Cobros y ganancia de productos

Los reportes ahora reconocen las compras a crédito el día que se recibe el abono, no cuando se entrega el medicamento.

| Ejemplo | Total cobrado | Costo correspondiente | Ganancia cobrada |
|---|---:|---:|---:|
| Día 1: una venta de $10 pagada y otra de $10 a crédito | $10 | $5 | $5 |
| Día 2: otra venta de $10 pagada y el pago de $10 de Liliana | $20 | $10 | $10 |

La compra a crédito sí registra los medicamentos entregados, descuenta inventario y aumenta la deuda. Sus unidades y ticket permanecen en el historial; su importe cobrado es cero hasta recibir abonos.

Los abonos se aplican automáticamente a las compras y partidas más antiguas. Cada abono reconoce el costo histórico y la ganancia correspondientes a la parte cobrada. Los redondeos acumulados conservan los centavos y, al pagar todo, se reconoce exactamente el costo completo y la ganancia completa. El abono no vuelve a sumar unidades entregadas ni crea una venta nueva.

Total cobrado incluye efectivo, tarjeta y transferencia. El corte físico compara solamente efectivo: fondo + ventas en efectivo + abonos aplicados en efectivo − devoluciones en efectivo + entradas − salidas. El dinero devuelto como cambio no aumenta caja.

Ganancia cobrada corresponde a productos, antes de gastos operativos del negocio. No es utilidad neta después de renta, sueldos u otros gastos.

La configuración aplica a Dirección, historial, métricas, CSV y consultas de cortes. Los registros originales, saldos y cortes guardados no se borran: las vistas se calculan con este criterio de cobros y mantienen el efectivo contado/esperado de los cortes cerrados.

Para cargar el cambio, completa tu corte actual, reinicia el programa y actualiza el navegador con Ctrl + F5.
