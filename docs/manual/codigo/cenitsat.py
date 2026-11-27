def satellite_zenith_deg(lat: float, lon: float, sat_lon: float = GOES_EAST_LON) -> float:
    """Ángulo cenital (°) del satélite geoestacionario visto desde (lat, lon): 0° si está justo encima."""
    R, r = 6371.0, 42164.0
    cg = math.cos(math.radians(lat)) * math.cos(math.radians(lon - sat_lon))
    d = math.sqrt(R * R + r * r - 2 * R * r * cg)
    return math.degrees(math.acos(max(-1.0, min(1.0, (r * cg - R) / d))))
