## TurbuLENS 1.4.0

Descarga el archivo de tu sistema, descomprímelo y abre TurbuLENS: no hay que instalar nada más. Funciona en **español, inglés y portugués**.

| Sistema | Archivo | Se abre con |
|---|---|---|
| Windows 10/11 (64 bits) | `TurbuLENS-v1.4.0-Windows-x64.zip` | `TurbuLENS.exe` |
| Mac con Apple Silicon (M1, M2, M3, M4…) | `TurbuLENS-v1.4.0-macOS-AppleSilicon.zip` | `TurbuLENS.app` |
| Mac con Intel | `TurbuLENS-v1.4.0-macOS-Intel.zip` | `TurbuLENS.app` |
| Linux (64 bits) | `TurbuLENS-v1.4.0-Linux-x64.tar.gz` | `TurbuLENS` |

**Nuevo**
- **Calibración guiada por las cabeceras** (modo Imágenes): agrega imágenes sueltas o **carpetas completas** (con subcarpetas). TurbuLENS lee la cabecera de cada archivo (FITS, o EXIF de las fotos), las clasifica en luces, darks, flats, darks de flat y bias, y empareja cada luz con los **darks de su misma exposición**, ganancia, temperatura, binning y tamaño, y con los **flats de su filtro**. Si falta un dark de esa exposición, lo escala con el bias. Antes de calibrar muestra el plan con avisos; las series grandes se combinan sin llenar la memoria.
- **Dispositivos del OAN** (en Parámetros): Celestron NexStar 8SE y Meade 10″, Nikon D5600, Canon T5i y QHY174M-GPS, y las máscaras del grupo y del protocolo. Llena D, B y la escala de placa (con el píxel efectivo del video en las cámaras de fotos).
- **Interfaz al 100 %** por defecto, aunque Windows o Linux tengan la pantalla al 125 % o 150 %. Se cambia en *Acerca de*.
- **Manual en PDF** (fundamentos, equipos del OAN, uso de los cuatro modos, archivos y problemas frecuentes), incluido en cada descarga.

**Mejoras**
- Parámetros más limpio: la calculadora de la escala se abre con *Calcular…* y los perfiles caben en una fila.
- Recorte y tramo con la barra en dos filas; la calibración del análisis solo muestra sus campos al activarla.
- Arreglado: textos encimados en la ficha del video.

La primera vez, Windows puede mostrar «Windows protegió su PC»: pulsa *Más información → Ejecutar de todas formas*. En Mac, abre la app con clic derecho → *Abrir*.

Cómo citar: Cagua Lozada, D. F., Cruz Ospina, F. E., & Pinto Sanabria, S. J. (2026). *TurbuLENS* (versión 1.4.0) [Software]. https://github.com/DiegoCagua/TurbuLENS
