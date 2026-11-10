# Firma local de LunaDev POS — solo desarrollo

Haz doble clic en **Firmar-copia.cmd**. En la entrega del Escritorio, pulsa **Enter** para elegir el POS compilado. Si quieres firmar otro archivo, pega solo su ruta completa o arrástralo sobre el CMD. El asistente crea una copia firmada y un informe en **salidas**. No necesita el SDK de Windows ni permisos de administrador.

- Si eliges **Instalar-LunaDevPOS.exe**, la firma cubre solo el instalador exterior; no modifica los ejecutables que contiene. Para probar la firma del programa, elige **LunaDevPOS.exe** dentro de **Ejecutable-compilado**. El asistente copia también **_internal**, que trae Python y Qt. Conserva esa carpeta al lado del EXE firmado. La copia no trae una base de datos; si pruebas el arranque, especifica una carpeta de datos aislada con `--data-dir`, porque el programa normalmente busca los datos del POS instalado.
- Crea un certificado temporal de firma en el almacén personal del usuario, firma la copia y elimina el certificado y su clave privada al terminar. No añade confianza a Windows, no cambia el antivirus y no toca el POS instalado ni los datos.
- Windows puede mostrar **NotTrusted** o **UnknownError** indicando que la cadena no es de confianza. Que se vea un firmante en el archivo no significa que Smart App Control lo acepte.
- El lanzador usa la política **RemoteSigned** solo en el proceso que ejecuta el script. Si Windows o la política de tu equipo impiden ejecutarlo, el asistente no cambia esas protecciones.

Para distribuir el POS a clientes, usa un MSIX firmado por Microsoft Store o una firma de código de confianza pública para los ejecutables de descarga directa. [Requisitos de Smart App Control](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control).
