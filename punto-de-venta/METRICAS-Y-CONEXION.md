# Turnos, historial y métricas

## Turno obligatorio en el mostrador

Al iniciar sesión, una cuenta con permiso de vender debe seleccionar turno y fondo inicial antes de entrar. Si ya dejó un turno abierto, se recupera ese mismo turno, sin crear otro. Las cuentas dedicadas a consulta o administración sin permiso de vender no abren caja.

El botón Salir conduce al conteo si hay turno abierto. Cuenta el efectivo, declara y cierra el turno; después puedes salir. El servidor también rechaza cerrar sesión sin cerrar turno. Tras un corte se permite consultar reportes o salir; volver al mostrador exige abrir un turno nuevo.

El navegador puede mostrar una advertencia al cerrar la pestaña con turno abierto, pero ninguna página puede impedir apagar Windows, forzar el cierre del navegador o el vencimiento de una sesión. Eso no hace un corte automático: el turno sigue abierto en la base y se recupera al volver a entrar.

## Historial en ambos programas

Abre **Historial**, elige Desde y Hasta y pulsa Consultar. Usa la misma fecha para un día concreto; se aceptan hasta 366 días por consulta. En el mostrador requiere permiso de vender o de consultar reportes y muestra las ventas de toda la farmacia, como solicitaste. No muestra costos, clientes, recetas ni el efectivo esperado de caja.

Incluye totales diarios, productos y unidades, y movimientos con hora local, ticket original, devolución y partida. No duplica importes cuando un ticket tiene varios medios de pago o usa varios lotes.

Puedes descargar **resumen diario CSV** o **detalle CSV**, abiertos por Excel. Los importes están en pesos con dos decimales. Al importar el detalle en Excel, selecciona la columna Código como texto para conservar ceros iniciales. El resumen incluye fechas sin ventas; el detalle incluye todos los movimientos, aunque la pantalla los muestre en bloques de 100.

Las ventas permanecen en su fecha original; las devoluciones y anulaciones se descuentan en la fecha en que se registraron. El neto de un día puede ser negativo por devoluciones de tickets anteriores. El estado mostrado del ticket es el actual. Los datos de fecha usan la zona horaria de Windows del servidor.

## Métricas de Dirección

Selecciona **Métricas** y un periodo (por defecto 30 días). El botón Consultar actualiza el análisis; estos reportes son una consulta puntual. El resumen de Dirección e inventario sí se revisan automáticamente cada 10 segundos.

- Ventas registradas, devoluciones, ventas netas, unidades y tickets.
- Comparación del neto con el periodo inmediato anterior de igual duración. Solo se calcula porcentaje si la base anterior es positiva.
- Promedio de importe por ticket registrado (antes de descontar devoluciones posteriores).
- Gráfica y tabla diaria; fecha de mayor y menor venta neta. En empates se muestra una fecha y la tabla conserva todas.
- Promedio neto por lunes, martes, etcétera; incluye todas esas fechas del periodo, incluso sin ventas registradas.
- Productos más y menos vendidos por unidades netas; filtro independiente de productos sin ventas y búsqueda por nombre/código.
- Días estimados de existencia: stock vendible actual dividido entre promedio diario de unidades netas. Cuando el ritmo neto no es positivo no se inventa una duración.

## Cómo usar el análisis para comprar

Compara periodos de duración similar y revisa 30–90 días para reducir el efecto de un día aislado. Para decidir cuándo pedir, contrasta la cobertura estimada con los días que tarda tu proveedor, agregando un margen según la variabilidad observada. La reposición actual por máximos es una sugerencia, no un pedido automático.

Un producto sin ventas pudo estar agotado, haberse agregado recientemente o no tener demanda. La base no registra oportunidades de venta perdidas ni un calendario de apertura; por eso un día en cero significa **sin ventas registradas**, no necesariamente un día abierto. Un periodo que incluye hoy está incompleto. La cobertura usa stock actual, aunque consultes ventas históricas, y no es una predicción que ajuste temporadas o faltantes históricos. No se presentan rotación financiera, margen o sell-through como si existieran todos sus datos históricos.

La selección de medidas se apoyó en documentación primaria consultada el 6 de octubre de 2026:

- [Shopify: análisis de productos y días de inventario](https://help.shopify.com/en/manual/products/analytics): relaciona unidades existentes con velocidad diaria de ventas.
- [Odoo: reportes, medidas y agrupaciones](https://www.odoo.com/documentation/17.0/applications/essentials/reporting.html): agrupar por producto/fecha y comparar medidas.
- [Shopify: inventario y días agotados](https://shopify.dev/docs/api/shopifyql/latest/schemas/inventory/inventory): distingue existencias, ritmo de venta y periodos agotados. Estos últimos no se estiman a partir de ventas ausentes.

## Sincronización: estado real y siguiente paso

Hoy hay una sola base SQLite para el mostrador y Dirección. Una venta confirmada ya queda disponible para la siguiente consulta de Dirección; el resumen y el inventario se actualizan cada 10 segundos mientras la página está abierta y visible. No se trata de dos bases que necesiten intercambiar archivos. Historial y Métricas se actualizan pulsando Consultar.

El acceso desde casa/oficina aún no está configurado: el servidor solo atiende en la computadora local. Para esa etapa propongo una conexión privada con HTTPS entre la computadora de la farmacia y los dispositivos autorizados de la administradora. Por ejemplo, [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve) permite acceder a un servicio local desde dispositivos de una red privada; su configuración NO está incluida ni instalada en esta entrega.

Habría que configurar esa red, autorizar únicamente sus dispositivos, adaptar y probar el acceso de Dirección con el nombre HTTPS y las validaciones de origen/sesión, y dejar el equipo de farmacia encendido, con Internet y el programa funcionando. No basta con compartir el enlace 127.0.0.1. El historial remoto debe probarse también al perder conexión y al restablecerla.

Si se necesita consultar aunque la computadora esté apagada, se requiere otra arquitectura: servidor central o copia sincronizada en la nube, con cola de operaciones y recuperación tras desconexiones. Eso implica alojamiento, respaldo y pruebas de sincronización adicionales.

Para ver cambios casi instantáneos en vez de revisiones cada 10 segundos se puede añadir un canal de eventos. Las notificaciones con la página cerrada requieren además un servicio de notificaciones y permiso del teléfono. Ninguna de estas conexiones externas se ha habilitado todavía.
