# Panel exclusivo de Dirección

El mostrador y Dirección tienen páginas e inicios de sesión separados. El panel de Dirección no aparece en la navegación de los cajeros.

El programa de la farmacia conserva la pestaña **Inventario** para cualquier trabajador autenticado: permite consultar existencias, agotados y existencia baja, sin mostrar costos ni reportes financieros.

## Cómo entrar

1. Actualiza los archivos del programa conservando `data`, como explica ACTUALIZAR.md.
2. Abre `Iniciar.cmd` y deja el programa funcionando.
3. Haz doble clic en `Abrir Direccion.cmd`. Abre la dirección del panel de esa instalación. También puedes añadir `/direccion/` al final de la dirección de Botica, por ejemplo `http://127.0.0.1:8765/direccion/`.
4. Inicia sesión con la cuenta de la administradora. La cuenta inicial `admin` tiene acceso. Las cuentas autorizadas deben tener los permisos **Administrar usuarios** y **Ver corte X y reportes financieros**; se comprueban en cada consulta, no solo al iniciar sesión.

Cada empleado debe usar su propia cuenta de mostrador, sin esos permisos de administración. No compartas la contraseña de la administradora. Tener abierta la sesión del mostrador no inicia sesión en Dirección. Salir de Dirección no cierra el turno del mostrador.

## Qué muestra

Dirección tiene cinco secciones: **Ventas y caja**, **Inventario**, **Historial**, **Métricas** y **Reposición**. No incluye mostrador, reimpresión ni controles para abrir/cerrar turnos o registrar movimientos de efectivo. Consulta [METRICAS-Y-CONEXION.md](METRICAS-Y-CONEXION.md) para el historial, la investigación de indicadores y los requisitos de conexión remota.

- Caja: turnos abiertos y cortes cerrados hoy, con ventas netas del turno, efectivo esperado, contado y diferencia. Los faltantes y sobrantes se suman por separado, solo para cortes cerrados; los abiertos quedan pendientes. Un turno puede contener ventas de más de un día, por lo que no equivale al total de ventas de hoy.
- Reposición: productos en el punto de reorden o agotados, cantidad sugerida para completar su existencia máxima y contactos de proveedores. Es una herramienta de consulta para preparar compras, no envía pedidos ni modifica existencias. Revisa los máximos configurados antes de usar las sugerencias.

- Ventas registradas hoy, devoluciones/anulaciones de hoy y ventas netas hasta el momento, en pesos mexicanos con dos decimales.
- Cantidad de tickets registrados hoy (incluye tickets que después se anularon; sus importes se descuentan mediante las devoluciones).
- Productos agotados, productos con existencia baja y todo el inventario. La existencia baja corresponde al punto de reorden de cada producto. Si el punto es cero, solo avisa al agotarse: ajústalo en Editar producto para anticipar compras.
- Búsqueda por nombre o código, resultados paginados y avisos dentro del panel cuando un producto pasa a existencia baja o se agota.

La consulta se actualiza cada 10 segundos mientras el panel permanece abierto y visible. Si falla la conexión, identifica los datos como desactualizados. Las cantidades excluyen lotes caducados y productos dados de baja.

El día sigue la fecha y zona horaria de Windows de la computadora de la farmacia. Se descuentan las devoluciones registradas hoy aunque sean de tickets anteriores; por ello el neto del día puede ser negativo.

## Acceso desde otro dispositivo

Esta entrega es software local que utiliza el navegador como interfaz. Dirección es una página independiente del mostrador, pero comparte su base de datos para consultar las mismas ventas y existencias.

La administradora necesita consultar desde casa u oficina. Todavía no se ha publicado un sitio externo ni se ha habilitado conexión desde el teléfono: esta entrega escucha únicamente en la computadora donde se ejecuta. El acceso remoto sigue pendiente de configurar. No incluye avisos del sistema con el panel cerrado.
