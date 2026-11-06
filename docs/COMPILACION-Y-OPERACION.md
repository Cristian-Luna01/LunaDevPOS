# Compilación y operación de la versión mejorada

## Entradas vigentes

- Escritorio: `punto-de-venta/native_desktop.py`.
- API local: `punto-de-venta/app.py`.
- Dominio comercial: `punto-de-venta/core.py` y módulos de crédito, inventario y facturación.
- Solicitudes durables y recuperación: `pending_operations.py` y `static/pending-operations.js`.
- Respaldos externos: `external_backup.py` y `static/backup-settings.js`.
- Búsqueda e índices: `performance.py`.
- Transporte por partes: `sync_transport.py` y `pagina-administrador/sync_transport.js`.
- Formularios de inventario: `static/inventory-forms.js`; clientes y proveedores: `static/entities-ui.js`.
- Empaquetado: `LunaDevPOS.spec`, `Instalar-LunaDevPOS.spec` y `herramientas/Compilar.py`.

Solo se incluyen las tres recetas vigentes: aplicación, instalador y desinstalador.
La aplicación excluye Tkinter, QML y traducciones ajenas a español/inglés.
El script de compilación prepara una entrega en directorios de trabajo; no modifica la aplicación en uso.

## Compilar en Windows x64 con Python 3.12

Desde la raíz de la copia, prepara primero el conector:

```powershell
.\herramientas\Preparar-conector.ps1
```

```powershell
py -3.12 -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install --require-hashes -r requirements-release.lock
.\.build-venv\Scripts\python.exe herramientas\Compilar.py
```

El bloqueo fija versiones y hashes de las ruedas de Windows. Se genera una
carpeta portátil, un instalador, un manifiesto SHA256 y una prueba del instalador
en una carpeta temporal. No se instala en el negocio ni se publica automáticamente.
El resultado no se presenta como idéntico byte por byte entre máquinas: PyInstaller
y las herramientas del sistema pueden incorporar metadatos del entorno.

## Comprobar

Dentro de `punto-de-venta`:

```powershell
..\.build-venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py"
```

Para la suite completa usa `herramientas/Verificar.ps1` desde un entorno con Python
y Node disponibles; para escritorio real utiliza:

```powershell
.\.build-venv\Scripts\python.exe herramientas\Probar-escritorio.py --output work\validacion
.\.build-venv\Scripts\python.exe herramientas\Medir-rendimiento.py --output work\rendimiento.json
```

La prueba Qt utiliza una base temporal, simula una respuesta perdida, recarga el
mostrador y recupera la venta. No utiliza la base del negocio ni una impresora física.

## Actualizar el panel central

Conserva la carpeta configurada del negocio, sus credenciales y su archivo
`CONFIGURADO.json`. Actualiza únicamente fuentes y usa `Actualizar-pagina.cmd`.
El asistente instala dependencias e incorpora `migrations/0003_chunked_sync.sql`
antes de publicar. Para un negocio nuevo utiliza `Crear-pagina.cmd`.

El transporte pequeño anterior sigue disponible. Las actualizaciones grandes
se comprimen y envían en partes de 512 KiB, con identidad, revisión y SHA256.
La recepción publica únicamente documentos completos. D1 almacena las partes en
filas separadas para respetar el límite de tamaño por fila.

Límites explícitos: 32 MiB sin comprimir, 16 MiB comprimidos y 32 partes. El catálogo
central mantiene su validación de hasta 10,000 productos. Se necesita publicar el
Worker actualizado para usar el nuevo protocolo. La operación local funciona
aunque no se haya actualizado el servicio remoto.

## Datos y recuperación

El diario de operaciones y la identidad de la instalación son tablas operativas
locales. Se guardan en la misma base SQLite, antes de ejecutar la operación.
La restauración limpia el diario y renueva la identidad para no reutilizar cuentas
o solicitudes de otra base. Los respaldos lógicos comerciales no trasladan ese
diario pendiente a otra instalación.

Los respaldos externos se ejecutan cada 30 minutos mientras el escritorio está
abierto. También se pueden solicitar manualmente y comprobar con una restauración
en una base temporal. No se elige una unidad por el usuario: debe configurar una
carpeta real. No se eliminan automáticamente los respaldos externos.

La recuperación después de una avería del disco depende del último respaldo
externo disponible; no se promete recuperar trabajo posterior a esa copia.

## Fuentes técnicas verificadas

- [PyInstaller: construcción y opciones](https://pyinstaller.org/en/stable/usage.html).
- [Cloudflare D1: límites de filas y consultas](https://developers.cloudflare.com/d1/platform/limits/).

En reposo se utiliza un heartbeat autenticado, conservando la fecha de conexión
sin reenviar el catálogo completo. Un cambio de datos o de fecha vuelve a generar
la instantánea.


## Carpetas de esta entrega

`programa/` contiene el ejecutable optimizado; `datos/` conserva la base y configuración; `respaldos/` es el destino actual de las copias. El acceso **Abrir LunaPOS** pasa explícitamente la ruta de datos. Para trabajar con el código usa `herramientas/Ejecutar-codigo.cmd` con la aplicación cerrada, o una ruta temporal para pruebas. La compilación crea `work/` y paquetes que no son necesarios para abrir la aplicación.

El historial Git del original no se copia aquí. El manifiesto de compilación admite fuentes exportadas sin repositorio Git. El instalador genera e incluye el desinstalador antes de crear su payload.
