# Evaluación de seguridad, rendimiento y capacidad — 26 de octubre de 2026

## Alcance y significado del resultado

Evaluación interna del código de LunaDev POS, la API local, el panel central y el proceso de distribución. Base: `a7bf298`; correcciones en `seguridad/auditoria-2026-10-26`, entrega 0.2.0-rc.2. No es una certificación, una auditoría independiente ni una declaración de cumplimiento integral de ASVS L1/L2/L3, ISO 27001, PCI DSS o legislación fiscal.

Se usaron como referencias primarias:

- [OWASP ASVS 5.0](https://owasp.org/projects/asvs): requisitos de controles verificables. [Su guía de evaluación](https://github.com/OWASP/ASVS/blob/master/5.0/en/0x04-Assessment_and_Certification.md) exige definir alcance, evidencia y excepciones; OWASP no certifica software ni verificadores.
- [OWASP WSTG 4.2](https://wstg.owasp.org/stable/4-Web_Application_Security_Testing/): pruebas de autenticación, autorización, sesiones, validación, configuración y lógica de negocio.
- [NIST SSDF, SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final): revisión de código y componentes, pruebas, tratamiento de hallazgos y prevención de regresiones.

Las pruebas adversarias y de carga fueron locales y sobre datos ficticios. Además, el propietario proporcionó el dominio de su publicación de pruebas: se hicieron cinco consultas de lectura sin iniciar sesión, se guardó un respaldo privado de D1 y se publicó la corrección en el mismo servicio y cuenta comprobados. Se aplicó solo una migración aditiva de tablas/índices, sin sentencias de borrado ni sustitución de claves. No se certificó la protección de la cuenta de Cloudflare ni se modificó el equipo del establecimiento. Las pruebas de carga del Worker usan SQLite y la interfaz de pruebas de D1; no equivalen a una prueba de capacidad en la infraestructura real.

## Hallazgos y tratamiento

| ID | Hallazgo | Tratamiento | Evidencia |
| --- | --- | --- | --- |
| SEC-01 | npm señaló undici (alta), miniflare y wrangler (moderada), relacionados con herramientas de desarrollo/publicación. | Dependencias compatibles actualizadas; Wrangler fijado en 4.153.0. | Auditoría npm posterior: cero avisos conocidos. No implica ausencia de vulnerabilidades desconocidas. |
| SEC-02 | pip-audit detectó GHSA-xmj3-9gf7-h52w en setuptools 84.0.0, herramienta de compilación. | Pin 84.1.0. | pip-audit del lock completo posterior: cero avisos conocidos. |
| SEC-03 | El motor usado para compilar era Python 3.12.14, anterior a actualizaciones de seguridad recientes. | Motor oficial 3.14.10, distribución de PSF verificada por SHA-256 y firmas de sus componentes. | Regresión completa de 232 pruebas aprobada en el motor actualizado. Se conserva el motor/instalador anterior para recuperación. |
| SEC-04 | El bloqueo textual de DOCTYPE/ENTITY fiscal podía omitir declaraciones codificadas en UTF-16. | Parser defusedxml 0.7.1 para XML y acuses; mantiene verificaciones fiscales existentes. | Prueba UTF-16 con entidad rechazada antes de interpretar datos fiscales. No habilita timbrado real. |
| SEC-05 | Servidor con número no acotado de conexiones/hilos y puente sin tiempo explícito de socket. | Máximo 32 conexiones activas por servidor; exceso rechazado con 503; puente con tiempo de socket. | Prueba de saturación con límite reducido, rechazo y recuperación; prueba de carga concurrente. No es protección frente a todo DDoS. |
| SEC-06 | Cabeceras incompletas en algunas respuestas centrales y sin redirección HTTPS explícita en el Worker. | CSP, HSTS, nosniff, no-referrer, DENY y Permissions-Policy en respuestas HTTPS; HTTP redirige con 308. | Pruebas de cabeceras sobre 401 y de redirección. El POS de loopback sigue en HTTP interno deliberadamente. |
| SEC-07 | La ruta de login eliminaba espacios de la contraseña aunque se guardaban al crearla. | Validación de credenciales separada de los textos de formularios; sin recortar el secreto; límite de 500 caracteres. | Prueba de contraseña con espacios, rechazo de la variante modificada y regresión de login. |
| SEC-08 | Consulta de un local hidrataba también inventarios de otros locales. | Selección parametrizada por ID antes de recuperar/hidratar documentos. | Prueba: un documento dañado de otro local no impide consultar el local seleccionado; el conjunto completo falla sin presentar totales engañosos. |
| SEC-09 | El instalador buscaba powershell.exe mediante una ruta parcial. | Ruta absoluta desde SystemRoot; argumentos en lista, sin shell=True. | Revisión de llamada y pruebas de arranque/instalación. No protege frente a un sistema operativo ya comprometido. |
| SEC-10 | No había un flujo de seguridad continuo. | GitHub Actions separado: npm audit, pip-audit, Gitleaks y revisión Bandit; se mantienen las pruebas funcionales. | Archivos de workflow, versiones de herramientas fijadas y huella del binario de Gitleaks. |
| SEC-11 | El contador de fallos centrales podía perder incrementos al leer/escribir intentos concurrentes. | Incremento y decisión de bloqueo mediante UPSERT atómico. | Doce accesos incorrectos concurrentes dejan el bloqueo activo; el siguiente acceso se rechaza con 429. |

## Comprobaciones ejecutadas

- 232 pruebas Python aprobadas, incluidas nueve adversarias nuevas: rutas anónimas, sesión vencida/revocada, credenciales exactas, SQL hostil, rutas de archivo, CSRF, XML UTF-16 y agotamiento de conexiones. Suite completa aprobada tanto en el motor anterior como en el actualizado.
- 21 pruebas del panel central aprobadas: autenticación, limitación de intentos secuenciales y concurrentes, cookies, separación de sucursales, caducidad, entradas inválidas, HTTPS/cabeceras, réplica grande y conservación de resultados.
- Las 16 pruebas de interfaz del POS se ejecutan también en la verificación general: incluyen escáner, limpieza del cliente, importes y recuperación de operaciones.
- Instalación aislada del ejecutable, autoprueba de la aplicación instalada y arranque Qt WebEngine aprobados. El motor identificado por la entrega es Python 3.14.10, OpenSSL 3.5.9 y Qt 6.12.0, con Chromium base 140.0.7339.225 y nivel de parches de seguridad 152.0.7977.83 declarado por Qt. Es inventario de componentes, no una auditoría exhaustiva de todos sus binarios.
- Gitleaks 8.30.1 sobre el historial completo de base: 14 commits, aproximadamente 1.24 MB analizados. Tres coincidencias correspondían a UUID de idempotencia documentados/de prueba, no credenciales. Se conservan excepciones por huella exacta en `.gitleaksignore`; tras clasificarlas no quedaron coincidencias pendientes. Las nuevas confirmaciones se vuelven a escanear en CI.
- Bandit 1.9.4: 38 coincidencias revisadas individualmente en `bandit-revisado.json`. Predominan SQL con identificadores internos y valores parametrizados, importación de subprocess y construcción de XML de exportación. No se desactivaron reglas globales: una coincidencia nueva o con contexto de código distinto hace fallar la revisión. Esto es una revisión de alcance limitado, no una prueba de inexistencia de inyección en todo contexto posible.
- No se incluyeron credenciales reales ni bases del negocio en los ensayos o en la entrega.

### Publicación de pruebas: antes y después

El HTTPS existente validó su certificado y las consultas anónimas o con una sesión falsa devolvieron 401 sin campos financieros. Sin embargo, HTTP devolvía 200 sin redirigir y faltaban HSTS/otras cabeceras. Tras el despliegue, las cinco consultas verificaron los estados 200 (página HTTPS), 308 (HTTP a HTTPS), 401, 401 y 401 (datos protegidos), y las cabeceras HSTS, CSP, DENY, nosniff, Referrer-Policy y Permissions-Policy. No se realizaron intentos de contraseña ni modificaciones de usuarios, ventas o productos durante esas consultas. Esta comprobación no demuestra que todas las rutas y controles de la cuenta estén auditados.

## Rendimiento y capacidad comprobados

Medición de referencia local con datos ficticios: 2,000 productos, 10,000 lotes, 180 ventas y 12,000 eventos de auditoría. Mediana de búsqueda: 0.964 ms; preparación de instantánea: 302.942 ms; huellas históricas: 235.623 ms y pico de memoria medido de 278,758 bytes en esa operación. No representa el consumo total de Qt, del POS ni del sistema operativo.

Carga HTTP con ocho clientes: 192 solicitudes de cobro para 96 ventas únicas, repitiendo claves. Resultado: cero ventas duplicadas, 192,000 centavos cobrados, stock final 904 de 1,000 unidades, integridad SQLite correcta y sin claves foráneas rotas. Tiempo total 3.647 s; mediana de latencia 145.642 ms, percentil 95 de 171.310 ms y máximo 716.133 ms. Resultados de esta computadora y este escenario; no son un SLA ni capacidad garantizada en el equipo antiguo.

Las pruebas centrales conservan la réplica de más de 2 MB y 7,000 productos, envíos incompletos/corruptos, reintento, retención y separación por sucursal. No se midió carga ilimitada, múltiples propietarios ni consumo real de cuotas gratuitas. El diseño utiliza una cuenta/base separada por negocio y claves distintas por sucursal; no es una plataforma pública multitenant compartida entre clientes independientes.

## Matriz de los 20 puntos consultados

| Control | Estado dentro del alcance |
| --- | --- |
| Claves del servidor fuera del frontend | Implementado; claves centrales del servidor y DPAPI para vinculación local. Una clave de sucursal se muestra al propietario al crearla para su instalación. |
| Secretos en Git | Escaneo especializado del historial y CI; excepciones exactas justificadas, no una exclusión general de tests o documentación. |
| Clave pública de base | No aplica: el frontend no accede directamente a SQLite/D1. |
| RLS | No aplica literalmente a esta arquitectura. Se comprueban permisos en servidor y separación entre claves/sucursales; no se afirma RLS nativa. |
| Cifrado de datos sensibles en disco | Requisito de despliegue pendiente: SQLite y JSON de respaldo no están cifrados por la aplicación. DPAPI protege claves, no toda la base. Ver medidas obligatorias abajo. |
| Autenticación | Probada para rutas protegidas, claves de sucursal y sesiones; no se habilita acceso anónimo a datos. |
| Acceso a registros | Comprobado por permisos e identidad de sucursal en los escenarios revisados; historial global requiere reports.view. |
| Manipulación de campos | Validación en servidor y reglas transaccionales; pruebas de importes, stock, idempotencia y entradas hostiles. |
| Cookies | Sesiones centrales Secure/HttpOnly/SameSite con vencimiento y revocación; cookies locales HttpOnly/SameSite en loopback. |
| Hash de contraseñas | PBKDF2 con sal local; claves centrales aleatorias de alta entropía almacenadas como hash. No se muestran contraseñas originales. |
| Rate limiting | Login acotado por usuario/IP según componente; conexiones locales acotadas. No existe una garantía de límites distribuidos globales para toda la infraestructura. |
| Bots | Rechazo de sesiones/claves y control de intentos; no CAPTCHA/Turnstile ni WAF de cuenta auditado. Protección distribuida depende del proveedor y del despliegue. |
| SQL parametrizado | Revisión de consultas y listas internas para identificadores; pruebas hostiles; alertas estáticas clasificadas. |
| Validación | Tipos, límites, formatos y coherencia financiera; existen pruebas de rechazo. No equivale a cubrir toda combinación imaginable. |
| Contenido | Escape en vistas, CSP, JSON con tipo correcto y protección de fórmulas CSV revisados; no se afirma pentest independiente completo de XSS. |
| Archivos | Listas de rutas, tipos y límites; validación PNG/respaldos y parser XML endurecido. No es un antivirus de archivos. |
| Minimización de respuestas | Permisos de costos, omisión de credenciales y panel de consulta; backup completo contiene datos por diseño y exige backup.manage. |
| Cabeceras | Pruebas locales del Worker sobre éxito/rechazo; comprobar su aplicación después de publicar en la cuenta real. |
| HTTPS | Forzado por Worker y sincronización HTTPS sin redirecciones externas. Loopback interno no usa TLS; LAN HTTP opcional exige red confiable o desactivarlo. |
| Dependencias | Escáneres reproducibles y en CI; avisos conocidos corregidos a la fecha. No cubren por sí solos todas las vulnerabilidades de Windows, Qt, OpenSSL o firmware. |

## Riesgos residuales y aceptación de despliegue

1. **Datos en disco:** cifrar el disco del equipo y el medio externo con una solución del sistema operativo, proteger la cuenta de Windows y resguardar las claves de recuperación fuera del equipo. No guardar respaldos JSON en servicios/carpetas compartidas sin protección. No se afirma que el archivo sea cifrado por tener SHA-256: la huella solo verifica integridad accidental.
2. **Publicación real:** HTTPS/cabeceras y rechazo anónimo se comprobaron en el sitio de pruebas indicado. Quedan por verificar con el propietario el inicio/cierre de sesión legítimo y la recepción de su sucursal; activar MFA en las cuentas de Cloudflare y GitHub y no reutilizar la contraseña de prueba `12345678`. No se cambiaron ni inspeccionaron esas opciones privadas de las cuentas en esta evaluación. Otros clientes y dominios requieren su propia comprobación.
3. **Disponibilidad:** internet, disco, energía, impresora y dispositivo antiguo requieren piloto. Una prueba finita no demuestra escalabilidad sin límites. Documentos de sincronización tienen límite de 16 MB y la nube conserva sus cuotas y tiempos máximos. Mantener aviso de datos pendientes y respaldo restaurable fuera del equipo.
4. **Autenticación del personal:** usar contraseñas únicas y largas; los PIN cortos y una sesión Windows compartida tienen riesgo residual. Esta versión no incorpora MFA dentro del POS ni convierte un sistema operativo comprometido en seguro.
5. **Verificación externa:** quedan fuera la auditoría independiente, certificación contractual, pruebas destructivas de la cuenta publicada, ataque distribuido, cifrado/configuración real de la computadora de caja y validación fiscal real con PAC.

La entrega reduce los riesgos identificados y conserva evidencia reproducible. No declara «cero fallas», «seguridad al 100 %» ni «todos los controles certificados». Cambiar dependencias, entorno o volumen obliga a reevaluar los resultados.
