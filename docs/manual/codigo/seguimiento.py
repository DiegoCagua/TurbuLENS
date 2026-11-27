# 2) Seguimiento cuadro a cuadro: la región se mueve hacia el centro de luz (amortiguado para
#    no copiar el temblor de la turbulencia). Si se pierde varios cuadros, se busca en todo el cuadro.
lx, ly, ok = light_center(crop)
if ok:
    misses = 0
    cx += 0.5 * (x0 + lx - cx)
    cy += 0.5 * (y0 + ly - cy)
else:
    misses += 1
    if misses >= 5:
        r_far = locate_pair(frame)
        if r_far is not None and r_far["valid"]:
            cx, cy = r_far["cx"], r_far["cy"]
            reacquired += 1
        misses = 0
