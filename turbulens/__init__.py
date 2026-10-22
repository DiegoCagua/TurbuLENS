# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""TurbuLENS: separa videos de un DIMM en imágenes, mide el seeing y enseña estadística.

Observatorio Astronómico Nacional · Universidad Nacional de Colombia.
Autores: Diego Fernando Cagua Lozada (estudiante del pregrado de Física) y Fredy Esteban Cruz Ospina.
"""

__version__ = "1.1.2"

APP_NAME = "TurbuLENS"
AUTHORS = [("Diego Fernando Cagua Lozada", "Estudiante del pregrado de Física"), ("Fredy Esteban Cruz Ospina", "")]
AUTHOR = "Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina"
AUTHOR_ROLE = "Estudiante del pregrado de Física"
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
