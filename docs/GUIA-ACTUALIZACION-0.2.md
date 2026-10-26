# Actualizar LunaDev POS a 0.2.0-rc.2

Esta entrega corrige permisos, reintentos, cortes cerrados, transporte de documentos grandes y respaldos externos. Es una candidata para validación operativa; no afirma ausencia absoluta de errores ni habilita facturación fiscal real.

La revisión del 26 de octubre añade motor Python 3.14.10, dependencias corregidas, XML endurecido, límites de conexiones y cabeceras HTTPS del panel. No cambia el esquema 11 ni borra datos. Conserva los permisos y las funciones de negocio. Revisa el informe AUDITORIA-SEGURIDAD.md de la entrega: el cifrado del disco y de medios de respaldo, las cuentas de Windows/Cloudflare y la configuración real de publicación siguen siendo requisitos de instalación; la base y los JSON no se cifran por la aplicación.

1. Termina los turnos, exporta un respaldo completo desde Mantenimiento y guárdalo fuera del equipo. Conserva también el instalador anterior.
2. Actualiza PRIMERO la página central: copia el contenido del asistente nuevo sobre tu carpeta de publicación existente. Conserva CONFIGURADO.json, wrangler.json, .config-cloudflare y DATOS-PRIVADOS. Ejecuta Actualizar-pagina.cmd en esa misma carpeta: instala automáticamente las dependencias fijadas por la nueva entrega, incluso si ya tenías node_modules. Requiere Node.js LTS e internet en la computadora de configuración. Aplica una migración aditiva; no crea otra cuenta, base ni enlace.
3. Cierra LunaDev POS y ejecuta Instalar-LunaDevPOS.exe, eligiendo actualizar conservando datos. La base se migra a versión 11 y se guarda una copia SQLite previa a la migración. Los respaldos antiguos de versiones 2 a 10 se siguen admitiendo.
4. La versión anterior NO abre una base ya migrada a 11. Para volver atrás, usa la instalación anterior con el respaldo PREVIO a actualizar; no fuerces versiones ni borres tablas.
5. En Administración → Mantenimiento configura el respaldo externo mediante Elegir carpeta y Guardar destino. Elige una USB o disco distinto, no otra carpeta del mismo disco. Comprueba la copia del último turno. Las copias automáticas propias tienen retención de 30 días; las exportaciones manuales no se borran.
6. Si aparece Operación pendiente de comprobar, pulsa Comprobar. Si ya se registró, recupera el resultado original. Reintentar usa la misma clave. Cancelar comprueba primero el registro y, si no existe, impide una confirmación tardía. No vuelvas a cobrar por fuera sin aclarar el resultado.
7. El vendedor usa Historial de tickets para sus ventas; Historial general y sus descargas requieren permiso de informes. El administrador conserva la consulta completa y el control de permisos.
8. Abre la página del dueño, recárgala una vez y verifica la fecha de recepción de cada local. Un envío incompleto conserva la copia anterior y no publica bloques sueltos. Los errores se reintentan; cuotas del proveedor o documentos superiores a 16 MB requieren atención, no se presenta un total parcial como completo.
9. Realiza un piloto con caja física y restaura una copia en una instalación aislada. Las pruebas automatizadas no sustituyen esa comprobación.

La página central sigue siendo de consulta. No se incluyeron credenciales, inventario ni datos de prueba en el instalador. La configuración del destino externo es local a cada computadora y debe revisarse al reinstalar o restaurar en otra máquina.

La facturación sigue claramente identificada como entorno de pruebas. Emitir CFDI reales requiere cuenta del proveedor, datos fiscales y validación externa; no se activó emisión real con credenciales ficticias.
