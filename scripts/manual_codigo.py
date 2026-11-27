# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Copia al manual los fragmentos de código que se comentan en «Por dentro: el código».

Uso:  python scripts/manual_codigo.py

Cada fragmento sale del código fuente actual, con sus números de línea reales, a docs/manual/codigo/<id>.py, y
docs/manual/codigo/lineas.tex define para cada uno la macro \\primera<id> (su primera línea) y \\archivo<id>. Así el
manual no queda desactualizado: después de cambiar el código basta con volver a correr este script.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "manual", "codigo")

# (id, archivo, desde, hasta)
#   desde/hasta: «def nombre» o «class Nombre» (la función o clase completa) o un texto que aparece en la línea.
#   hasta = None: hasta el final de la función o clase de «desde», o del bloque que empieza en el texto de «desde».
#   hasta = (texto, k): k líneas más después de la línea con el texto.
FRAGMENTOS = [
    ("tokovinin", "turbulens/core/dimm.py", "def k_coefficients", "def seeing_from_r0"),
    ("ejebase", "turbulens/core/dimm.py", "# Los spots pueden intercambiarse", "tra = -dx * uy + dy * ux"),
    ("seeingdimm", "turbulens/core/dimm.py", "scale = params.scale_arcsec_px", "res.eps_zenith = res.eps"),
    ("umbral", "turbulens/core/detect.py", "flat = a.reshape(n, -1)", "wgt = np.where(fg"),
    ("centroides", "turbulens/core/detect.py", "def centroids(", ("if float(moved.max", 1)),
    ("valido", "turbulens/core/detect.py", "with np.errstate(invalid=\"ignore\"):", ("& inside", 1)),
    ("sigmaclip", "turbulens/core/stats.py", "def sigma_clip_mask", None),
    ("escala", "turbulens/core/devices.py", "def effective_pixel_um", "return self.pixel_um"),
    ("escalaplaca", "turbulens/core/devices.py", "def plate_scale", None),
    ("seguimiento", "turbulens/core/pipeline.py", "# 2) Seguimiento cuadro a cuadro", None),
    ("darkescalado", "turbulens/core/calframes.py", "def dark_for", None),
    ("combinar", "turbulens/core/calibration.py", "def combine_stack", None),
    ("corregir", "turbulens/core/calibration.py", "def apply_calibration", None),
    ("gauss", "turbulens/core/starfit.py", "p = np.array([A, cx, cy", "break"),
    ("satformulas", "turbulens/core/satseeing.py", "def f_stability", 'return {"cn2": cn2, "seeing": fwhm'),
    ("tendencia", "turbulens/core/satseeing.py", "def trend", None),
    ("sol", "turbulens/core/satseeing.py", "def sun_altitude_deg", None),
    ("cenitsat", "turbulens/core/satseeing.py", "def satellite_zenith_deg", None),
    ("carpeta", "turbulens/core/satseeing.py", "def eval_folder_name", None),
    ("rango", "turbulens/core/goes.py", "def _get(self, i: int)", "return data"),
    ("proyeccion", "turbulens/core/goes.py", "def scan_angles", None),
]


def _node_range(tree, name):
    kind, _, ident = name.partition(" ")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == ident.split("(")[0]:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            return start, node.end_lineno
    raise SystemExit(f"no se encontró {name}")


def _find(lines, text, after=0):
    for i in range(after, len(lines)):
        if text in lines[i]:
            return i + 1
    raise SystemExit(f"no se encontró «{text}»")


def extract(path, desde, hasta):
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    lines = src.splitlines()
    tree = ast.parse(src)
    if desde.startswith(("def ", "class ")) and not desde.endswith("("):
        a, b = _node_range(tree, desde)
    else:
        a = _find(lines, desde)
        b = None
        if hasta is None:  # hasta el final del bloque que empieza en «desde»
            ind = len(lines[a - 1]) - len(lines[a - 1].lstrip())
            b = a
            for j in range(a, len(lines)):
                s = lines[j]
                if s.strip() and len(s) - len(s.lstrip()) < ind:
                    break
                b = j + 1
            while not lines[b - 1].strip():
                b -= 1
    extra = 0
    if isinstance(hasta, tuple):
        hasta, extra = hasta
    if hasta is not None:
        if hasta.startswith(("def ", "class ")):
            b = _node_range(tree, hasta)[1]
        else:
            b = _find(lines, hasta, a - 1)
            if hasta == "break":  # el «break» del bucle de Levenberg–Marquardt
                b = _find(lines, "if not improved", a - 1) + 1
    b += extra
    body = lines[a - 1:b]
    ind = min(len(s) - len(s.lstrip()) for s in body if s.strip())
    return a, b, "\n".join(s[ind:] for s in body) + "\n"


def main():
    os.makedirs(OUT, exist_ok=True)
    tex = ["% Generado por scripts/manual_codigo.py: primera línea y archivo de cada fragmento."]
    for ident, path, desde, hasta in FRAGMENTOS:
        a, b, code = extract(path, desde, hasta)
        with open(os.path.join(OUT, ident + ".py"), "w", encoding="utf-8") as fh:
            fh.write(code)
        tex.append(f"\\expandafter\\def\\csname primera{ident}\\endcsname{{{a}}}")
        tex.append(f"\\expandafter\\def\\csname ultima{ident}\\endcsname{{{b}}}")
        tex.append(f"\\expandafter\\def\\csname archivo{ident}\\endcsname{{{path.replace('_', chr(92) + '_')}}}")
        print(f"{ident:13s} {path}:{a}-{b} ({b - a + 1} líneas)")
    with open(os.path.join(OUT, "lineas.tex"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(tex) + "\n")


if __name__ == "__main__":
    sys.exit(main())
