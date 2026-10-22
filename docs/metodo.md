# Método

## 1. El DIMM

Una máscara con dos orificios de diámetro **D**, separados **B** entre centros, se pone sobre la apertura del telescopio. Con la cámara levemente desenfocada se ven dos imágenes de la misma estrella. La vibración del telescopio mueve las dos imágenes juntas, pero la turbulencia afecta distinto a cada camino de luz: medir la **diferencia** de posición cancela las vibraciones y deja solo el efecto de la atmósfera.

## 2. Medición por cuadro

Para cada cuadro (en bloques vectorizados de 32 cuadros):

1. Fondo = mediana del recorte; ruido = 1,4826 × MAD.
2. Spot 1 = píxel más brillante. Se oculta un disco de radio ≈ 3 r (r = radio del spot estimado a media altura) y el máximo restante es el spot 2.
3. Centroide ponderado por intensidad en una ventana de semiancho ≈ 2,5 r, con umbral max(0,2 × pico, 3 × ruido); se repite centrado en el resultado.
4. El cuadro es válido si ambos picos superan 6 × ruido, el segundo tiene al menos 12 % del primero y ninguno está en el borde.

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

## 4. Precauciones

- El seeing depende linealmente de la escala de placa y de la geometría de la máscara: un error del 10 % en la escala produce un error parecido en ε.
- La varianza también incluye el ruido de medición del centroide (aquí ~0,03 px, despreciable frente a ~0,7 px) y se ve afectada por exposiciones largas; con 30–60 cuadros/s el efecto es pequeño pero no nulo.
- Elige un tramo estable de al menos 15–20 s: la gráfica de σ segundo a segundo en Resultados muestra golpes y ráfagas.
- El cálculo debe validarse con el equipo y el procedimiento del observatorio antes de usarse como medida oficial.
