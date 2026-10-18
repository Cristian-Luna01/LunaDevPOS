# Dirección y logotipo

Ventas y caja muestra los mismos seis importes del historial para hoy: venta total de productos, ganancia de productos, total antes de devoluciones, devoluciones y anulaciones, costo de compra de lo vendido y tickets registrados. Se actualiza cada 10 segundos mientras Dirección esté abierta y visible. Los costos y ganancias requieren permiso de ver costos; no se muestran como cero si el usuario carece del permiso.

Entra como administradora y abre «Menú → Configuración → Subir logotipo». Selecciona un PNG de hasta 2 MB y hasta 4096 × 4096 píxeles. Se conserva la transparencia, se comparte entre Mostrador y Dirección y aparece al volver a abrir la otra pantalla. Puedes cambiarlo o quitarlo desde Configuración. Se requiere permiso de administrar usuarios.

El respaldo completo incluye el logotipo; exportar solo inventario no lo incluye. La base y los respaldos nuevos usan versión 6. Se restauran también los respaldos 2, 3, 4 y 5. Al actualizar conserva data y haz primero un respaldo completo.

# Instalador Windows: pendiente

Este ZIP aún requiere el inicio actual. El siguiente trabajo es empaquetar el programa y Python en un ejecutable Windows, crear un instalador con accesos directos, guardar datos en una carpeta persistente separada del programa y comprobar instalación, actualización y desinstalación sin pérdida de información. Si se quiere una ventana propia en lugar de pestaña, también hay que integrar esa ventana y sustituir la configuración inicial que hoy pide datos en consola. PyInstaller es una opción para empaquetar Python: https://pyinstaller.org/en/stable/usage.html

# Dirección desde el teléfono: pendiente

Actualmente el servidor solo admite conexiones locales. Instalar Tailscale por sí solo no lo habilita: falta adaptar y probar los nombres de servidor permitidos, HTTPS y sesiones, y restringir el acceso remoto a Dirección y sus recursos.

La opción propuesta es una red privada Tailscale entre la PC de la farmacia y el teléfono de la administradora, con HTTPS mediante Tailscale Serve, acceso limitado a sus dispositivos y un usuario propio de Dirección. Consultaría la misma base, con actualización cada 10 segundos. La PC y el programa deben permanecer encendidos, sin suspensión y con Internet. No requiere duplicar el inventario. Referencia: https://tailscale.com/docs/features/tailscale-serve

Si se necesita consultar con la PC apagada, hace falta un servidor siempre disponible y sincronización, incluyendo manejo de ventas sin Internet y conflictos. Los avisos con el panel cerrado requieren además notificaciones push; todavía no están implementados.

