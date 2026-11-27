p = np.array([A, cx, cy, min(sx, w / 2), min(sy, h / 2), B])
lam = 1e-3
f, J = _model_jac(p, x, y)
r = v - f
cost = float(r @ r)
it = 0
for it in range(1, max_iter + 1):
    JTJ = J.T @ J
    g = J.T @ r
    improved = False
    for _ in range(12):
        Hm = JTJ + lam * np.diag(np.diag(JTJ) + 1e-12)
        try:
            step = np.linalg.solve(Hm, g)
        except np.linalg.LinAlgError:
            lam *= 10
            continue
        q = p + step
        q[3] = max(abs(q[3]), 0.2)
        q[4] = max(abs(q[4]), 0.2)
        f2, J2 = _model_jac(q, x, y)
        r2 = v - f2
        c2 = float(r2 @ r2)
        if c2 < cost:
            p, f, J, r, cost = q, f2, J2, r2, c2
            lam = max(lam / 3, 1e-9)
            improved = True
            break
        lam *= 4
    if not improved or float(np.max(np.abs(step) / (np.abs(p) + 1e-9))) < 1e-7:
        break
