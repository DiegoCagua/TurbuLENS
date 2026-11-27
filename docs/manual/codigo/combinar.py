def combine_stack(stack: np.ndarray, method: str = "mediana", sigma: float = 3.0) -> np.ndarray:
    """Igual que :func:`combine`, para un arreglo ``(n, alto, ancho)`` ya armado (no lo copia)."""
    if stack.ndim != 3 or stack.shape[0] == 0:
        raise ValueError("se necesita al menos una imagen")
    if stack.shape[0] == 1:
        return np.array(stack[0], dtype=np.float32)
    if method == "media":
        return stack.mean(axis=0, dtype=np.float32)
    med = np.median(stack, axis=0)
    if method == "mediana":
        return med.astype(np.float32)
    mad = np.median(np.abs(stack - med), axis=0) * 1.4826
    ok = np.abs(stack - med) <= sigma * np.maximum(mad, 1e-6)
    s = np.where(ok, stack, 0).sum(axis=0)
    c = ok.sum(axis=0)
    return np.where(c > 0, s / np.maximum(c, 1), med).astype(np.float32)
