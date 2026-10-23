# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Genera las imágenes de las fórmulas (LaTeX con mathtext) del modo educativo.

Herramienta de desarrollo: necesita matplotlib, que NO se incluye en la app.
Uso: python scripts/formulas.py   →   turbulens/assets/formulas/<nombre>_<idioma>_<tema>.png
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "turbulens", "assets", "formulas")
COLORS = {"dark": "#ECEDEF", "light": "#1D2622"}

# Decimales: coma en español y portugués, punto en inglés. «mediana» cambia de nombre en inglés.
def formulas(lang):
    dec = "." if lang == "en" else "{,}"
    med = r"\mathrm{median}" if lang == "en" else r"\mathrm{mediana}"
    return {
        "frecuencia": r"$f_k=\dfrac{n_k}{N}$",
        "media": r"$\bar{x}=\dfrac{1}{N}\sum_{i=1}^{N}x_i$",
        "desviacion": r"$\sigma=\sqrt{\dfrac{1}{N-1}\sum_{i=1}^{N}\left(x_i-\bar{x}\right)^{2}}$",
        "seeing": r"$\sigma_{\ell}^{2}=K_{\ell}\,\lambda^{2}\,r_0^{-5/3}\,D^{-1/3}\qquad\varepsilon=0" + dec + r"98\,\dfrac{\lambda}{r_0}$",
        "normal": r"$f(x)=\dfrac{1}{\sigma\sqrt{2\pi}}\;e^{-\frac{(x-\bar{x})^{2}}{2\sigma^{2}}}$",
        "error": r"$\sigma_{\bar{x}}=\dfrac{\sigma}{\sqrt{n}}$",
        "mad": r"$\sigma_{\mathrm{rob}}=1" + dec + r"4826\cdot " + med + r"\left(\left|x_i-\tilde{x}\right|\right)$",
        "correlacion": r"$r=\dfrac{\sum_{i}\left(x_i-\bar{x}\right)\left(y_i-\bar{y}\right)}{\sqrt{\sum_{i}\left(x_i-\bar{x}\right)^{2}\;\sum_{i}\left(y_i-\bar{y}\right)^{2}}}$",
    }


def render(tex, color, path, size=19):
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, tex, fontsize=size, color=color, math_fontfamily="cm")
    fig.savefig(path, dpi=200, transparent=True, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for lang in ("es", "en", "pt"):
        for name, tex in formulas(lang).items():
            for theme, col in COLORS.items():
                render(tex, col, os.path.join(OUT, f"{name}_{lang}_{theme}.png"))
                n += 1
    print(n, "fórmulas en", OUT)


if __name__ == "__main__":
    main()
