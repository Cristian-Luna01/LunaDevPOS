# Página central de sucursales

Una cuenta central por negocio; sucursales con caja e inventario locales independientes.
El mismo instalador de escritorio sirve para uno o varios locales. No lleva cuentas o claves precargadas.

## Publicación en una cuenta nueva

Instalar las dependencias con el archivo de bloqueo, autenticar Wrangler en la cuenta del dueño,
crear una base D1 y sustituir su identificador en la configuración. Ejecutar `schema.sql` en la base nueva.
Publicar Worker y assets. Configurar los secretos `OWNER_EMAIL` y `OWNER_PASSWORD_SHA256`.
El segundo debe ser el SHA-256 de una clave aleatoria de 32 bytes (64 caracteres hexadecimales);
**no usar este esquema con una contraseña elegida por una persona**, pues no es un derivador de contraseñas.
Entregar esa clave al dueño por un canal privado. Nunca incluir claves, OAuth o datos en paquetes de software.

El despliegue de esta carpeta es de prueba. Para otros negocios copiar una configuración nueva con
nombre de servicio y base propios, sin los identificadores de cuenta/base de la prueba.
No ejecutar otra vez `schema.sql` sobre una base existente: aplicar migraciones revisadas.

## Enlazar un local

Entrar en la página central, crear la sucursal y copiar su clave. En el POS, Configuración →
Cuenta del dueño · Sucursales y enlace fijo: URL HTTPS workers.dev, nombre del local y clave.
La clave se almacena cifrada con DPAPI en una base lateral de conexión, independiente de los respaldos
del negocio. Rotar desde la página central cuando se reemplace la computadora.

## Sincronización y límites

Cada local envía el panel completo de Dirección y el inventario actual,
aproximadamente cada 15 segundos. Se usan revisiones crecientes y una identidad de instalación.
La página reemplaza la copia anterior de esa sucursal, no suma envíos ni reintentos. La clave de un local
no permite leer el panel del dueño ni escribir otros locales. La sincronización no habilita operaciones remotas.

La réplica se conserva en D1 al apagar el local. El historial se envía incrementalmente por fecha,
con huellas verificadas contra el estado publicado; mientras falta una fecha se indica que continúa la
sincronización. El selector se aplica también a CSV y Excel de cuatro hojas. Se informa la hora recibida y la falta de cobertura.
Las ventas locales no dependen de Cloudflare. Al recuperar conexión se envía el estado vigente, calculado
desde la base operativa. No existe una cola de eventos históricos en este protocolo: la copia de consulta
abarca 31 días; el historial completo y los respaldos siguen en cada POS.

Límite actual del mensaje: 900 KB; no se truncan catálogos. No es un límite de sucursales fijo, pero los
límites gratuitos de CPU, solicitudes, filas y almacenamiento de Cloudflare restringen la escala.
Los snapshots se leen con índices por clave; no se envían clientes ni contraseñas de empleados.

Fuentes oficiales: [workers.dev](https://developers.cloudflare.com/workers/configuration/routing/workers-dev/),
[límites de Workers](https://developers.cloudflare.com/workers/platform/limits/),
[D1 gratuito](https://developers.cloudflare.com/d1/platform/pricing/).

## Validación

`npm test`: SQLite real para el adaptador de pruebas del contrato D1, autenticación, permisos, revocación,
idempotencia, revisiones, validación de importes y suma de locales. También se probó con Wrangler local,
dos bases POS reales, Qt WebEngine en tamaños de computadora/teléfono y el servicio publicado.

La interfaz utiliza las mismas pantallas de Dirección del POS: ventas/caja, inventario, historial, métricas,
reposición y configuración de locales. No incluye facturación CFDI ni aplicación móvil sin conexión. No se considera todavía una
versión comercial certificada; probar en las computadoras y red del negocio antes de uso definitivo.
