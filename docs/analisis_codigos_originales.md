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

1. **FloodFill incorrecto.** Al recorrer hacia el oeste y el este usa `(x, y−c)` con la semilla original en lugar del nodo actual, y ni la semilla ni los píxeles agregados por norte/sur se guardan en `D`. En un cuadro de prueba contó 3 de 7 píxeles y el centroide quedó desplazado 0,29 px, cuando toda la señal del DIMM es una variación de ~0,7 px.
2. **Copiar y pegar:** revisa `ne` cuatro veces y nunca `se`, `nw` ni `sw`.
3. **Bordes:** índices negativos dan la vuelta a la imagen; en el borde derecho o inferior falla con `IndexError`.
4. **Lento:** recorre los ~2 millones de píxeles en Python: 0,87 s por cuadro (≈2 h para el video). TurbuLENS procesa el video completo en ~20 s.
5. **Se cae:** usa `re.sub` sin `import re` (las versiones actuales de `pylab` no lo exportan).
6. **Archivos intermedios:** `test.dat` se abre en modo agregar y se relee completo en cada cuadro (costo cuadrático), nunca se cierra, y hay que borrar los `.dat` a mano antes de cada ejecución.
7. **Emparejamiento a ciegas:** supone exactamente dos objetos por cuadro. En este video 68 cuadros tienen un solo objeto con el umbral fijo de 128; se emparejan con el cuadro siguiente y producen distancias falsas cercanas a 0 px que **casi duplican σ** (0,74 → ~1,3 px). Esa historia es la lección 7 del modo educativo.
8. **Umbral fijo de 128 y solo el canal rojo:** el resultado depende del brillo y del color de la estrella.
9. **Histograma y curva en escalas distintas:** el histograma está normalizado a fracciones y la curva normal es una densidad.
10. **Física incompleta:** la media y la desviación de la distancia no son el seeing; `ESCALAPLACA = 1.0` era un valor de relleno.

## Qué cambió en TurbuLENS

- Todo con **NumPy vectorizado**: bloques de cuadros `(n, alto, ancho)`, sin recorrer píxeles en Python; mediciones en un arreglo estructurado reservado de antemano.
- **Centroide ponderado por intensidad** con umbral relativo al fondo y al pico, en dos pasadas: error típico de 0,02–0,05 px en pruebas sintéticas.
- **Validación** de cada cuadro (relación señal/ruido, segundo spot real, dentro del recorte) y descarte robusto de atípicos (5 σ con MAD).
- **Seguimiento** de la estrella: en el video de Altair la estrella se desplaza ~110 px horizontal y ~140 px vertical en 2 minutos; sin seguimiento, un recorte fijo la pierde.
- **Seeing** con el modelo de Tokovinin (2002), longitudinal y transversal por separado, r₀ y corrección al cenit.
- Pruebas automáticas con videos sintéticos de valores conocidos.
