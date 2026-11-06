# Aplicación local de LunaPOS

La entrada actual es `native_desktop.py`, con Python 3.12, SQLite y Qt WebEngine. Para el uso diario abre **Abrir LunaPOS** en la raíz; no necesitas ejecutar estos archivos individualmente.

## Módulos principales

- `core.py`: base de datos, transacciones y reglas comerciales.
- `app.py`: servidor y API HTTP local; `API.md` documenta los contratos.
- `static/`: interfaz HTML/CSS/JavaScript.
- `pending_operations.py`: operaciones durables y recuperación.
- `external_backup.py`: respaldos configurables y verificación.
- `performance.py`: índices y búsquedas.
- `sync_transport.py`: transporte comprimido por partes.
- `native_desktop.py`: escritorio, impresión y comprobaciones del motor.
- `desktop.py`: interfaz antigua de desarrollo y funciones compartidas; Tkinter solo se carga al ejecutar esa interfaz.
- `runtime_check.py`: diagnóstico del paquete con datos temporales, venta, recuperación y PDF.
- `LunaDevPOS.spec`: compilación optimizada; las otras dos recetas vigentes generan instalador y desinstalador.

## Desarrollo y pruebas

Sigue [el README principal](../README.md) y [la guía de compilación](../docs/COMPILACION-Y-OPERACION.md). Las pruebas `test_*` se conservan para verificar futuras modificaciones. `vendor` conserva licencia y procedencia del conector; usa `herramientas/Preparar-conector.ps1` antes de recompilar o probar el acceso remoto desde las fuentes.

Los accesos históricos `Iniciar.cmd`, `Iniciar.ps1` y `Abrir Direccion.cmd` se conservan para mantenimiento; pueden utilizar otras ubicaciones de datos. No sustituyen el acceso de uso diario de la raíz.

Consulta [importación y respaldos](IMPORTACION.md), [configuración](CONFIGURACION.md) y [actualización](ACTUALIZAR.md).
