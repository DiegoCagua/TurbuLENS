def _get(self, i: int) -> bytes:
    b = self._cache.get(i)
    if b is not None:
        return b
    a = i * self._block
    z = min(self.size, a + self._block) - 1
    with self._opener(self.url, timeout=60, headers={"Range": f"bytes={a}-{z}"}) as r:
        status = getattr(r, "status", None) or getattr(r, "code", 206)
        if status != 206:
            raise RangeNotSupported("el servidor no permite descargas parciales")
        data = r.read()
    self.downloaded += len(data)
    if self._progress:
        self._progress(self.downloaded)
    self._cache[i] = data
    self._order.append(i)
    if len(self._order) > 96:  # como máximo 96 bloques en memoria (12 MB con bloques de 128 KB)
        self._cache.pop(self._order.pop(0), None)
    return data
