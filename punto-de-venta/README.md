# Botica · Base técnica de POS e inventario

Aplicación local ejecutable para una farmacia comunitaria: **Python 3.11 o superior + SQLite WAL + HTML/CSS/JavaScript sin frameworks**. No requiere paquetes de pip, compilación de frontend, servicios externos ni conexión a Internet para operar. Esta entrega es un código base funcional, con reglas transaccionales verificadas; requiere una validación operativa en el establecimiento antes de usar datos reales.

## Inicio rápido

Si ya tienes una versión en uso, sigue [ACTUALIZAR.md](ACTUALIZAR.md) para conservar tus datos y aplicar los cambios del mostrador.

El panel exclusivo de la administradora se abre con **Abrir Direccion.cmd** una vez iniciado el programa. Tiene su propio acceso, resumen de ventas del día y faltantes. Consulta [DIRECCION.md](DIRECCION.md) para permisos y límites del acceso remoto.

En Windows, abre la carpeta descomprimida y haz doble clic en **Iniciar.cmd** (puede aparecer simplemente como **Iniciar** si Windows oculta las extensiones).

El inicio localiza Python, pide crear y repetir la contraseña del administrador la primera vez y abre el navegador automáticamente. Deja la ventana de comandos abierta mientras trabajas. Si ocurre un error, queda visible hasta que pulses una tecla. No requiere ejecutar archivos PowerShell ni cambiar su política de ejecución.

El puerto habitual es 8765; si está ocupado, busca uno libre hasta 8775 y abre la dirección correcta. La base de esta copia permanece en su propia carpeta `data`.

Con Python instalado y disponible como `python`:

```text
python app.py init
python app.py serve
```

Abre **http://127.0.0.1:8765**. Usuario inicial: `admin`; contraseña: la que introdujiste. No se entrega una contraseña predeterminada. Si tu instalación usa `py`, sustituye `python` por `py -3`. Detén el servidor con Ctrl+C.

La base nueva está vacía. Puedes usar **Administración → Importar inventario** para cargar tu archivo anterior. Para exportar, respaldar en USB y restaurar después de mantenimiento, sigue [IMPORTACION.md](IMPORTACION.md).

Para registrar datos manualmente, en Administración:

1. Registra un proveedor; conserva su identificador.
2. Crea los productos con precio de venta **incluyendo impuestos**.
3. Recibe mercancía indicando ID de producto y proveedor, lote, caducidad, costo y factura.
4. Crea cajeros y marca sus permisos. Para preservar el arqueo ciego, no concedas `reports.view` al cajero habitual.
5. Abre un turno con el fondo inicial; después usa Mostrador para vender.
6. Al terminar, declara el efectivo contado en Caja y corte. Confirmar genera el corte Z y cierra el turno.

La vista previa utilizada para las comprobaciones emplea datos ficticios en una base separada. No se incluye esa base ni sus credenciales en este paquete.

## Archivos de la entrega

| Archivo | Contenido |
|---|---|
| `schema.sql` | DDL completo, claves, restricciones, índices y protección del kardex |
| `core.py` | Autenticación, permisos, inventario, FEFO, venta, devolución, apertura y corte Z |
| `app.py` | API HTTP local, consultas, sesión, comprobaciones de origen y copia consistente |
| `static/index.html` | Pantallas de acceso, mostrador, caja y administración |
| `static/style.css` | Layout adaptable, estilos de impresión de 58/80 mm |
| `static/app.js` | Interacción por teclado, formularios y cobro por medio seleccionado |
| `ARQUITECTURA.md` | Modelo, flujos, decisiones y límites de operación |
| `API.md` | Rutas y ejemplos de solicitudes de los módulos críticos |
| `test_pos.py` y `test_inventory_io.py` | Pruebas de integridad, permisos, concurrencia e importación/restauración |
| `inventory_io.py` y `migrations.py` | Archivos de inventario, respaldo completo y actualización de bases anteriores |
| `static/inventory-ui.js` | Asistentes de importación, exportación y restauración |

## Capacidades incluidas

- Inicio individual con contraseña o PIN de al menos seis dígitos, sesiones y bloqueo temporal por intentos fallidos.
- Roles y permisos individuales con casillas; comprobación de permisos en el servidor, no solo en la pantalla.
- Fondo inicial obligatorio, un turno activo por caja y por cajero.
- Corte X autorizado; corte Z con conteo previo, diferencia, métodos de pago, devoluciones, departamentos y proveedores. Consulta general de un rango de turnos.
- Productos separados de lotes; mínimos/máximos y punto de reorden; bajas lógicas; costos y margen unitario estimado sujetos a permiso.
- Recepciones con lote, proveedor y caducidad opcionales, FEFO, ajustes con motivo y kardex por usuario.
- Importación con selección de productos; exportación CSV, XLS de texto y JSON; respaldo y restauración completos desde la interfaz.
- Venta por teclado, búsqueda por código/nombre/sustancia, efectivo/tarjeta/transferencia, cambio, clientes con descuento e impresión desde navegador.
- Devoluciones parciales y anulación completa con trazabilidad hasta el lote; cuarentena opcional para devoluciones no vendibles.
- Flag de receta y captura obligatoria de médico, cédula y folio cuando se activa.
- Directorio de proveedores, clientes e historial de compras.
- Cartera de fiados con cargos por medicamentos, abonos al saldo global y su integración al corte. Consulta [FIADOS.md](FIADOS.md) y [COBROS-Y-GANANCIA.md](COBROS-Y-GANANCIA.md).

## Pruebas

```text
python -m unittest -v test_pos.py test_inventory_io.py
```

La suite prueba pagos mixtos e impuestos, FEFO, descuento, idempotencia, stock insuficiente, fallo inyectado después de descontar inventario, venta concurrente, cierre, devolución en otro turno, redondeo, cuarentena, ajuste, receta, permisos, bloqueo de login y protección HTTP. Se ejecutó satisfactoriamente durante la entrega. La revisión en navegador cubrió acceso, apertura, venta mixta, cambio, corte Z y el flujo de importación, descarga y restauración en bases de prueba.

No se han medido tiempos ni RAM en un equipo físico de 4 GB; la elección de dependencias y el tamaño de la interfaz buscan ese objetivo sin presentar un rendimiento no medido como garantía. No se probó una impresora o un escáner físico.

## Respaldo y recuperación

Para uso cotidiano, usa **Administración → Respaldar todo**, copia el archivo descargado a tu USB y recupéralo en una instalación vacía mediante **Restaurar respaldo**. Los pasos detallados están en [IMPORTACION.md](IMPORTACION.md). La siguiente alternativa es una copia SQLite para uso técnico.


```text
python app.py backup --destination respaldo-2026-10-06.sqlite3
```

El destino debe ser nuevo. La copia usa la API de respaldo SQLite y verifica su integridad. No copies únicamente el archivo principal mientras el servidor está activo: puede haber cambios en el WAL.

Para recuperar, detén el servidor, conserva una copia del conjunto anterior y arranca sobre la copia verificada:

```text
python app.py serve --db respaldo-2026-10-06.sqlite3
```

Programar la rotación de copias, cifrado y una prueba periódica de restauración forma parte del despliegue. No abras el archivo SQLite desde una carpeta compartida de red.

## Alcance de esta base

El servidor escucha exclusivamente en `127.0.0.1`. Está pensado para un equipo local, con varias solicitudes concurrentes sobre la misma base. Para varias terminales físicas se necesita un servicio de red con HTTPS, servidor HTTP adecuado y una política de sesiones y respaldos; no basta con cambiar la dirección de escucha.

Los pagos por tarjeta o transferencia son **registros de pagos confirmados externamente**. El programa no cobra ni reembolsa en bancos o terminales. La impresión usa el diálogo del navegador y el controlador de la impresora; no incluye impresión silenciosa, apertura de cajón, ESC/POS ni facturación fiscal. Los datos de receta son una estructura de trazabilidad, no una certificación regulatoria.

La administración usa formularios sencillos y algunos identificadores numéricos. Se incluye descuento porcentual por cliente; no listas de precios múltiples, cuentas por pagar, sincronización entre sucursales, fraccionamiento de unidades o edición de recetas después de vender. La decisión de reingresar un medicamento devuelto debe seguir el procedimiento validado por la farmacia; usa cuarentena cuando no corresponda ponerlo a la venta.

Las fechas de eventos se guardan en UTC. La caducidad se evalúa con la fecha local del servidor: configura correctamente su zona horaria. Las unidades que vencen hoy se excluyen de venta por la política conservadora de esta base.
