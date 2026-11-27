def f_stability(t9: float, t13: float, t16: float) -> float:
    """F = T9 − (T16 − T13), en kelvin."""
    return t9 - (t16 - t13)


def seeing_from_deviation(dF: float, theta_deg: float, z_km: float = 4.0, lambda_nm: float = 500.0) -> dict:
    """Seeing (″), r₀ (cm) y ∫Cn²dz (m^(1/3)) a partir de |F − F_tendencia| (K)."""
    lam = lambda_nm * 1e-9
    big_l = LAMBDA_COEF / max(1e-6, math.cos(math.radians(theta_deg)))
    cn2 = big_l * abs(dF) / z_km if math.isfinite(dF) else float("nan")
    if not math.isfinite(cn2):
        return {"cn2": float("nan"), "seeing": float("nan"), "r0_cm": float("nan"), "Lambda": big_l}
    fwhm = 0.58 * lam ** (-0.2) * (4 * math.pi ** 2 * cn2) ** 0.6 * ARCSEC
    r0 = (0.423 * (2 * math.pi / lam) ** 2 * cn2) ** (-0.6) * 100 if cn2 > 0 else float("inf")
    return {"cn2": cn2, "seeing": fwhm, "r0_cm": r0, "Lambda": big_l}
