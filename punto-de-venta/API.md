# API local y ejemplos

Promociones: GET `/api/promotions` para consultar; POST `/api/promotions/save` requiere `products.edit` y recibe `product_id`, `name`, `price_cents`, `starts_on`, `ends_on`. Para desactivar: `product_id` y `disable:true`. Una promoción por producto. La venta aplica el menor total entre promoción vigente y descuento del cliente, sin acumulación. El precio se valida nuevamente en la transacción de venta.

Historial y corte agregan `cost_cents`, `tax_cents`, `profit_cents` y `zero_cost_units` solo con permiso `costs.view`. El costo procede de las asignaciones históricas de lotes. CSV conserva importes en pesos.

Historial: GET `/api/sales/history?from=YYYY-MM-DD&to=YYYY-MM-DD` para usuarios con `sell` o `reports.view`. CSV: misma ruta terminada en `.csv`; `summary=1` exporta totales diarios. Dirección usa `/direccion/api/history`, `/direccion/api/history.csv` y `/direccion/api/metrics`, con su cookie independiente y permisos de Dirección. Los CSV presentan pesos; los JSON conservan centavos. Se admiten hasta 366 días por consulta.

POST `/api/logout` devuelve 409 si existe un turno abierto del usuario; debe cerrarlo con el conteo primero. La sesión de Dirección no está sujeta a esa restricción porque no opera caja.

Todas las cantidades monetarias son centavos y las cantidades de inventario son unidades enteras. Las rutas de escritura usan POST con JSON, cookie de sesión y `X-POS-Request: 1`. El navegador añade Origin; el servidor solo admite su mismo origen local. No se habilita acceso entre orígenes.

## Rutas

| Método y ruta | Uso / permiso |
|---|---|
| POST `/api/login` | `{username, secret}`; establece sesión |
| POST `/api/logout` | Invalida sesión |
| GET `/api/me` | Usuario, permisos y turno propio sin saldo esperado |
| POST `/api/users/save` | Crear/editar, `{id?,username,display_name,secret,active,permissions:[]}`; `users.manage` |
| GET `/api/users` | Usuarios sin hashes; `users.manage` |
| GET `/api/categories` | Departamentos iniciales |
| GET `/api/products?q=&offset=0` | Búsqueda acotada de productos activos; costos/margen solo con `costs.view` |
| POST `/api/products/save` | Crear/editar producto; `products.create` / `products.edit` |
| POST `/api/products/deactivate` | `{id}`; `products.delete` |
| GET `/api/suppliers` | Directorio de proveedores, máximo 200 |
| POST `/api/suppliers/save` | `{id?,business_name,contact,phone,credit_days}`; `suppliers.manage` |
| GET `/api/customers?q=` | Buscar nombre/teléfono; lista completa para selección |
| POST `/api/customers/save` | `{id?,name,phone,discount_bps}`; `customers.manage` |
| GET `/api/customers/history?id=1` | Últimas 100 compras; `reports.view` |
| POST `/api/inventory/receive` | Recepción con lote y costo; `inventory.receive` |
| POST `/api/inventory/adjust` | Conteo con control de concurrencia; `inventory.adjust` |
| GET `/api/inventory/batches?product_id=1` | Hasta 200 lotes; costos sujetos a permiso |
| GET `/api/inventory/kardex?product_id=1` | Últimos 200 movimientos |
| GET `/api/inventory/alerts` | Hasta 200 lotes caducados o por vencer en 90 días |
| POST `/api/shifts/open` | Apertura propia; `sell` |
| POST `/api/cash` | Entrada o salida; `cash.in` / `cash.out` |
| GET `/api/shifts/report?id=1` | Corte X con `reports.view`; corte Z propio disponible tras cierre |
| POST `/api/shifts/close` | Declarar conteo y cerrar turno propio; `sell` |
| GET `/api/reports/general?from_id=1&to_id=100` | Consolidación de hasta 366 turnos; `reports.view` |
| POST `/api/sales` | Confirmar venta; `sell` |
| GET `/api/ticket?id=1` | Ticket propio o acceso mediante reportes/devoluciones/anulación |
| POST `/api/returns` | Devolver (`sales.return`) o anular (`sales.void`) |

El esquema de campos completos está en el DDL. Los formularios de administración proporcionan ejemplos ejecutables de las escrituras. Listados con tope fijo son consultas operativas recientes, no exportaciones completas.

## Ejemplo: apertura y salida a proveedor

POST `/api/shifts/open`

```json
{"shift_number":1,"opening_cents":50000}
```

POST `/api/cash`

```json
{
  "direction":"out",
  "category":"supplier",
  "amount_cents":10000,
  "supplier_id":1,
  "invoice_ref":"FACT-2026-001",
  "concept":"Abono de mercancía"
}
```

Categorías: `change` exclusivamente para entrada, `supplier`, `expense` o `safekeeping` para salida. Proveedor y folio son obligatorios cuando la categoría es `supplier`.

## Ejemplo: venta mixta

Suponiendo dos unidades de $50 y ningún descuento:

```json
{
  "request_key":"a4b09684-38c6-439a-baf8-bd81c8b092fd",
  "customer_id":null,
  "items":[{"product_id":1,"quantity":2}],
  "payments":[
    {"method":"cash","amount_cents":4000,"tendered_cents":5000},
    {"method":"transfer","amount_cents":6000,"reference":"BANCO-001"}
  ]
}
```

Aplicado: $100. Efectivo recibido: $50. Cambio: $10. Efectivo añadido a caja: $40. Los métodos válidos son `cash`, `debit`, `credit`, `transfer`; máximo una entrada por método. Si el descuento de un cliente cambia el total, los pagos deben coincidir con el nuevo importe. Una venta con descuento de 100% admite un arreglo de pagos vacío.

Para un producto que requiere receta, agrega a su partida:

```json
{
  "product_id":1,
  "quantity":1,
  "prescription":{
    "doctor_name":"Nombre del médico",
    "license_number":"Cédula",
    "prescription_ref":"Folio"
  }
}
```

## Ejemplo: recepción y ajuste

POST `/api/inventory/receive`

```json
{
  "product_id":1,"supplier_id":1,"lot_number":"L-001",
  "expires_on":"2028-04-30","quantity":30,"unit_cost_cents":3000,
  "reason":"Recepción factura FACT-001"
}
```

POST `/api/inventory/adjust`

```json
{"batch_id":1,"expected_quantity":30,"counted_quantity":28,"reason":"Merma: dos empaques rotos"}
```

Si la existencia actual dejó de ser 30, el ajuste devuelve 409; el operador debe revisar el nuevo estado. No repitas a ciegas recepciones o movimientos de efectivo después de una respuesta incierta: estas rutas exigen request_key; el diario de operaciones permite comprobarlas. Consulta el registro antes de reenviar.

## Ejemplo: corte Z

POST `/api/shifts/close`

```json
{"shift_id":1,"counted_cents":43950}
```

El resultado incluye `opening_cents`, `sales_by_method`, `refunds_by_method`, `incoming_cents`, `outgoing_cents`, `expected_cents`, `counted_cents`, `difference_cents`, `departments` y `movements`. El servidor recibe primero el conteo y solo entrega estos datos al confirmar el cierre.

## Ejemplo: devolución parcial

POST `/api/returns`

```json
{
  "request_key":"2deeb3ca-32ae-42a1-91d5-0c6d3e3ea860",
  "sale_id":1,"kind":"return","reason":"Devolución autorizada",
  "items":[{"sale_item_id":1,"quantity":1,"disposition":"restock"}]
}
```

La partida es su ID histórico, no el ID del producto. `quarantine` sustituye a `restock` para mantener el producto fuera del inventario vendible. Para anular todo el ticket, usa `kind:"void"` y omite `items`; se requiere `sales.void` y la venta no debe tener devoluciones previas.

## Errores

`400`: datos o importes inválidos. `401`: falta sesión válida. `403`: permiso/origen no autorizado. `404`: registro o ruta inexistente. `409`: conflicto de estado, stock insuficiente, duplicidad o clave reutilizada. `429`: intentos de acceso excesivos. `503`: base ocupada/no disponible. Un error en una escritura transaccional revierte la operación completa.

Ante una respuesta perdida, reintenta ventas/devoluciones con **la misma clave y el mismo contenido**. Nunca generes otra clave para resolver incertidumbre sobre si una operación anterior se confirmó.


## Importación y respaldos (versión 2)

- POST `/api/inventory/import/preview`: `{file_base64, selection: "positive"|"numeric", tax_bps}`. Retorna resumen, incidencias, productos y revisión. Permiso `inventory.import`.
- POST `/api/inventory/import/confirm`: agrega `revision`, `request_key`, `existing: "skip"|"replace"`, `excluded_rows: []` y `skip_invalid: boolean`. La clave y el cuerpo deben repetirse sin cambios ante respuesta incierta.
- GET `/api/inventory/export?format=json|csv|xls`: descarga con Content-Disposition. Permiso `inventory.export`, que incluye acceso a costos exportados.
- GET `/api/backup/export`: respaldo lógico completo. Permiso `backup.manage`.
- POST `/api/backup/preview`: `{file_base64}`; valida formato/huella y muestra conteos y elegibilidad del destino.
- POST `/api/backup/restore`: agrega `confirmation: "RESTAURAR"`; solo destino vacío; requiere volver a iniciar sesión.
- GET `/api/inventory/undated`: lista hasta 200 lotes con stock sin fecha.
- POST `/api/inventory/batch/edit`: `{batch_id, lot_number?, expires_on?, reason}`; permiso `inventory.adjust`.

Los archivos admiten hasta 64 MB antes de codificar a base64 y la importación admite hasta 50,000 registros. Los respaldos Botica actuales son versión 12 (incluyen el aviso de privacidad; se conservan las importaciones de versiones anteriores); el inventario JSON usa formato botica-inventory, versión 1. En recepción, proveedor, lote y expires_on ahora son opcionales; fecha vacía se guarda como NULL.

Historial general, CSV y Excel requieren reports.view. Las rutas /api/cash, /api/inventory/restock y /api/inventory/receive exigen request_key. /api/operations/prepare, pending, ack y cancel permiten recuperar o cancelar el mismo intento de forma durable y aislada por usuario. Las cancelaciones no borran operaciones ya confirmadas.
