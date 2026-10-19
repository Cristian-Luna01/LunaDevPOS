# Optimización de LunaDev POS — 18 de octubre de 2026

## Respaldo y control de versiones

Estado anterior: `fe26db6`, conservado en la rama `respaldo/antes-optimizacion-2026-10-18` del repositorio privado y en `respaldo-LunaDevPOS-antes-optimizacion-2026-10-18.zip` del espacio de trabajo. Las mejoras se mantienen en `optimizacion/equipos-basicos`; main conserva el estado previo.

## Qué se revisó y qué cambió

Se revisaron las rutas del mostrador, consultas de productos/existencias, costos y reportes, reparto de abonos, sincronización de sucursales, representación del panel local y central, actualizaciones periódicas, respaldo/restauración y empaquetado de escritorio.

- Índices auxiliares para encontrar los lotes de un producto, su último costo y las relaciones de devoluciones. Se agregan al abrir una base anterior; no cambian registros ni el formato de los respaldos.
- El buscador primero selecciona sus 40 coincidencias y suma únicamente los lotes de esos productos; conserva orden, permisos, páginas y tratamiento de caducados.
- La sincronización reutiliza el catálogo ya calculado, en lugar de sumar dos veces todas las existencias.
- Las verificaciones del historial se calculan fila por fila, sin mantener todas las filas históricas en listas. Las huellas son idénticas a las anteriores.
- Los informes reutilizan el reparto de abonos ya calculado dentro de la misma consulta. No hay caché persistente de importes ni cambios de redondeo.
- Dirección local y central evitan sustituir seis bloques de tarjetas si su contenido sigue igual. Se mantiene la actualización de diez segundos, la navegación y el desplazamiento.

Se conservaron transacciones, validaciones, permisos, seguridad de contraseñas y escritura segura en disco. Los cambios no eliminan históricos, productos ni funciones. No se sustituyó el motor gráfico del escritorio.

## Medición reproducible

Datos ficticios aislados: 2,000 productos, 10,000 lotes, 180 ventas distribuidas en 180 días y 12,000 anotaciones de ajuste. Mediana de tres ejecuciones por operación, en la computadora de desarrollo. La memoria es el pico de asignaciones Python medido con tracemalloc para las huellas, no la RAM de todo el programa.

| Operación | Antes | Después |
|---|---:|---:|
| Preparar datos de sucursal | 2943.933 ms | 120.936 ms |
| Buscar un código en ese catálogo | 3.886 ms | 0.522 ms |
| Pico de memoria de huellas | 6,706,412 bytes | 278,758 bytes |
| Tiempo de cálculo de huellas | 53.957 ms | 75.115 ms |

El cálculo aislado de huellas sacrifica algo de tiempo a cambio de reducir mucho la memoria; la preparación completa de datos sigue siendo considerablemente más rápida. Los resultados completos de la sincronización y de la búsqueda coincidieron exactamente entre ambas versiones (SHA-256, excluyendo únicamente la hora de generación).

Estas cifras no representan el consumo total de RAM ni garantizan el mismo tiempo en un equipo antiguo. El motor gráfico incluido sigue siendo una parte importante del peso y consumo del programa. La mejora principal está en CPU, consultas y memoria de trabajo; el instalador no se convierte en una aplicación diminuta.

Para repetir la comparación: ejecutar `herramientas/Medir-rendimiento.py --source RUTA/punto-de-venta --output medicion.json` con Python, primero sobre el respaldo y luego sobre esta rama. El script crea y elimina exclusivamente su base ficticia temporal. No utilizar una base real como sustituto de la prueba.

## Verificación

- 211 pruebas Python aprobadas: ventas, impuestos, descuentos, promociones, créditos/abonos, cambios, devoluciones, caja, inventario, permisos, respaldos, facturación de prueba, tickets y sincronización.
- 26 pruebas JavaScript aprobadas, incluyendo 3,000 combinaciones de descuentos/promociones y conservación de tarjetas idénticas.
- Pruebas nuevas comparan la consulta antigua y la nueva con caducados, productos sin lotes, coincidencias, paginación y permisos de costos. Verifican huellas idénticas, integridad de la base e instalación repetible de índices sin cambiar datos.
- En la página local de prueba se comprobó inicio de sesión, inventario y permanencia en Inventario a 1,440 píxeles de desplazamiento después de varias actualizaciones automáticas.
- Ejecutable generado: prueba interna y carga del motor gráfico correctas, sobre carpetas aisladas.

No es una prueba física de la computadora AMD de 4 GB, la terminal, el lector ni la impresora. Se recomienda comparar el piloto en ese equipo con el respaldo conservado. No se afirma ausencia absoluta de errores.

## Instalar y actualizar la página

1. Exporta un respaldo completo de los datos, termina el turno y cierra el programa.
2. Ejecuta `Instalar-LunaDevPOS-Optimizado.exe` y elige instalar/actualizar conservando datos. No elijas empezar de cero.
3. Para la página central, usa `Actualizar-pagina.cmd` del asistente actualizado en la misma carpeta de despliegue que ya utilizabas, conservando sus archivos privados de configuración y la misma cuenta de Cloudflare. No crees otra página ni otras claves.
4. Recarga una vez la página del dueño tras publicarla.

La instalación existente y la página publicada no se sustituyen automáticamente al preparar este paquete. El kit no incluye cuentas, inventario ni claves privadas. El respaldo del código no sustituye al respaldo de los datos del negocio.
