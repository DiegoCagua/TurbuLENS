# Análisis de los códigos originales

TurbuLENS reemplaza dos scripts de Python usados en la práctica del DIMM: `open.py` (separa el video en imágenes) e `Imagen_v5.py` (calcula el histograma de la separación entre los dos spots). Las cifras de este documento se midieron con el video de prueba `G_3_Altair_300824_21_38_DSC0034_Mascara.MOV` (H.264, 1920 × 1080, 59,94 cuadros/s, 8.484 cuadros, 13,9 MB).

## `open.py`

| Problema | Efecto | En TurbuLENS |
|---|---|---|
| Guarda cada cuadro completo a color en JPG (~107 kB) | ~900 MB de imágenes para un video de 14 MB | Recorte a la estrella en escala de grises: ~5 MB en PNG sin pérdida |
| JPG con pérdida | Hasta 5 niveles de gris de error en los spots | PNG predeterminado; TIFF 16 bits, NumPy y FITS opcionales |
| Nombres `frame10.jpg` sin ceros | El orden temporal se pierde al listar | `nombre_000010.png` y tiempo de cada cuadro en `mediciones.csv` |
| No revisa si el video abrió | Con un códec no soportado no crea nada y no avisa | Mensaje de error claro; PyAV/FFmpeg abre cientos de formatos |
| Ruta fija en el código | Hay que editar el programa para cada video | Interfaz gráfica, arrastrar y soltar |

## `Imagen_v5.py`

| Problema | Efecto | En TurbuLENS |
|---|---|---|
| FloodFill recorre oeste/este con `(x, y−c)` de la semilla original y no guarda en `D` la semilla ni los píxeles de norte/sur | En un cuadro de prueba contó 3 de 7 píxeles: centroide desplazado 0,29 px, cuando la señal del DIMM es ~0,7 px | Centroide ponderado por intensidad en toda la ventana del spot, en dos pasadas (error típico 0,02–0,05 px) |
| Copiar y pegar: revisa `ne` cuatro veces y nunca `se`, `nw` ni `sw` | Partes del spot quedan sin recorrer | No hay relleno por vecinos: operaciones de NumPy sobre el bloque completo |
| Bordes sin control | Índices negativos dan la vuelta a la imagen; en el borde derecho o inferior falla con `IndexError` | Recorte limitado a la imagen y cuadros con spots en el borde marcados como no válidos |
| Recorre los ~2 millones de píxeles en Python | 0,87 s por cuadro: ≈2 h para el video de prueba | Bloques vectorizados de cuadros `(n, alto, ancho)`: video completo en ~20 s |
| Usa `re.sub` sin `import re` | Se cae con las versiones actuales de `pylab` | Sin texto intermedio que procesar |
| `test.dat` en modo agregar, releído completo en cada cuadro y nunca cerrado | Costo cuadrático y hay que borrar los `.dat` a mano antes de cada ejecución | Mediciones en un arreglo estructurado de NumPy reservado de antemano; `mediciones.csv` y `resumen.json` al final |
| Empareja los spots suponiendo exactamente dos objetos por cuadro | 68 cuadros con un solo objeto (umbral 128) producen distancias falsas cercanas a 0 px que casi duplican σ (0,74 → ~1,3 px) | Cada cuadro se valida (señal/ruido, segundo spot real) y se descartan atípicos a más de 5 σ robustas; es la lección 7 del modo educativo |
| Descarta los objetos 3 y 4 pero conserva el 5 en adelante | Ruido o reflejos se cuelan en el análisis | Solo se usan los dos picos de la imagen doble dentro de la región |
| Umbral fijo de 128 y solo el canal rojo | El resultado depende del brillo y del color de la estrella | Umbral relativo al fondo y al pico; imagen en escala de grises (8 o 16 bits) |
| `glob` sin ordenar | Se pierde el orden temporal de los cuadros | Índice y tiempo reales de cada cuadro |
| Histograma normalizado a fracciones con una curva normal en densidad | Barras y curva en escalas distintas | Histograma y curva normal en la misma escala |
| Media y desviación de la distancia reportadas como resultado; `ESCALAPLACA = 1.0` de relleno; título fijo `MVI1346.MOV` | No es el seeing y no sirve para otro video ni equipo | Seeing longitudinal y transversal con el modelo de Tokovinin (2002), r₀ y corrección al cenit, con los parámetros del usuario |

### Un caso real: spots grandes y desenfocados (2026)

Con un video de estudiantes grabado con un Celestron NexStar 8SE (focal 2032 mm), máscara de D = 4,2 cm y B = 14,4 cm y una Nikon D5600, el código original daba una separación media de unos 20 a 50 px con σ ≈ 77 px, y TurbuLENS 1.2.2 daba unos 0,3 px. Ninguno era correcto:

- En **163 de 462 cuadros** el umbral de 128 encontraba **un solo objeto** (los dos spots eran grandes y se tocaban, o uno era débil). `Imagen_v5.py` emparejaba entonces ese objeto con el primero del cuadro siguiente: salían 117 distancias de 0 a 5 px y otras de más de 100 px por objetos de ruido. La media y la σ resultantes no medían la turbulencia.
- TurbuLENS 1.2.2 buscaba el segundo pico fuera de un disco pequeño alrededor del primero; con spots de ~20 px y textura interna, encontraba el «segundo spot» **dentro del primero**.

Desde la 1.3.0 los píxeles con luz se separan en dos grupos (k-medias ponderado por intensidad) y un cuadro solo cuenta si hay una caída de luz entre los dos spots. En ese video: 457 de 462 cuadros válidos, separación de 43,6 px con σ = 1,43 px. Con estrellas pequeñas (Altair) los dos métodos coinciden (13,35 frente a 13,45 px).

Además, la escala de placa que se había usado (0,40–0,44 ″/px) salía del píxel del **sensor** (3,9 µm), pero en video la cámara reduce la imagen: el píxel efectivo es 23,5 mm ÷ 1920 px = 12,2 µm, es decir 1,24 ″/px. Con la escala correcta el seeing pasa de ~1″ (imposible para ese sitio) a ~3,8″.

## Qué cambió en TurbuLENS

- Todo con **NumPy vectorizado**: bloques de cuadros `(n, alto, ancho)`, sin recorrer píxeles en Python; mediciones en un arreglo estructurado reservado de antemano.
- **Dos grupos de luz** (k-medias ponderado) y **centroide ponderado por intensidad** de cada spot, con umbral relativo al fondo y al pico: error típico de 0,02–0,05 px en pruebas sintéticas, también con spots grandes o en anillo.
- **Validación** de cada cuadro (relación señal/ruido, segundo spot real, dentro del recorte) y descarte robusto de atípicos (5 σ con MAD).
- **Seguimiento** de la estrella: en el video de Altair la estrella se desplaza ~110 px horizontal y ~140 px vertical en 2 minutos; sin seguimiento, un recorte fijo la pierde.
- **Seeing** con el modelo de Tokovinin (2002), longitudinal y transversal por separado, r₀ y corrección al cenit.
- Pruebas automáticas con videos sintéticos de valores conocidos.
