# Receta vigente de distribución

Windows x64, Python 3.12. En un entorno virtual limpio instala `punto-de-venta/requirements-build.lock`, ejecuta `herramientas/Preparar-conector.ps1` para verificar el conector oficial y luego `python herramientas/Compilar.py --output dist`. La receta construye LunaDevPOS.spec, Desinstalar-LunaDevPOS.spec e Instalar-LunaDevPOS.spec; prepara el contenido, copia avisos de dependencias y genera SHA256.json. El repositorio no incluye bases, claves ni binarios compilados.

Los demás .spec son recetas históricas conservadas para trazabilidad; no son entradas de compilación para esta versión. No se cambia su arquitectura ni se presenta el ejecutable x64 como compatible con Windows de 32 bits.

Antes de distribuir, ejecutar herramientas/Verificar.ps1 y las pruebas internas del instalador en una carpeta aislada. El flujo .github/workflows/verificar.yml ejecuta también las nuevas pruebas de recuperación y transporte. El resultado de GitHub debe estar aprobado para la revisión publicada.

La ventana usa Qt WebEngine incluido; no abre un navegador externo. El mostrador conserva la base local SQLite y opera sin la página del dueño. Los respaldos automáticos no son una réplica fiscal ni sustituyen una copia fuera del equipo.

Los avisos y licencias de dependencias se incluyen en licenses/. La disponibilidad de código propio no concede derechos adicionales sobre componentes de terceros.
