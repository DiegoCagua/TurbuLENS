def sigma_clip_mask(x, k: float = 5.0, iters: int = 3) -> np.ndarray:
    """Máscara de datos que quedan tras descartar los que se alejan más de ``k`` σ robustas."""
    a = np.asarray(x, dtype=np.float64)
    keep = np.isfinite(a)
    for _ in range(iters):
        if keep.sum() < 3:
            break
        med = np.median(a[keep])
        mad = np.median(np.abs(a[keep] - med)) * 1.4826
        if mad <= 0:
            break
        new = keep & (np.abs(a - med) <= k * mad)
        if new.sum() == keep.sum():
            break
        keep = new
    return keep
