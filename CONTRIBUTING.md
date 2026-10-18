# Desarrollo y cambios

1. Crea una rama desde `main`, por ejemplo `fix/cobro` o `feat/inventario`.
2. Trabaja con una base de datos ficticia y una carpeta de datos independiente.
3. Conserva los importes en centavos enteros. No recalcules ventas históricas con precios o costos actuales.
4. Agrega pruebas cuando cambies cobros, redondeos, crédito, stock o persistencia.
5. Ejecuta las pruebas y revisa la sincronización del panel antes de integrar.
6. Actualiza CHANGELOG y VERSION al preparar otra entrega. Publica los binarios en Releases.

Antes de las pruebas, ejecuta `herramientas/Preparar-conector.ps1` desde la raíz. Descarga el conector oficial y verifica su SHA256. El ejecutable queda ignorado por Git.

Pruebas del punto de venta, dentro de `punto-de-venta`:

```powershell
python -m pip install -r requirements-test.txt
python -m unittest discover -s . -p "test_*.py"
node --test test_direction_responses.js test_financial_ui.js
```

Pruebas del panel, dentro de `pagina-administrador`:

```powershell
npm ci
npm test
```

Ejecuta `herramientas/Verificar.ps1` para recorrer las pruebas. La plantilla opcional de GitHub Actions no está activada.

Nunca incluyas bases de datos, respaldos, tokens, contraseñas, certificados fiscales, archivos privados del asistente ni identificadores de clientes en un commit o una captura.
