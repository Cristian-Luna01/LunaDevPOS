# LunaDev POS

Punto de venta de escritorio para Windows, con inventario local, caja y consulta central para el dueÃ±o de uno o varios establecimientos.

**VersiÃ³n: 0.1.0-beta Â· pruebas controladas Â· 18 de octubre de 2026.**

## Descargar e instalar

El instalador y el paquete con asistente y manual se distribuyen en **Releases**. Descarga el ZIP completo y comienza con `EMPIEZA-AQUI.txt`. En Windows 10/11 de 64 bits el instalador incluye el motor necesario; la computadora de caja no necesita Python ni Node.js.

Antes de actualizar una instalaciÃ³n existente, exporta un respaldo completo fuera de la computadora. La actualizaciÃ³n conserva datos; una instalaciÃ³n nueva empieza sin inventario ni usuarios del negocio.

## Funciones

- Ventas en efectivo, tarjeta y transferencia; descuentos y promociones.
- Clientes, crÃ©ditos, abonos y cambio en efectivo.
- Apertura y cierre de turnos; entradas y salidas de caja.
- Inventario por lotes, recepciones, ajustes con motivo y valoraciÃ³n a costo de compra.
- Historial, mÃ©tricas, exportaciÃ³n a Excel/CSV y respaldos completos.
- Usuarios y permisos configurables; identidad visual del negocio.
- Panel central de consulta y selecciÃ³n de sucursales, manteniendo inventario y caja separados por local.

La aplicaciÃ³n opera localmente; la consulta remota requiere internet y la publicaciÃ³n/configuraciÃ³n del servicio central. El panel no sustituye los respaldos completos de la computadora de caja.

## Estructura

```text
punto-de-venta/          AplicaciÃ³n Python, SQLite, interfaz y pruebas
pagina-administrador/   Cloudflare Worker, D1, interfaz y asistente de publicaciÃ³n
docs/                   Manual y notas de actualizaciÃ³n
.github/workflows/      Verificaciones manuales de cÃ³digo
VERSION                 VersiÃ³n del repositorio
CHANGELOG.md            Cambios por versiÃ³n
```

## Ejecutar desde cÃ³digo

Con Python 3.12 de 64 bits, dentro de `punto-de-venta`:

```powershell
python -m pip install -r requirements-desktop.txt
python native_desktop.py --data-dir C:\LunaDevPOS-Pruebas
```

Usa una carpeta nueva para pruebas. `native_desktop.py` es la entrada del escritorio actual; algunos documentos histÃ³ricos describen ademÃ¡s el modo web local.

Para el servicio central se necesita Node.js LTS, dentro de `pagina-administrador`:

```powershell
npm ci
npm test
```

Para una publicaciÃ³n nueva usa `Crear-pagina.cmd`. Para actualizar un servicio existente conserva su carpeta configurada y usa `Actualizar-pagina.cmd`. No reemplaces sus credenciales ni sus identificadores. `wrangler.example.json` es una plantilla sin datos de la cuenta de pruebas.

## Calidad y lÃ­mites conocidos

La Ãºltima comprobaciÃ³n local aprobÃ³ 201 pruebas Python y 22 pruebas de interfaz/servicio central. La simulaciÃ³n acelerada de 183 dÃ­as comprobÃ³ 14,640 compras con 749,726 comparaciones independientes sin discrepancias observadas. Estos resultados no garantizan ausencia de errores futuros ni sustituyen el piloto en el equipo real.

- FacturaciÃ³n: entorno de pruebas; la emisiÃ³n fiscal real no estÃ¡ habilitada como una funciÃ³n lista para producciÃ³n.
- Las devoluciones de ventas a crÃ©dito estÃ¡n bloqueadas y requieren resolver la deuda mediante un procedimiento especÃ­fico.
- La aplicaciÃ³n Windows publicada es de 64 bits; no se entrega compilaciÃ³n de 32 bits ni Android.
- Las comisiones de tarjeta son estimaciones configurables, no una conciliaciÃ³n automÃ¡tica con la terminal bancaria.
- En la nube el detalle antiguo se compacta; los datos locales y el respaldo completo siguen siendo necesarios.

## Versionado y distribuciÃ³n

`main` conserva el cÃ³digo vigente. Cada entrega se identifica con una etiqueta; los instaladores se guardan en Releases, no dentro del historial de Git. La primera entrega se identifica como `v0.1.0-beta`.

No se incluyen bases de datos, cuentas reales, claves, dependencias ni compilaciones. El binario opcional `cloudflared.exe` se obtiene de su fuente oficial; su procedencia y licencia estÃ¡n en `punto-de-venta/vendor`. Para recompilar el instalador se debe generar el payload `programa.zip`, que no estÃ¡ versionado.

Consulta [el manual](docs/Manual-LunaDevPOS.html), [cÃ³mo contribuir](CONTRIBUTING.md) y [manejo de seguridad](SECURITY.md). No se ha otorgado una licencia de cÃ³digo abierto ni autorizaciÃ³n general de reutilizaciÃ³n comercial.
