def scan_angles(self, lat: float, lon: float) -> tuple[float, float, bool]:
    """Ángulos de barrido (x, y) en radianes y si el punto es visible desde el satélite."""
    phi = math.radians(lat)
    lam = math.radians(lon - self.lon0)
    e2 = (self.r_eq ** 2 - self.r_pol ** 2) / self.r_eq ** 2
    phic = math.atan((self.r_pol ** 2 / self.r_eq ** 2) * math.tan(phi))
    rc = self.r_pol / math.sqrt(1 - e2 * math.cos(phic) ** 2)
    sx = self.h - rc * math.cos(phic) * math.cos(lam)
    sy = -rc * math.cos(phic) * math.sin(lam)
    sz = rc * math.sin(phic)
    visible = self.h * (self.h - sx) >= sy ** 2 + (self.r_eq ** 2 / self.r_pol ** 2) * sz ** 2
    y = math.atan(sz / sx)
    x = math.asin(-sy / math.sqrt(sx ** 2 + sy ** 2 + sz ** 2))
    return x, y, visible
