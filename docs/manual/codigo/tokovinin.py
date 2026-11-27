def k_coefficients(b: float) -> tuple[float, float]:
    kl = 0.364 * (1 - 0.532 * b ** (-1 / 3) - 0.024 * b ** (-7 / 3))
    kt = 0.364 * (1 - 0.798 * b ** (-1 / 3) + 0.018 * b ** (-7 / 3))
    return kl, kt


def r0_from_variance(var_rad2: float, K: float, lam_m: float, D_m: float) -> float:
    if not (var_rad2 > 0 and K > 0 and lam_m > 0 and D_m > 0):
        return float("nan")
    return (K * lam_m ** 2 * D_m ** (-1 / 3) / var_rad2) ** (3 / 5)


def seeing_from_r0(r0_m: float, lam_m: float) -> float:
    if not (r0_m > 0):
        return float("nan")
    return 0.98 * lam_m / r0_m * ARCSEC_PER_RAD
