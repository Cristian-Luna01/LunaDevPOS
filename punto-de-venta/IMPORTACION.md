# Importar, exportar y recuperar tus datos

## Actualizar la copia que ya usas

1. Termina cualquier operación en pantalla y detén Botica con **Ctrl+C** en su ventana de comandos. Cierra las otras copias que hayas abierto.
2. Conserva una copia de tu carpeta actual como respaldo.
3. Descomprime el nuevo ZIP aparte. Copia el contenido de la nueva carpeta `farmacia-pos` sobre la carpeta anterior y acepta reemplazar los archivos del programa.
4. **No borres la carpeta `data`**: contiene tu información. El ZIP no contiene una carpeta `data`, por lo que no sustituye esa base.
5. Haz doble clic en `Iniciar.cmd` y abre la dirección que indique. Recarga la página si estaba abierta; entra de nuevo con tu usuario.

Al abrir una base anterior, el sistema permite caducidades opcionales mediante una migración que conserva los registros. Antes crea una copia SQLite en `data` con el sufijo `.antes-v2-…sqlite3`. Los permisos nuevos se conceden al rol Administrador. No vuelvas a iniciar la versión antigua sobre la base actualizada.

## Cargar el archivo del sistema anterior

En **Administración → Importar inventario**:

1. Elige `Inventario 16 agosto 2026.xls`, un CSV compatible o un inventario Botica JSON.
2. Para tu archivo anterior, deja **Solo con existencia mayor que cero**. También puedes incluir existencias cero. Los registros `N/A` o sin dato se omiten: no se convierten en cero ni se les inventa una cantidad.
3. Deja **Omitirlo: conservar lo que ya tengo** para códigos existentes. La alternativa sustituye datos y cantidades de los productos seleccionados y requiere turnos cerrados. Nunca suma de nuevo las cantidades por repetir el archivo; los productos ausentes del archivo permanecen intactos.
4. Revisa la tasa de IVA que se aplicará al archivo anterior, que no trae impuestos. La selección inicial es 0%; luego puedes ajustarla por producto. En el formato Botica se conservan los impuestos originales.
5. Pulsa **Revisar archivo**. Revisa el resumen, busca nombres o códigos y desmarca los productos que no venderás. La lista muestra 100 productos por página y mantiene tu selección al buscar o cambiar de página.
6. Pulsa **Confirmar importación**. Si hay filas inválidas, puedes corregir el archivo o marcar expresamente que se omitan. Los precios cero del archivo anterior están desmarcados inicialmente; puedes seleccionarlos si es intencional. El inventario Botica conserva su selección, incluidos precios cero.

El archivo anterior fue probado en una base separada: 6,137 filas; 1,100 productos con existencia positiva, 7,565 unidades, 832 filas con cero y 4,205 con `N/A`. Son cantidades de ese archivo, no un conteo actual de la farmacia. El programa no adivina si un artículo es alimento: usa la búsqueda y las casillas para excluir lo que no vendas.

### Columnas de la tabla anterior

`Codigo`, `Descripcion`, `Precio Costo`, `Precio Venta`, `Precio Mayoreo`, `Inventario`, `Inv. Minimo`, `Departamento`.

El `.xls` proporcionado es una tabla de texto separada por tabulaciones en Windows-1252. Se admite directamente. También se admite CSV con coma o punto y coma como separador y texto UTF-8 o Windows-1252; los valores numéricos usan punto decimal, como el archivo original. Códigos y nombres se mantienen como texto, incluidos ceros iniciales. No se ejecutan fórmulas del archivo.

Los libros Excel binarios `.xls` y los `.xlsx` no se importan directamente: deben guardarse como CSV. La importación permite hasta 50,000 registros y archivos de hasta 64 MB. Mayoreo no se activa como una lista de precios; el catálogo del sistema actual tiene un precio de venta. El archivo anterior no contiene proveedor, sustancia, impuestos, receta ni máximos. Para registros nuevos, sustancia queda vacía, receta desactivada, máximo al menos 100 o el mínimo si lo supera y punto de reorden igual al mínimo. Revisa esos campos donde corresponda antes de operar.

## Caducidad y lote opcionales

Puedes recibir mercancía sin capturar proveedor, lote o fecha. Se registra como **SIN LOTE CAPTURADO** y la fecha permanece vacía; no se inventa una caducidad.

Los lotes sin fecha se pueden vender. Si un producto tiene lotes con fecha y sin fecha, se consumen primero los lotes vigentes con fecha más cercana, y después los que no tienen fecha, por orden de recepción. Los lotes con fecha vencida o que vencen hoy siguen excluidos de venta.

En Administración, **Sin caducidad capturada** permite consultar hasta 200 lotes con existencias sin fecha. **Completar lote / caducidad** permite registrar el dato después, con motivo y auditoría. **Consultar kardex y lotes** permite ver los lotes de un producto concreto. Sin fecha no es posible emitir una alerta de vencimiento para ese lote.

## Exportar solo inventario

En **Administración → Exportar inventario** elige:

| Formato | Qué conserva |
|---|---|
| Inventario Botica JSON | Todos los productos, activos e inactivos, precios, impuestos, mínimos/máximos, receta, lotes, fechas, costos de lote, nombre del proveedor, fechas de recepción y existencias |
| CSV | Productos activos y las ocho columnas de la tabla anterior; existencias físicas sumadas por producto |
| XLS de texto | La misma tabla agregada, separada por tabulaciones y con extensión `.xls`, como el archivo anterior |

CSV y XLS no conservan lotes, fechas, IVA, historial ni productos inactivos. Agrupan incluso existencias de lotes caducados como existencia física. Por ello **no los uses para una recuperación exacta** si ya capturaste caducidades. Excel puede advertir que el `.xls` de texto no coincide con su extensión; eso describe el formato de texto, no un libro Excel binario.

El inventario Botica JSON es la opción para trasladar solo inventario conservando los detalles. Al seleccionarlo, el formulario incluye también existencias cero. Importarlo no recupera ventas, usuarios ni datos de contacto del proveedor; para eso utiliza respaldo completo.

## Antes de formatear: respaldar todo

1. Termina la jornada y cierra el turno si ya terminó. Haz la copia después de tu última operación para no dejar ventas posteriores fuera del respaldo.
2. Ve a **Administración → Respaldar todo**.
3. Se descargará `respaldo-fecha-hora.botica.json`. El navegador lo guarda en Descargas o pregunta dónde guardarlo, según su configuración.
4. **Cópialo a la USB y comprueba que el archivo está allí antes de borrar la computadora.** Guarda también el ZIP del programa. Conviene conservar otra copia de ambos.

El respaldo completo contiene productos, proveedores, clientes, lotes, inventario, usuarios con hashes de contraseña, permisos, ventas, pagos, devoluciones, turnos, movimientos y auditoría. Se genera desde una sola lectura consistente. No contiene las sesiones abiertas ni los intentos fallidos de acceso; tendrás que iniciar sesión al restaurar. El archivo completo no está cifrado, por lo que la USB debe quedar bajo tu control.

La suma de verificación detecta archivos alterados o incompletos, pero no verifica que la USB funcione ni sustituye una prueba de recuperación. Puedes probar el archivo en una copia vacía separada de Botica antes del mantenimiento.

## Después del mantenimiento: restaurar todo

1. Descomprime el programa en la computadora y ejecuta `Iniciar.cmd`. El equipo necesita Python 3.11 o superior; el ZIP actual no es un instalador autónomo de Python.
2. Crea la cuenta temporal que pide el primer inicio y entra. **No agregues productos ni abras un turno** en esa base.
3. Ve a **Administración → Restaurar respaldo** y selecciona el archivo `.botica.json` de la USB.
4. Pulsa **Revisar respaldo**, comprueba las cantidades, escribe **RESTAURAR** y confirma.
5. El programa vuelve a la pantalla de acceso. Entra con el usuario y contraseña que usabas al crear el respaldo, porque reemplazan la cuenta temporal.

La restauración solo está permitida sobre una instalación vacía, sin productos, proveedores, clientes ni turnos. Si ya tiene datos, usa otra carpeta vacía en lugar de borrarlos. No hay mezcla silenciosa de ventas o usuarios. Un error revierte la restauración completa; las sesiones anteriores dejan de funcionar después de confirmar.

Se admiten respaldos de formato Botica versiones 2, 3, 4 y 5 y hasta 64 MB. Los nuevos respaldos completos incluyen promociones (versión 5). Para bases que superen ese tamaño, usa la copia SQLite consistente disponible en `app.py backup` y la recuperación documentada en README; el asistente JSON no admite archivos mayores.

## Alcance pendiente

Ya están implementadas importación, exportación, respaldo, restauración y caducidad opcional. El instalador autónomo de Windows, actualizador automático, panel remoto para la administradora y notificaciones sincronizadas todavía no forman parte de esta versión.

