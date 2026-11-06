# Validar la caja con el equipo real

Esta hoja complementa las pruebas automáticas. Todavía requiere ejecución por
la persona que tiene la impresora y el escáner. Registra fecha, equipo, versión
de Windows, modelo del periférico y resultado de cada paso.

## Preparación

1. Utiliza la copia de pruebas o una carpeta nueva mediante `--data-dir`.
2. Crea un administrador y un cajero ficticios; registra dos productos de prueba.
3. Abre Mantenimiento → Comprobar impresora y escáner. Esta pantalla no registra ventas.

## Escáner USB

- Escanea el mismo código diez veces. Cada lectura debe aparecer completa y una sola vez.
- Alterna dos códigos y verifica el orden y las cantidades.
- Escanea un código inexistente: debe informar el problema y aceptar el siguiente.
- Escribe un nombre lentamente: no debe interpretarlo como una lectura de escáner.
- Abre un formulario y captura datos: el lector no debe modificar el carrito.

## Impresora

- Imprime el ticket de prueba en 58 mm y, si corresponde, en 80 mm.
- Comprueba acentos, nombre, código, importes, cambio, márgenes y corte del papel.
- Imprime una venta ficticia y reimprime el mismo ticket. No debe generarse otra venta.
- Con la impresora desconectada, confirma una venta ficticia; vuelve a conectarla
  y reimprime el ticket existente. El papel y la venta son operaciones distintas.

## Respuesta perdida y reinicio

- Las pruebas automáticas ya simulan una respuesta perdida después de confirmar.
- En una caja de prueba, cierra forzosamente el proceso durante un cobro y vuelve
  a abrir la misma carpeta de datos. Revisa Operación pendiente de verificar.
- Usa Recuperar resultado. Debe conservarse el mismo ticket, una sola salida de
  inventario y el mismo total. Si nunca se confirmó y el turno terminó, la
  recuperación debe rechazar el envío y permitir descartar la solicitud.
- Registra el número de ticket, las unidades anteriores y posteriores, y el corte.

## Energía y almacenamiento

Las pruebas automáticas terminan un proceso durante una transacción y verifican
rollback e integridad SQLite. Esto no certifica el comportamiento eléctrico del
disco, del controlador ni del equipo.

Para un ensayo de pérdida de energía utiliza exclusivamente un equipo y una base
de prueba, con respaldo externo comprobado. Después del reinicio verifica acceso,
operaciones pendientes, existencias y corte. Para uso habitual conviene una UPS
que permita cerrar el programa y apagar el sistema.

## Respaldos

1. Selecciona la carpeta de USB, otro disco o sincronización en Mantenimiento →
   Respaldos automáticos externos.
2. Usa Respaldar y comprobar restauración. Debe finalizar con restauración correcta.
3. Desconecta la unidad y solicita otra copia: debe informar que no se pudo guardar;
   el mostrador debe seguir funcionando.
4. Reconecta y repite. Conserva también una copia fuera del local cuando proceda.
5. Si usas una carpeta sincronizada, confirma en el proveedor que el archivo terminó
   de subir. La aplicación comprueba el archivo local, no la sincronización del proveedor.

## Registro

| Comprobación | Resultado | Fecha / observaciones |
|---|---|---|
| Escáner: secuencia y cantidades | Pendiente presencial | |
| Impresión 58 mm | Pendiente presencial | |
| Impresión 80 mm, si se usa | Pendiente presencial | |
| Reimpresión sin nueva venta | Pendiente presencial | |
| Reinicio de la caja real | Pendiente presencial | |
| Energía / UPS | Pendiente presencial | |
| Carpeta de respaldo y restauración | Configurada; prueba ficticia aprobada | Validar también con la cuenta real de pruebas |
