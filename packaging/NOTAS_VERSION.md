## TurbuLENS 1.3.0

Descarga el archivo de tu sistema, descomprímelo y abre TurbuLENS: no hay que instalar nada más. Funciona en **español, inglés y portugués**.

| Sistema | Archivo | Se abre con |
|---|---|---|
| Windows 10/11 (64 bits) | `TurbuLENS-v1.3.0-Windows-x64.zip` | `TurbuLENS.exe` |
| Mac con Apple Silicon (M1, M2, M3, M4…) | `TurbuLENS-v1.3.0-macOS-AppleSilicon.zip` | `TurbuLENS.app` |
| Mac con Intel | `TurbuLENS-v1.3.0-macOS-Intel.zip` | `TurbuLENS.app` |
| Linux (64 bits) | `TurbuLENS-v1.3.0-Linux-x64.tar.gz` | `TurbuLENS` |

**Nuevo**
- **Modo Imágenes**: calibración con **darks, flats, darks de flats y bias** (maestros por mediana, media o recorte de 3 σ, guardados en FITS) y un **visor de píxeles** como DS9: valor del píxel bajo el cursor, escalas lineal/log/raíz/asinh/histograma, límites ZScale y percentiles, mapas de color, zoom, estadística de una región y exportación de sus píxeles a CSV. Los maestros se pueden usar en el análisis de video.
- **Modo Satélite (GOES)**: elige fecha, hora (de Colombia o UTC), coordenadas, canales (1 a 16) y carpeta; TurbuLENS busca la imagen de disco completo más cercana, la descarga y lee el valor en tu punto, con un recorte en FITS y PNG. Usa **GOES-16** hasta el 4 de abril de 2025 y **GOES-19** desde entonces (o el que elijas).
- **Informe PDF**: nueva sección **«Cómo leer la correlación r»**: qué es r (longitudinal y transversal), cómo interpretar valores cercanos a 1, a 0 o negativos, el cociente σt/σl frente al teórico y un diagnóstico. En Resultados se ven estos valores con su **!**.
- **Modo educativo**: animaciones en «¿Por qué titilan?» (moneda en la piscina y estrella que cruza el aire) y en «Los dos huequitos» (con el telescopio que tiembla); «LA ESTRELLA» va antes de «ESTADÍSTICA»; las opciones de las preguntas salen en orden al azar; en «Media y mediana» los datos raros caen a un lado al azar; en tema claro la media (roja) y la mediana (azul) se distinguen bien del histograma.

**Mejoras del análisis**
- **Detección de los dos spots** más robusta: funciona con spots grandes, en anillo (desenfocados) o partidos, que antes se medían dentro de un mismo spot.
- **Seguir a la estrella**: la encuentra aunque la región quede lejos y la sigue cuadro a cuadro desde el primero; si se pierde, la vuelve a buscar en todo el cuadro.
- **Tamaño automático de la región** según el tamaño y la separación de los spots, y aviso si la región es demasiado pequeña.
- **Sin escala de placa no se procesa**: aviso destacado. Si cambias D, B, λ, la escala o la altura después de procesar, el seeing se recalcula al instante, sin volver a procesar.
- **Calculadora de escala para video**: con cámaras de fotos (Nikon, Canon) el píxel que vale es el efectivo del video (ancho del sensor ÷ ancho del video), no el del sensor. Lista de cámaras habituales.
- **Unidades** a elegir (µm, mm, cm) en diámetro, separación, píxel y sensor.
- **Perfiles de equipo** que se pueden actualizar, renombrar y eliminar.
- Los números aceptan **punto o coma** decimal.
- **Selector de archivos del sistema** (el de Windows, macOS o Linux) en toda la app.
- **Windows**: ya no aparecen ventanas sueltas al abrir el programa ni al cambiar de idioma.
- **Saray Juliana Pinto Sanabria** se une como coautora y encargada de las pruebas.

La primera vez, Windows puede mostrar «Windows protegió su PC»: pulsa *Más información → Ejecutar de todas formas*. En Mac, abre la app con clic derecho → *Abrir*.

Cómo citar: Cagua Lozada, D. F., Cruz Ospina, F. E., & Pinto Sanabria, S. J. (2026). *TurbuLENS* (versión 1.3.0) [Software]. https://github.com/DiegoCagua/TurbuLENS
