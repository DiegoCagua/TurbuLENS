## TurbuLENS 1.5.1

Descarga el archivo de tu sistema, descomprímelo y abre TurbuLENS: no hay que instalar nada más. Funciona en **español, inglés y portugués**.

| Sistema | Archivo | Se abre con |
|---|---|---|
| Windows 10/11 (64 bits) | `TurbuLENS-v1.5.1-Windows-x64.zip` | `TurbuLENS.exe` |
| Mac con Apple Silicon (M1, M2, M3, M4…) | `TurbuLENS-v1.5.1-macOS-AppleSilicon.zip` | `TurbuLENS.app` |
| Mac con Intel | `TurbuLENS-v1.5.1-macOS-Intel.zip` | `TurbuLENS.app` |
| Linux (64 bits) | `TurbuLENS-v1.5.1-Linux-x64.tar.gz` | `TurbuLENS` |

### En esta versión
- **José Alejandro López Hernández** se suma como autor. Los cuatro autores aparecen de la misma forma en *Acerca de*, en
  el manual, en la licencia y en la cita: Diego Fernando Cagua Lozada, Fredy Esteban Cruz Ospina, Saray Juliana Pinto
  Sanabria y José Alejandro López Hernández.

Lo que trajo la 1.5.0:

### Medición del seeing
- El modo de mediciones se llama ahora **Medición del seeing** (antes «Análisis científico»).
- **Exportar en dos pasos**: eliges los formatos y la carpeta de destino y pulsas **Generar**. Los archivos se crean en ese momento; *Ver archivos* abre la carpeta.
- Un análisis se puede **guardar en el historial varias veces** (con otra etiqueta o después de cambiar los parámetros). Si cierras TurbuLENS, abres otro video o procesas de nuevo con un análisis sin guardar, te pregunta si quieres guardarlo.
- Si en el tramo no se detectan los dos puntos de la estrella, las gráficas quedan **vacías** con un aviso que dice qué revisar.
- El informe PDF completo trae los valores y las gráficas; la explicación de cómo leer las correlaciones *r* está en la lección 8 del modo educativo, con los números de tu análisis.
- **Equipos propios**: en *Dispositivos (OAN y propios)* agregas tu telescopio, tu cámara o tu máscara; quedan guardados junto a los del OAN. Junto con los perfiles, sirve para medir con cualquier montaje.
- Al lado de D, B y λ se ve el rango de valores permitido.
- Las gráficas leen el valor del punto bajo el cursor; con clic derecho se guardan como PNG o se copian, y con doble clic se ven en grande.

### Satélite
- **Serie de una noche**: elige *Desde* y *Hasta* con imágenes cada 30 o 60 minutos (la serie puede pasar la medianoche).
- **Seeing desde el satélite** con los canales 9, 13 y 16 (método de Cavazzani, Ortolani y Zitelli, 2012): función de estabilidad, su tendencia en la noche y el seeing hora por hora, con gráficas y tabla.
- **Criterio del Sol**: calcula la altura del Sol en cada hora y deja fuera las horas de día o de crepúsculo.
- **Mapa** sobre el recorte: costas, países y departamentos; al pasar el cursor se leen la latitud, la longitud y el valor. El zoom no se aleja más allá del recorte completo.
- **Lectura solo de la zona**: pide al servidor únicamente las partes del archivo que cubren tu recorte (≈2 MB por canal en vez de ≈25 MB).
- Cada evaluación se guarda en su propia subcarpeta, por ejemplo `evaluadas_dia_20261019_18-23_20261126_100953`, con la serie, los valores de cada canal, las gráficas, los recortes y un LEEME con los parámetros.
- Página **Cómo funciona**: el satélite GOES, qué mide cada uno de los 16 canales y el método del seeing con sus fórmulas.
- Recorte mínimo de 10 km.

### Imágenes
- Regiones **rectangulares, circulares o elípticas**.
- **Escala variable** como en DS9: histograma con el negro y el blanco, límites manuales y la opción de usar los mismos límites en todos los cuadros.
- **FWHM y seeing de una estrella**: ajuste de una gaussiana 2D, radio al primer sigma, FWHM en píxeles y, con la escala de placa, en segundos de arco.
- **Gráficas de la imagen**: perfil radial de la estrella, histograma de la región y perfiles horizontal y vertical.
- Calibración: **diagnóstico del flat** (cuánto corrige y si los flats están saturados) y **Comparar antes y después** con los mismos límites de brillo.
- Se pueden arrastrar imágenes y carpetas a la ventana.

### Manual
- Manual nuevo en PDF dentro de cada descarga: uso paso a paso de los cuatro modos, cómo medir con un equipo propio, los fundamentos y el código de las partes principales.

La primera vez, Windows puede mostrar «Windows protegió su PC»: pulsa *Más información → Ejecutar de todas formas*. En Mac, abre la app con clic derecho → *Abrir*.

Cómo citar: Cagua Lozada, D. F., Cruz Ospina, F. E., Pinto Sanabria, S. J., & López Hernández, J. A. (2026). *TurbuLENS* (versión 1.5.1) [Software]. https://github.com/DiegoCagua/TurbuLENS
