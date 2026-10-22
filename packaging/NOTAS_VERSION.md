## TurbuLENS 1.1.0

Descarga el archivo de tu sistema, descomprímelo y abre TurbuLENS: no hay que instalar nada más.

| Sistema | Archivo |
|---|---|
| Windows 10/11 (64 bits) | `TurbuLENS-v1.1.0-Windows-x64.zip` |
| Mac con Apple Silicon (M1, M2, M3, M4…) | `TurbuLENS-v1.1.0-macOS-AppleSilicon.zip` |
| Mac con Intel | `TurbuLENS-v1.1.0-macOS-Intel.zip` |
| Linux (64 bits) | `TurbuLENS-v1.1.0-Linux-x64.tar.gz` |

**Novedades**
- **Animación de los centroides** en Resultados: cuadro a cuadro se ve dónde ubicó TurbuLENS cada punto, la distancia medida y el rastro de las posiciones anteriores. También se guarda en el historial.
- **Linux corregido:** el programa ya no se cierra con el error «xcb-cursor0 or libxcb-cursor0 is needed»; las bibliotecas necesarias vienen dentro del ejecutable. Si no hay X11, intenta con Wayland.
- Cada ejecutable se prueba en GitHub abriendo la **ventana real** en Windows, macOS y en un Linux sin esas bibliotecas.
- **Nueva licencia: PolyForm Noncommercial 1.0.0.** Uso libre sin fines comerciales; toda copia o versión modificada debe conservar el crédito al autor. La cita (APA y BibTeX) está en *Acerca de*, en `CITATION.cff` y en el pie de informes y gráficas.

El programa no está firmado digitalmente: la primera vez Windows o macOS pedirán confirmación (ver LEEME.txt).
