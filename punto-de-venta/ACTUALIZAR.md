# Actualización del mostrador y Dirección

1. En tu versión actual, entra a Administración → Respaldar todo y guarda el archivo fuera de la carpeta del programa.
2. Termina la venta que tengas en pantalla y cierra Botica. Detén su ventana de comandos con Ctrl+C.
3. Descomprime el ZIP nuevo. Copia el contenido de su carpeta `farmacia-pos` dentro de la carpeta de tu programa actual y acepta reemplazar los archivos del programa. No borres ni reemplaces la carpeta `data`: ahí está tu información.
4. Abre `Iniciar.cmd` desde esa misma carpeta. Si te pide crear un administrador nuevo, estás abriendo una carpeta sin tu base: detén el inicio y revisa la ubicación de `data`.
5. Actualiza la pestaña del navegador con Ctrl+F5.

## Cambios

- Promociones permanentes, temporales o recurrentes por días; paquetes del mismo producto como 2 por $15. Las promociones existentes se conservan.

- Historial y cortes muestran ganancia de productos y costo histórico, sujetos al permiso de costos. Consulta [GANANCIA-Y-PROMOCIONES.md](GANANCIA-Y-PROMOCIONES.md).
- El catálogo empieza vacío hasta buscar. Cada tarjeta separa disponibles y unidades en carrito; consulta cambios externos de existencias cada cinco segundos.
- Promociones permite crear, editar y desactivar precios por producto con vigencia, aplicados al cobrar sin acumular descuentos.

- El mostrador exige abrir turno después del login para cuentas de venta. Si ya hay un turno abierto, lo recupera. Salir exige primero contar el efectivo y cerrar el turno.
- Ambos programas incluyen Historial por fecha, con detalle de productos, tickets, devoluciones y exportación CSV de resumen y detalle.
- Dirección añade Métricas por periodo, comparación, productos más/menos vendidos y cobertura estimada. Consulta [METRICAS-Y-CONEXION.md](METRICAS-Y-CONEXION.md) para las definiciones y el estado de la conexión remota.

- Las cantidades del carrito no pueden superar la existencia disponible conocida: se limita la captura y las adiciones repetidas. Antes de abrir el cobro se consulta de nuevo el inventario; si cambió, se ajusta el carrito y se pide revisar. La confirmación mantiene la comprobación transaccional contra ventas simultáneas.
- Búsqueda, total y botón Cobrar permanecen visibles. Catálogo y carrito se desplazan por separado. Se retiró el encabezado grande del mostrador.
- El turno aparece junto al usuario. Al abrirlo se elige Turno 1 o Turno 2. Ambos corresponden a CAJA-1; cambiar de turno exige cerrar el anterior. El número consecutivo del corte sigue siendo un identificador histórico independiente.
- Las tablas muestran los importes en pesos con dos decimales, por ejemplo $160.00. El almacenamiento interno sigue usando centavos para evitar errores de redondeo.
- El programa de la farmacia conserva la pestaña Inventario para los trabajadores, sin datos financieros. Dirección tiene entrada independiente con ventas de hoy, cortes, diferencias de caja, inventario y reposición con proveedores. Se abre con `Abrir Direccion.cmd` después de iniciar Botica. Consulta [DIRECCION.md](DIRECCION.md).
- El panel se adapta a teléfono, pero esta entrega sigue atendiendo solo conexiones locales. Aún no incluye acceso desde el teléfono, sincronización por Internet ni notificaciones con la aplicación cerrada. La conexión remota se debe configurar según si se usará en la misma red o desde fuera.

Los respaldos anteriores siguen siendo compatibles. La base se actualiza automáticamente a versión 5 para promociones, creando antes una copia de seguridad local.


Dirección muestra venta y ganancia del día; el logotipo PNG compartido se incluye en el respaldo completo. Consulta LOGOTIPO-E-INSTALACION.md.

La versión actual migra a esquema 6. Menú reúne las secciones y Configuración permite editar nombre, mensaje del ticket y logotipo. Consulta CONFIGURACION.md.

Ajuste visual: el navbar ya no repite la sección activa. Mostrador aparece dentro del catálogo, encima de Buscar producto. El mensaje de catálogo vacío queda centrado. Verificado en teléfono y laptop, conservando Cobrar visible.
