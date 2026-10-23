# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Cambia la versión de TurbuLENS en todos los archivos a la vez.

Uso:  python scripts/nueva_version.py 1.2.0

Después hay que escribir las novedades en ``packaging/NOTAS_VERSION.md`` (la
tabla de descargas y la cita se actualizan solas), correr ``python -m pytest``
y hacer push a ``main``: GitHub Actions compila, prueba y publica la versión.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def actual() -> str:
    return re.search(r'__version__ = "([^"]+)"', (ROOT / "turbulens/__init__.py").read_text(encoding="utf-8")).group(1)


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]):
        sys.exit(__doc__)
    old, new = actual(), sys.argv[1]
    if old == new:
        sys.exit(f"La versión ya es {new}.")
    cambios = {
        "turbulens/__init__.py": [(f'__version__ = "{old}"', f'__version__ = "{new}"')],
        "pyproject.toml": [(f'version = "{old}"', f'version = "{new}"')],
        "CITATION.cff": [(f'version: "{old}"', f'version: "{new}"')],
        "LICENSE": [(f"(versión {old})", f"(versión {new})")],
        "packaging/LEEME.txt": [(f"TurbuLENS {old}", f"TurbuLENS {new}"), (f"(versión {old})", f"(versión {new})")],
        "packaging/NOTAS_VERSION.md": [(f"TurbuLENS {old}", f"TurbuLENS {new}"), (f"v{old}-", f"v{new}-"), (f"(versión {old})", f"(versión {new})")],
        "README.md": [(f"Versión actual: {old}", f"Versión actual: {new}"), (f"v{old}", f"v{new}"),
                      (f"(versión {old})", f"(versión {new})"), (f"version   = {{{old}}}", f"version   = {{{new}}}")],
    }
    for rel, pares in cambios.items():
        p = ROOT / rel
        s = p.read_text(encoding="utf-8")
        for a, b in pares:
            if a not in s:
                sys.exit(f"No encontré «{a}» en {rel}: revisa ese archivo a mano.")
            s = s.replace(a, b)
        p.write_text(s, encoding="utf-8")
        print(f"  {rel}")
    import datetime

    c = ROOT / "CITATION.cff"
    c.write_text(re.sub(r'date-released: "[^"]+"', f'date-released: "{datetime.date.today().isoformat()}"',
                        c.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"Versión {old} → {new}. Escribe las novedades en packaging/NOTAS_VERSION.md y corre las pruebas.")


if __name__ == "__main__":
    main()
