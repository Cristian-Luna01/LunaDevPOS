# LunaPOS

Punto de venta para Windows con ventas, inventario por lotes, clientes, crédito, caja, historial, reportes y respaldos. Esta carpeta reúne el código mejorado y la aplicación compilada optimizada, versión **0.2.0-beta.1**.

## Abrir el programa

Haz doble clic en **Abrir LunaPOS**. No necesitas instalar Python ni Node para usar la aplicación compilada. Los datos están en `datos/` y los respaldos automáticos en `respaldos/`. Conserva la carpeta en su ubicación actual: el acceso directo guarda su ruta completa.

## Estructura

```text
punto-de-venta/          Código Python, API, SQLite, interfaz y pruebas
pagina-administrador/   Panel central, servicio Cloudflare y migraciones
herramientas/           Compilación, verificación y desarrollo
docs/                   Manual y guías técnicas
.github/workflows/      Verificación automática para el código
programa/               Aplicación optimizada lista para abrir
datos/                  Datos privados y configuración del negocio
respaldos/              Copias de recuperación
Abrir LunaPOS.lnk       Acceso de uso diario
GUIA.md                 Mejoras, uso y límites
VERSION                 Versión del código
CHANGELOG.md            Historial de versiones
requirements-release.lock Dependencias exactas para compilar
```

El original `LunaDevPOS` se conserva separado. Esta copia no incluye su historial `.git`; contiene las fuentes mejoradas. El código incorporado no sustituye ni restaura la base del negocio.

## Mejoras conservadas

- Permisos del historial financiero y reportes Z congelados.
- Registro durable de operaciones y recuperación sin duplicar ventas o movimientos.
- Respaldos automáticos configurables y prueba de restauración.
- Sincronización comprimida por partes con comprobación de integridad.
- Índices de búsqueda e historial; formularios con selección por nombre/código.
- Comprobación de impresora y escáner.
- Compilación con versiones y hashes fijados y motor depurado: unos 467 MB.

## Desarrollar o ejecutar el código

Se requiere Python 3.12 de 64 bits. Instala las dependencias de `punto-de-venta/requirements-desktop.txt` en tu entorno de desarrollo. Para ejecutar el código puedes usar `herramientas/Ejecutar-codigo.cmd`: utiliza la misma carpeta `datos`, por lo que debes cerrar antes la aplicación compilada. Para pruebas aisladas ejecuta `native_desktop.py --data-dir` con una carpeta nueva.

El conector remoto ya está incluido en `programa`. Para ejecutar las pruebas del conector o recompilar desde las fuentes, prepara su copia de desarrollo con `herramientas/Preparar-conector.ps1`; el ejecutable se descarga de su procedencia documentada y se valida por hash. No se duplica ese binario dentro de las fuentes por defecto.

Consulta [compilación y operación](docs/COMPILACION-Y-OPERACION.md), [las mejoras](GUIA.md) y [el manual](docs/Manual-LunaDevPOS.html).

## Panel central

La venta local funciona sin internet. La consulta remota requiere conexión y configurar/publicar el panel. Para desarrollar el servicio central utiliza Node y `npm ci` y `npm test` en `pagina-administrador`. La migración `0003_chunked_sync.sql` forma parte del servicio mejorado; no copies fuentes antiguas encima. Se conservan los asistentes `Crear-pagina.cmd` y `Actualizar-pagina.cmd`.

## Validación y límites

La versión mejorada se verificó anteriormente con 223 pruebas Python y 30 JavaScript. La depuración del motor pasó 32 pruebas Python y comprobaciones del ejecutable, ventas con recuperación tras recarga, edición de productos e impresión PDF. La impresión física, el escáner físico y una publicación real del panel requieren su comprobación en el equipo y servicio elegidos. La facturación sigue siendo un entorno de pruebas, no emisión fiscal habilitada.

Los respaldos guardados en el mismo disco no protegen de una avería de ese disco. Conserva también copias fuera del equipo.

Consulta [seguridad](SECURITY.md) y [contribución](CONTRIBUTING.md). Se conservan las condiciones de uso del proyecto original; esta copia no añade una licencia general de reutilización.
