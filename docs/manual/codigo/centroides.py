def centroids(c1y, c1x, c2y, c2x, lim1=None, lim2=None):
    d1 = (Y - c1y[:, None, None]) ** 2 + (X - c1x[:, None, None]) ** 2
    d2 = (Y - c2y[:, None, None]) ** 2 + (X - c2x[:, None, None]) ** 2
    A = d1 <= d2
    wA = np.where(A, wgt, 0.0)
    wB = wgt - wA
    if lim1 is not None:
        wA = np.where(d1 <= lim1[:, None, None], wA, 0.0)
        wB = np.where(d2 <= lim2[:, None, None], wB, 0.0)
    S1 = wA.sum(axis=(1, 2))
    S2 = wB.sum(axis=(1, 2))
    s1 = np.where(S1 > 0, S1, 1.0)
    s2 = np.where(S2 > 0, S2, 1.0)
    n1y = np.where(S1 > 0, (wA * Y).sum(axis=(1, 2)) / s1, c1y)
    n1x = np.where(S1 > 0, (wA * X).sum(axis=(1, 2)) / s1, c1x)
    n2y = np.where(S2 > 0, (wB * Y).sum(axis=(1, 2)) / s2, c2y)
    n2x = np.where(S2 > 0, (wB * X).sum(axis=(1, 2)) / s2, c2x)
    return n1y, n1x, n2y, n2x, A, wA, wB, S1, S2

for _ in range(max(1, cfg.iterations)):
    n1y, n1x, n2y, n2x, A, wA, wB, S1, S2 = centroids(c1y, c1x, c2y, c2x)
    moved = np.maximum(np.abs(n1y - c1y) + np.abs(n1x - c1x), np.abs(n2y - c2y) + np.abs(n2x - c2x))
    c1y, c1x, c2y, c2x = n1y, n1x, n2y, n2x
    if float(moved.max(initial=0.0)) < 1e-3:
        break
