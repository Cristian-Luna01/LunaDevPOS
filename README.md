# LunaDev POS

Punto de venta de escritorio para Windows, con inventario local, caja y consulta central para el dueño de uno o varios establecimientos.

**Versión: 0.1.0-beta · pruebas controladas · 18 de octubre de 2026.**

## Descargar e instalar

El instalador y el paquete con asistente y manual se distribuyen en **Releases**. Descarga el ZIP completo y comienza con `EMPIEZA-AQUI.txt`. En Windows 10/11 de 64 bits el instalador incluye el motor necesario; la computadora de caja no necesita Python ni Node.js.

Antes de actualizar una instalación existente, exporta un respaldo completo fuera de la computadora. La actualización conserva datos; una instalación nueva empieza sin inventario ni usuarios del negocio.

## Funciones

- Ventas en efectivo, tarjeta y transferencia; descuentos y promociones.
- Clientes, créditos, abonos y cambio en efectivo.
- Apertura y cierre de turnos; entradas y salidas de caja.
- Inventario por lotes, recepciones, ajustes con motivo y valoración a costo de compra.
- Historial, métricas, exportación a Excel/CSV y respaldos completos.
- Usuarios y permisos configurables; identidad visual del negocio.
- Panel central de consulta y selección de sucursales, manteniendo inventario y caja separados por local.

La aplicación opera localmente; la consulta remota requiere internet y la publicación/configuración del servicio central. El panel no sustituye los respaldos completos de la computadora de caja.

## Estructura

```text
punto-de-venta/          Aplicación Python, SQLite, interfaz y pruebas
pagina-administrador/   Cloudflare Worker, D1, interfaz y asistente de publicación
docs/                   Manual y notas de actualización
.github/workflows/      Verificaciones manuales de código
VERSION                 Versión del repositorio
CHANGELOG.md            Cambios por versión
```

## Ejecutar desde código

Con Python 3.12 de 64 bits, dentro de `punto-de-venta`:

```powershell
python -m pip install -r requirements-desktop.txt
python native_desktop.py --data-dir C:\LunaDevPOS-Pruebas
```

Usa una carpeta nueva para pruebas. `native_desktop.py` es la entrada del escritorio actual; algunos documentos históricos describen además el modo web local.

Para el servicio central se necesita Node.js LTS, dentro de `pagina-administrador`:

```powershell
npm ci
npm test
```

Para una publicación nueva usa `Crear-pagina.cmd`. Para actualizar un servicio existente conserva su carpeta configurada y usa `Actualizar-pagina.cmd`. No reemplaces sus credenciales ni sus identificadores. `wrangler.example.json` es una plantilla sin datos de la cuenta de pruebas.

## Calidad y límites conocidos

La última comprobación local aprobó 201 pruebas Python y 22 pruebas de interfaz/servicio central. La simulación acelerada de 183 días comprobó 14,640 compras con 749,726 comparaciones independientes sin discrepancias observadas. Estos resultados no garantizan ausencia de errores futuros ni sustituyen el piloto en el equipo real.

- Facturación: entorno de pruebas; la emisión fiscal real no está habilitada como una función lista para producción.
- Las devoluciones de ventas a crédito están bloqueadas y requieren resolver la deuda mediante un procedimiento específico.
- La aplicación Windows publicada es de 64 bits; no se entrega compilación de 32 bits ni Android.
- Las comisiones de tarjeta son estimaciones configurables, no una conciliación automática con la terminal bancaria.
- En la nube el detalle antiguo se compacta; los datos locales y el respaldo completo siguen siendo necesarios.

## Versionado y distribución

`main` conserva el código vigente. Cada entrega se identifica con una etiqueta; los instaladores se guardan en Releases, no dentro del historial de Git. La primera entrega se identifica como `v0.1.0-beta`.

No se incluyen bases de datos, cuentas reales, claves, dependencias ni compilaciones. El binario opcional `cloudflared.exe` se obtiene de su fuente oficial; su procedencia y licencia están en `punto-de-venta/vendor`. Para recompilar el instalador se debe generar el payload `programa.zip`, que no está versionado.

Consulta [el manual](docs/Manual-LunaDevPOS.html), [cómo contribuir](CONTRIBUTING.md) y [manejo de seguridad](SECURITY.md). No se ha otorgado una licencia de código abierto ni autorización general de reutilización comercial.
