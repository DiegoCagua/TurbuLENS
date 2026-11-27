with np.errstate(invalid="ignore"):
    valid = (
        (S1 > 0) & (S2 > 0)
        & (p1 > cfg.snr_min * noise) & (p2 > cfg.snr_min * noise)
        & (fmin > cfg.second_min_ratio * np.maximum(fmax, 1e-9))
        & (sep > 2.2 * np.maximum(np.maximum(rg1, rg2), 0.5))
        & (dip < 0.6 * np.minimum(q1, q2))
        & np.isfinite(p1) & np.isfinite(p2)
        & inside
    )
