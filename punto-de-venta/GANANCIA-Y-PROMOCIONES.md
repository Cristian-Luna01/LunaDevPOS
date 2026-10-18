# Ganancia, carrito y promociones

## Venta total y ganancia de productos

Historial y Métricas destacan dos importes: **Venta total de productos**, lo vendido después de descuentos, devoluciones y anulaciones del periodo, y **Ganancia de productos**, esa venta total menos el costo de compra de lo vendido. La ganancia requiere el permiso **Ver costos y márgenes**. Caja y corte y los CSV usan el mismo cálculo; Dirección lo muestra también por corte.

Ejemplos: comprar en $200 y vender en $300 da $300 de venta total y $100 de ganancia. Comprar en $10 y vender en $20 da $20 de venta total y $10 de ganancia. Si ambas ventas ocurren el mismo día, se muestran $320 de venta total, $210 de costo y $110 de ganancia.

El costo de compra no es ganancia: es lo que costaron los productos vendidos. Se toma del costo histórico guardado con cada venta, aunque después cambie el catálogo. Los costos cero se advierten para revisarlos.

Este indicador compara los importes registrados de venta y compra. No resta renta, sueldos, comisiones, movimientos de caja ni IVA por separado. No calcula utilidad contable ni impuestos a pagar. Los impuestos del ticket se conservan y se exportan como información independiente. Antes de esta actualización, el indicador restaba el IVA de venta; ahora las consultas históricas también usan venta menos costo.

Como detalle se conservan ventas antes de devoluciones, devoluciones, costo y tickets. Si no hay devoluciones, la venta antes de devoluciones y la venta total son iguales. Las devoluciones se contabilizan en su propia fecha; el costo se revierte si la mercancía regresa al inventario vendible. Si va a cuarentena, se conserva el costo de la mercancía no recuperada.

## Existencias en el mostrador

El catálogo comienza vacío: escribe un nombre o escanea un código. Las tarjetas muestran las unidades disponibles para agregar y las que están en **este carrito**. Con tres en inventario y una en el carrito verás «2 disponibles · 1 en carrito». Al quitarla vuelve a mostrar tres disponibles.

Agregar al carrito no descuenta ni reserva inventario para otras computadoras; el descuento real ocurre al confirmar la venta. La tarjeta se actualiza inmediatamente al editar este carrito y consulta cambios de existencias cada cinco segundos mientras el mostrador está abierto y visible. La venta vuelve a comprobar existencias y precios antes de cobrar y el servidor valida todo al confirmar.

Los productos agotados siguen apareciendo si coinciden con una búsqueda. No se elimina su ficha. La pantalla vacía evita cargar todos los medicamentos de entrada.

## Promociones

Abre **Promociones → Crear promoción**. Captura nombre y código exacto del producto. Se requiere permiso de editar productos.

- **Permanente:** sin fechas, hasta desactivarla.
- **Temporal:** fecha inicial y final obligatorias, ambas incluidas.
- **Recurrente:** selecciona uno o varios días de la semana. Las fechas inicial y final son opcionales. Usa el calendario local de la computadora de la farmacia.

Configura las **unidades por paquete** y el **precio TOTAL del paquete**. Usa 1 para un precio individual. Por ejemplo, si cada unidad cuesta $10 y configuras 2 por $15: una cuesta $10, dos $15, tres $25, cuatro $30. Para un 2×1 real configura 2 unidades por $10. El nombre de la promoción es descriptivo; el cobro depende de cantidad y precio configurados.

Los paquetes son del mismo producto/código, se repiten por cada grupo completo y dejan las unidades sobrantes a precio normal. No son una rebaja para todas las unidades al superar un mínimo ni combinan productos diferentes. Se mantiene una promoción por producto: editar sustituye la configuración y queda en auditoría.

No se acumula con el descuento del cliente: se cobra el menor total entre la oferta y el descuento. El servidor vuelve a verificar vigencia, precio y stock al confirmar. Las devoluciones usan el importe registrado en el ticket original. Las promociones anteriores conservan sus fechas y precio individual al actualizar.

## Actualización y respaldo

La base se actualiza automáticamente a versión 5, con copia de seguridad previa. Conserva la carpeta `data` al actualizar. El respaldo completo versión 5 incluye días, tipo y cantidad de las promociones; se pueden restaurar respaldos anteriores 2 y 3. Para restaurar respaldos nuevos utiliza esta versión o una posterior. Exportar solamente el inventario no incluye promociones.

