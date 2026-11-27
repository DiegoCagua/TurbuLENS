flat = a.reshape(n, -1)
bg = np.median(flat, axis=1)
mad = np.median(np.abs(flat - bg[:, None]), axis=1) * 1.4826
noise = np.maximum(mad, 0.5).astype(np.float32)
sub = a - bg[:, None, None]
s3 = _box(sub, 3)
Y = np.arange(h, dtype=np.float32)[None, :, None]
X = np.arange(w, dtype=np.float32)[None, None, :]

s3f = s3.reshape(n, -1)
i_pk = np.argmax(s3f, axis=1)
peak3 = s3f[ar, i_pk]
thr = np.maximum(cfg.threshold_frac * peak3, 4.0 * noise / 3.0)
fg = (s3 > thr[:, None, None]) & (sub > thr[:, None, None])
wgt = np.where(fg, sub - thr[:, None, None], 0.0).astype(np.float32)
