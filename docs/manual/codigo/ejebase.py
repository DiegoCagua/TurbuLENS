# Los spots pueden intercambiarse entre cuadros (cambia cuál es el más
# brillante). Se orienta cada vector según el eje principal de la nube.
if det.sum() >= 2:
    m = np.array([[np.mean(dx[det] ** 2), np.mean(dx[det] * dy[det])],
                  [np.mean(dx[det] * dy[det]), np.mean(dy[det] ** 2)]])
    w, v = np.linalg.eigh(m)
    ax, ay = v[:, int(np.argmax(w))]
    sgn = np.where(dx * ax + dy * ay < 0, -1.0, 1.0)
    dx, dy = dx * sgn, dy * sgn
sep = np.hypot(dx, dy)
sep = np.where(det, sep, np.nan)

used = det & stats.sigma_clip_mask(sep, k=clip_k)
if used.sum() < 3:
    used = det.copy()

# Dirección media de la línea de base y proyecciones.
mdx = float(np.nanmean(dx[used])) if used.any() else 1.0
mdy = float(np.nanmean(dy[used])) if used.any() else 0.0
norm = math.hypot(mdx, mdy) or 1.0
ux, uy = mdx / norm, mdy / norm
lon = dx * ux + dy * uy
tra = -dx * uy + dy * ux
