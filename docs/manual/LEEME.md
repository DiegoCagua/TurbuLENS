# Manual de TurbuLENS (fuente en LaTeX)

El PDF compilado está en `docs/Manual_TurbuLENS_v1.5.0.pdf` y va dentro de cada descarga.

## Archivos

- `TurbuLENS_manual.tex`: el documento principal (portada, índice y el orden de los capítulos).
- `estilo.tex`: colores, títulos, recuadros, botones, capturas con marcas numeradas y fragmentos de código.
- `capitulos/`: un archivo por capítulo. Partes I y II (uso de la aplicación), III (fundamentos), IV (el código) y apéndices.
- `img/`: capturas de la aplicación (tema claro, 1440 × 900) y, para las que llevan marcas numeradas, `<captura>_marcas.tex`
  con la posición de cada marca.
- `codigo/`: los fragmentos de código que se comentan en el capítulo 13 y `lineas.tex` con sus números de línea.

## Compilar

Con **XeLaTeX** (o LuaLaTeX), dos pasadas:

```bash
cd docs/manual
xelatex TurbuLENS_manual.tex
xelatex TurbuLENS_manual.tex
```

En Overleaf: sube la carpeta completa y elige Menú → Compilador → XeLaTeX. La fuente es Inter; si no está instalada se usa
la predeterminada.

## Después de cambiar la aplicación

```bash
python scripts/capturas_manual.py    # capturas y marcas (TURBULENS_CAPTURAS_DIR=/ruta/legible para rutas bonitas)
python scripts/manual_codigo.py      # fragmentos de código con sus líneas reales
```

y se compila otra vez. Los números de línea del capítulo 13 y la posición de las marcas salen de esos scripts, así que el
manual no queda desactualizado.
