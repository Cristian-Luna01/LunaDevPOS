# LunaDev POS

Punto de venta de escritorio para Windows, con inventario local, caja y consulta central para el dueÃƒÂ±o de uno o varios establecimientos.

**VersiÃƒÂ³n: 0.1.0-beta Ã‚Â· pruebas controladas Ã‚Â· 18 de octubre de 2026.**

## Descargar e instalar

El instalador y el paquete con asistente y manual se distribuyen en **Releases**. Descarga el ZIP completo y comienza con `EMPIEZA-AQUI.txt`. En Windows 10/11 de 64 bits el instalador incluye el motor necesario; la computadora de caja no necesita Python ni Node.js.

Antes de actualizar una instalaciÃƒÂ³n existente, exporta un respaldo completo fuera de la computadora. La actualizaciÃƒÂ³n conserva datos; una instalaciÃƒÂ³n nueva empieza sin inventario ni usuarios del negocio.

## Funciones

- Ventas en efectivo, tarjeta y transferencia; descuentos y promociones.
- Clientes, crÃƒÂ©ditos, abonos y cambio en efectivo.
- Apertura y cierre de turnos; entradas y salidas de caja.
- Inventario por lotes, recepciones, ajustes con motivo y valoraciÃƒÂ³n a costo de compra.
- Historial, mÃƒÂ©tricas, exportaciÃƒÂ³n a Excel/CSV y respaldos completos.
- Usuarios y permisos configurables; identidad visual del negocio.
- Panel central de consulta y selecciÃƒÂ³n de sucursales, manteniendo inventario y caja separados por local.

La aplicaciÃƒÂ³n opera localmente; la consulta remota requiere internet y la publicaciÃƒÂ³n/configuraciÃƒÂ³n del servicio central. El panel no sustituye los respaldos completos de la computadora de caja.

## Estructura

```text
punto-de-venta/          AplicaciÃƒÂ³n Python, SQLite, interfaz y pruebas
pagina-administrador/   Cloudflare Worker, D1, interfaz y asistente de publicaciÃƒÂ³n
docs/                   Manual y notas de actualizaciÃƒÂ³n
.github/workflows/      Verificaciones manuales de cÃƒÂ³digo
VERSION                 VersiÃƒÂ³n del repositorio
CHANGELOG.md            Cambios por versiÃƒÂ³n
```

## Ejecutar desde cÃƒÂ³digo

Con Python 3.12 de 64 bits, dentro de `punto-de-venta`:

```powershell
python -m pip install -r requirements-desktop.txt
python native_desktop.py --data-dir C:\LunaDevPOS-Pruebas
```

Usa una carpeta nueva para pruebas. `native_desktop.py` es la entrada del escritorio actual; algunos documentos histÃƒÂ³ricos describen ademÃƒÂ¡s el modo web local.

Para el servicio central se necesita Node.js LTS, dentro de `pagina-administrador`:

```powershell
npm ci
npm test
```

Para una publicaciÃƒÂ³n nueva usa `Crear-pagina.cmd`. Para actualizar un servicio existente conserva su carpeta configurada y usa `Actualizar-pagina.cmd`. No reemplaces sus credenciales ni sus identificadores. `wrangler.example.json` es una plantilla sin datos de la cuenta de pruebas.

## Calidad y lÃƒÂ­mites conocidos

La ÃƒÂºltima comprobaciÃƒÂ³n local aprobÃƒÂ³ 201 pruebas Python y 22 pruebas de interfaz/servicio central. La simulaciÃƒÂ³n acelerada de 183 dÃƒÂ­as comprobÃƒÂ³ 14,640 compras con 749,726 comparaciones independientes sin discrepancias observadas. Estos resultados no garantizan ausencia de errores futuros ni sustituyen el piloto en el equipo real.

- FacturaciÃƒÂ³n: entorno de pruebas; la emisiÃƒÂ³n fiscal real no estÃƒÂ¡ habilitada como una funciÃƒÂ³n lista para producciÃƒÂ³n.
- Las devoluciones de ventas a crÃƒÂ©dito estÃƒÂ¡n bloqueadas y requieren resolver la deuda mediante un procedimiento especÃƒÂ­fico.
- La aplicaciÃƒÂ³n Windows publicada es de 64 bits; no se entrega compilaciÃƒÂ³n de 32 bits ni Android.
- Las comisiones de tarjeta son estimaciones configurables, no una conciliaciÃƒÂ³n automÃƒÂ¡tica con la terminal bancaria.
- En la nube el detalle antiguo se compacta; los datos locales y el respaldo completo siguen siendo necesarios.

## Versionado y distribuciÃƒÂ³n

`main` conserva el cÃƒÂ³digo vigente. Cada entrega se identifica con una etiqueta; los instaladores se guardan en Releases, no dentro del historial de Git. La primera entrega se identifica como `v0.1.0-beta`.

No se incluyen bases de datos, cuentas reales, claves, dependencias ni compilaciones. El binario opcional `cloudflared.exe` se obtiene de su fuente oficial; su procedencia y licencia estÃƒÂ¡n en `punto-de-venta/vendor`. Para recompilar el instalador se debe generar el payload `programa.zip`, que no estÃƒÂ¡ versionado.

Consulta [el manual](docs/Manual-LunaDevPOS.html), [cÃƒÂ³mo contribuir](CONTRIBUTING.md) y [manejo de seguridad](SECURITY.md). No se ha otorgado una licencia de cÃƒÂ³digo abierto ni autorizaciÃƒÂ³n general de reutilizaciÃƒÂ³n comercial.
