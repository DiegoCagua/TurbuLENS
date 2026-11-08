# Componentes de terceros

La licencia de TurbuLENS (PolyForm Noncommercial 1.0.0) cubre únicamente el código de TurbuLENS. Los ejecutables incluyen estos componentes, cada uno con su propia licencia, que no cambia:

| Componente | Licencia | Fuente |
|---|---|---|
| Qt 6 / PySide6 | LGPL v3 | https://www.qt.io · https://code.qt.io/cgit/pyside/pyside-setup.git |
| FFmpeg (a través de PyAV) | LGPL v2.1 o posterior | https://ffmpeg.org · https://github.com/PyAV-Org/PyAV |
| NumPy | BSD-3-Clause | https://numpy.org |
| Pillow | MIT-CMU (HPND) | https://python-pillow.org |
| openpyxl | MIT | https://foss.heptapod.net/openpyxl/openpyxl |
| pyfive 0.5.1 (incluido en `turbulens/_vendor/pyfive`, lector de NetCDF4/HDF5 para el modo Satélite) | BSD-3-Clause, © 2016 Jonathan J. Helmus y colaboradores (texto completo en `turbulens/_vendor/pyfive/LICENSE.txt`) | https://github.com/NCAS-CMS/pyfive |
| libxcb y xcb-util (solo Linux) | MIT/X11 | https://xcb.freedesktop.org |
| Python | PSF License | https://www.python.org |

Las bibliotecas LGPL se distribuyen como bibliotecas dinámicas separadas dentro del ejecutable, y pueden reemplazarse por otras versiones compatibles.
