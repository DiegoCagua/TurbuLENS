# Componentes de terceros

La licencia de TurbuLENS (PolyForm Noncommercial 1.0.0) cubre únicamente el código de TurbuLENS. Los ejecutables incluyen estos componentes, cada uno con su propia licencia, que no cambia:

| Componente | Licencia | Fuente |
|---|---|---|
| Qt 6 / PySide6 | LGPL v3 | https://www.qt.io · https://code.qt.io/cgit/pyside/pyside-setup.git |
| FFmpeg (a través de PyAV) | LGPL v2.1 o posterior | https://ffmpeg.org · https://github.com/PyAV-Org/PyAV |
| NumPy | BSD-3-Clause | https://numpy.org |
| Pillow | MIT-CMU (HPND) | https://python-pillow.org |
| openpyxl | MIT | https://foss.heptapod.net/openpyxl/openpyxl |
| libxcb y xcb-util (solo Linux) | MIT/X11 | https://xcb.freedesktop.org |
| Python | PSF License | https://www.python.org |

Las bibliotecas LGPL se distribuyen como bibliotecas dinámicas separadas dentro del ejecutable, y pueden reemplazarse por otras versiones compatibles.
