# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""TurbuLENS: separa videos de un DIMM en imágenes, mide el seeing y enseña estadística.

Observatorio Astronómico Nacional · Universidad Nacional de Colombia.
Autores: Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina, estudiantes del pregrado de Física,
Universidad Nacional de Colombia.
"""

__version__ = "1.1.2"

APP_NAME = "TurbuLENS"
AUTHORS = [("Diego Fernando Cagua Lozada", "Estudiante del pregrado de Física · Universidad Nacional de Colombia"),
           ("Fredy Esteban Cruz Ospina", "Estudiante del pregrado de Física · Universidad Nacional de Colombia")]
AUTHOR = "Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina"
AUTHOR_ROLE = "Estudiantes del pregrado de Física · Universidad Nacional de Colombia"
INSTITUTION = "Observatorio Astronómico Nacional · Universidad Nacional de Colombia"
REPO_URL = "https://github.com/DiegoCagua/TurbuLENS"
LICENSE_NAME = "PolyForm Noncommercial 1.0.0"
LICENSE_SUMMARY = ("Uso libre sin fines comerciales (estudio, investigación, enseñanza). Toda copia o versión "
                   "modificada debe conservar el crédito a los autores. No se permite el uso comercial sin permiso escrito.")
CITATION_APA = ("Cagua Lozada, D. F., & Cruz Ospina, F. E. (2026). TurbuLENS (versión {v}) [Software]. Observatorio Astronómico Nacional, "
                "Universidad Nacional de Colombia. https://github.com/DiegoCagua/TurbuLENS")
CITATION_BIBTEX = """@software{{cagua_lozada_turbulens_2026,
  author    = {{Cagua Lozada, Diego Fernando and Cruz Ospina, Fredy Esteban}},
  title     = {{TurbuLENS: medición del seeing con un DIMM y enseñanza de la estadística}},
  year      = {{2026}},
  version   = {{{v}}},
  publisher = {{Observatorio Astronómico Nacional, Universidad Nacional de Colombia}},
  url       = {{https://github.com/DiegoCagua/TurbuLENS}}
}}"""


def citation_apa() -> str:
    return CITATION_APA.format(v=__version__)


def citation_bibtex() -> str:
    return CITATION_BIBTEX.format(v=__version__)

# Fuentes de datos para la escala de placa (se muestran en Parámetros y en Acerca de).
SCALE_LINKS = [
    ("https://byronbayobservatory.com.au/astronomy-calculator",
     "Dylan's Astronomy Setup Calculator: base de datos de 174 telescopios y 65 cámaras (focal y tamaño de píxel)"),
    ("https://apotelyt.com/camera-specs/nikon-d5300-sensor-pixels",
     "Apotelyt: tamaño de píxel de cada cámara (ej. Nikon D5300: 3,91 µm; busca tu modelo)"),
]
