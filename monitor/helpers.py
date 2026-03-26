import numpy as np
from config import NOISE_MIN_DBFS


def expand_roi(x1, y1, x2, y2, w, h, expand_ratio=0.15):
    bw = x2 - x1
    bh = y2 - y1
    ex = int(bw * expand_ratio)
    ey = int(bh * expand_ratio)
    nx1 = max(0, x1 - ex)
    ny1 = max(0, y1 - ey)
    nx2 = min(w - 1, x2 + ex)
    ny2 = min(h - 1, y2 + ey)
    return nx1, ny1, nx2, ny2


def dbfs_from_audio(x: np.ndarray):
    rms = float(np.sqrt(np.mean(np.square(x)) + 1e-12))
    db = 20.0 * np.log10(max(rms, 1e-12))
    return max(db, NOISE_MIN_DBFS)
