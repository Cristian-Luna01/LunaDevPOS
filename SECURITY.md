# Seguridad y alcance de soporte

LunaDev POS es una entrega candidata para pruebas operativas. La evaluación y sus límites están en `docs/seguridad/AUDITORIA-2026-10-26.md`; no se presenta como software certificado por OWASP ni como producto libre de vulnerabilidades.

Para comunicar una posible vulnerabilidad, contacta al propietario del repositorio por un canal privado o utiliza los avisos privados de seguridad de GitHub si están habilitados. No publiques contraseñas, tokens, respaldos, datos de clientes o instrucciones con información del negocio en un issue público. Incluye versión, escenario reproducible y evidencia con los datos ocultos.

Si se filtra una clave, revócala y reemplázala: borrarla del archivo actual no la elimina del historial de Git. Las credenciales del dueño, las de sucursal y las de Cloudflare tienen funciones distintas y no se sustituyen entre sí.

Las pruebas, escáneres y revisión manual se repiten antes de distribuir. Los workflows de código y seguridad se ejecutan con cambios y solicitudes de integración; pueden ejecutarse manualmente. Un resultado aprobado representa esa revisión y esa fecha, no protección permanente frente a avisos futuros. Deben revisarse también los avisos de Python, Qt/Chromium, OpenSSL, Cloudflare y Windows.

Requisitos de operación: cuentas con permisos mínimos y contraseñas únicas, sistema operativo actualizado, disco y medios externos cifrados cuando contienen información personal/financiera, respaldo completo restaurable fuera de la caja y verificación del dominio HTTPS publicado. La réplica del dueño no reemplaza el respaldo. No expongas directamente el puerto local del POS a internet. La modalidad LAN HTTP opcional es solo para redes confiables; para acceso remoto usa el panel central HTTPS.

Esta versión conserva SQLite y respaldos JSON sin cifrado de aplicación. Una huella SHA-256 no cifra datos ni autentica un respaldo frente a alguien que pueda modificarlo y recalcularla. Quien controla Windows o los archivos SQLite puede manipularlos fuera de la aplicación; los permisos y triggers del POS no sustituyen la protección del equipo. El soporte de facturación continúa exclusivamente en sandbox.
