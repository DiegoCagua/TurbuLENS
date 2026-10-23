# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Todo lo que muestra una versión debe mostrar la misma (si no, no se publica)."""

import re
from pathlib import Path

import turbulens

ROOT = Path(__file__).resolve().parents[1]
V = turbulens.__version__
SISTEMAS = ["Windows-x64-Instalador.exe", "Windows-x64.zip", "macOS-AppleSilicon.dmg", "macOS-Intel.dmg", "Linux-x64.tar.gz"]


def leer(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_version_bien_formada():
    assert re.fullmatch(r"\d+\.\d+\.\d+", V)


def test_metadatos():
    assert f'version = "{V}"' in leer("pyproject.toml")
    assert f'version: "{V}"' in leer("CITATION.cff")
    # El .spec (versión del .exe y de la app de Mac) lee la versión de turbulens/__init__.py
    assert "__version__" in leer("packaging/turbulens.spec") and '"CFBundleShortVersionString": VERSION' in leer("packaging/turbulens.spec")


def test_cita_en_licencia_leeme_y_readme():
    for rel in ("LICENSE", "packaging/LEEME.txt", "README.md", "packaging/NOTAS_VERSION.md"):
        assert f"(versión {V})" in leer(rel), rel
        otras = set(re.findall(r"\(versión (\d+\.\d+\.\d+)\)", leer(rel))) - {V}
        assert not otras, f"{rel} cita otra versión: {otras}"
    assert f"version   = {{{V}}}" in leer("README.md")


def test_descargas_del_readme_y_notas():
    readme = leer("README.md")
    assert f"Versión actual: {V}" in readme
    for nota in ("README.md", "packaging/NOTAS_VERSION.md"):
        txt = leer(nota)
        for s in SISTEMAS:
            assert f"TurbuLENS-v{V}-{s}" in txt, f"{nota}: falta TurbuLENS-v{V}-{s}"
        viejos = set(re.findall(r"TurbuLENS-v(\d+\.\d+\.\d+)-", txt)) - {V}
        assert not viejos, f"{nota} tiene descargas de otras versiones: {viejos}"
    for s in SISTEMAS:
        assert f"releases/download/v{V}/TurbuLENS-v{V}-{s}" in readme
    assert leer("packaging/NOTAS_VERSION.md").startswith(f"## TurbuLENS {V}")
    assert leer("packaging/LEEME.txt").startswith(f"TurbuLENS {V}")
