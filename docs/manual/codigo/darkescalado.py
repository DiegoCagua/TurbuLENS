def dark_for(self, c: DarkChoice) -> Optional[np.ndarray]:
    """La imagen que se resta, según el modo elegido en el plan."""
    if c.mode == "ninguno":
        return None
    if c.mode == "bias":
        return self.bias(c.bias_paths)
    d = self.raw_dark(c.paths, c.exptime)
    if c.mode == "escalado":
        b = self.bias(c.bias_paths)
        return ((d - b) * np.float32(c.scale) + b).astype(np.float32)
    return d
