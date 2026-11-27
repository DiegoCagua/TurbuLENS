def apply_calibration(img: np.ndarray, dark: Optional[np.ndarray] = None, flat: Optional[np.ndarray] = None,
                      bias: Optional[np.ndarray] = None) -> np.ndarray:
    """(imagen − dark) / flat. Si no hay dark pero sí bias, resta el bias. Devuelve float32."""
    out = np.asarray(img, dtype=np.float32)
    if dark is not None:
        if dark.shape != out.shape:
            raise ValueError(f"el dark mide {dark.shape[1]}×{dark.shape[0]} y la imagen {out.shape[1]}×{out.shape[0]}")
        out = out - dark
    elif bias is not None:
        if bias.shape != out.shape:
            raise ValueError("el bias no tiene el tamaño de la imagen")
        out = out - bias
    if flat is not None:
        if flat.shape != out.shape:
            raise ValueError(f"el flat mide {flat.shape[1]}×{flat.shape[0]} y la imagen {out.shape[1]}×{out.shape[0]}")
        out = out / flat
    return out
