# Método

## 1. El DIMM

Una máscara con dos orificios de diámetro **D**, separados **B** entre centros, se pone sobre la apertura del telescopio. Con la cámara levemente desenfocada se ven dos imágenes de la misma estrella. La vibración del telescopio mueve las dos imágenes juntas, pero la turbulencia afecta distinto a cada camino de luz: medir la **diferencia** de posición cancela las vibraciones y deja solo el efecto de la atmósfera.

## 2. Medición por cuadro

Antes de medir, en los primeros cuadros se **ubica la estrella** (aunque la región haya quedado lejos: la búsqueda se amplía desde la región hasta el cuadro completo) y, con *Tamaño automático*, se ajusta el tamaño de la región a la separación y el tamaño de los spots, con margen para el fondo y el movimiento. Con *Seguir a la estrella* la región se recentra en cada cuadro en el centro de luz de la imagen doble; si la estrella se pierde 5 cuadros seguidos, se vuelve a buscar en todo el cuadro. Si hay maestros de calibración, cada cuadro se corrige como (cuadro − dark) ÷ flat.

Para cada cuadro (en bloques vectorizados):

1. Fondo = mediana del recorte; ruido = 1,4826 × MAD. La imagen se suaviza con una caja de 3 × 3 solo para decidir qué píxeles tienen luz: los que superan max(0,15 × pico, 4 × ruido / 3).
2. Los píxeles con luz se separan en **dos grupos** con k-medias ponderado por intensidad (8 iteraciones), que empieza en el píxel más brillante y en el píxel con luz más alejado de él. Así se separan bien spots pequeños, grandes, en anillo (desenfocados) o partidos.
3. El centro de cada spot es el **centroide ponderado por intensidad** de su grupo, recortado a 3 r + 3 px alrededor del centro (r = radio de giro del grupo). El spot 1 es el más brillante.
4. El cuadro es válido si los dos spots superan la relación señal/ruido mínima, el segundo tiene al menos 12 % de la luz del primero, están separados más de 2,2 veces su radio, entre ellos hay una **caída de luz** (menos de 60 % del pico menor en el punto medio) y ninguno toca el borde del recorte.

## 3. De las mediciones al seeing

- Vector d = spot 2 − spot 1. Como los spots pueden intercambiarse, se orientan todos según el eje principal de la nube de vectores.
- Línea de base u = dirección media de d. Componentes: longitudinal ℓ = d · u, transversal t = d · u⊥.
- Se descartan los cuadros cuya separación |d| está a más de 5 σ robustas de la mediana.
- Varianzas σ²ₗ y σ²ₜ en px², convertidas a rad² con la escala de placa s (″/px): σ²(rad²) = σ²(px²) · (s / 206264,8)².
- Tokovinin (2002), centroide (inclinación G), b = B / D:

  Kₗ = 0,364 (1 − 0,532 b^(−1/3) − 0,024 b^(−7/3))
  Kₜ = 0,364 (1 − 0,798 b^(−1/3) + 0,018 b^(−7/3))
  r₀ = (K λ² D^(−1/3) / σ²)^(3/5)
  ε = 0,98 λ / r₀

- El seeing reportado es el promedio de εₗ y εₜ. Con la altura h de la estrella, z = 90° − h y ε_cenit = ε · (cos z)^(3/5).

Referencia de control (probada en `tests/test_core.py`): σ = 0,72 px, s = 1″/px, D = 2,5 cm, B = 14 cm, λ = 550 nm → r₀ ≈ 10 cm, ε ≈ 1,11″.

### Controles de calidad (correlaciones)

- **r longitudinal–transversal**: correlación de Pearson entre ℓ y t. La turbulencia mueve las dos componentes de forma independiente; |r| < 0,2 es lo esperado y un |r| grande indica vibración en una dirección, cambios de foco o spots confundidos.
- **r entre los dos spots** (longitudinal y transversal), tras quitar la deriva lenta con una media móvil de 1 s: cerca de 1 domina el movimiento común (vibración, seguimiento), que el DIMM cancela; entre 0 y 1 es lo normal; cerca de 0 cada orificio ve turbulencia independiente; negativo indica cambios de foco o de escala o errores de detección.
- **σt/σl** medido frente al teórico √(Kt/Kl).

El informe PDF explica estos valores con los números del análisis.

## 4. Precauciones

- El seeing depende linealmente de la escala de placa y de la geometría de la máscara: un error del 10 % en la escala produce un error parecido en ε.
- La varianza también incluye el ruido de medición del centroide (aquí ~0,03 px, despreciable frente a ~0,7 px) y se ve afectada por exposiciones largas; con 30–60 cuadros/s el efecto es pequeño pero no nulo.
- Elige un tramo estable de al menos 15–20 s: la gráfica de σ segundo a segundo en Resultados muestra golpes y ráfagas.
- El cálculo debe validarse con el equipo y el procedimiento del observatorio antes de usarse como medida oficial.
