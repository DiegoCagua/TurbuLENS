scale = params.scale_arcsec_px
if scale and scale > 0 and params.valid_geometry():
    D = params.D_cm / 100.0
    B = params.B_cm / 100.0
    lam = params.lambda_nm * 1e-9
    kl, kt = k_coefficients(B / D)
    conv = (scale / ARCSEC_PER_RAD) ** 2
    r0l = r0_from_variance(sl ** 2 * conv, kl, lam, D)
    r0t = r0_from_variance(st ** 2 * conv, kt, lam, D)
    res.eps_l = seeing_from_r0(r0l, lam)
    res.eps_t = seeing_from_r0(r0t, lam)
    vals = [v for v in (res.eps_l, res.eps_t) if math.isfinite(v)]
    res.eps = float(np.mean(vals)) if vals else float("nan")
    r0s = [v for v in (r0l, r0t) if math.isfinite(v)]
    res.r0_cm = float(np.mean(r0s)) * 100 if r0s else float("nan")
    alt = params.altitude_deg
    if alt is not None and 5 <= alt <= 90:
        z = math.radians(90 - alt)
        res.airmass = 1.0 / math.cos(z)
        res.eps_zenith = res.eps * math.cos(z) ** (3 / 5)
