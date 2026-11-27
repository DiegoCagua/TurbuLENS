def trend(hours: np.ndarray, F: np.ndarray, use: np.ndarray) -> tuple[np.ndarray, str]:
    """Tendencia de F durante la noche: recta de mínimos cuadrados con los instantes usados (≥ 3) o su promedio."""
    hours = np.asarray(hours, float)
    F = np.asarray(F, float)
    ok = np.asarray(use, bool) & np.isfinite(F)
    if ok.sum() >= 3:
        a, b = np.polyfit(hours[ok], F[ok], 1)
        return a * hours + b, "recta"
    if ok.sum() >= 1:
        return np.full(F.shape, float(np.mean(F[ok]))), "promedio"
    return np.full(F.shape, np.nan), "sin datos"
