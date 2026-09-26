from typing import Optional

import numpy as np

# 1€ Filter (One Euro Filter) - Casiez et al.
# Compared with a plain EMA, the cut-off frequency is raised while the signal is
# moving fast, which removes jitter when a face is still and avoids ghosting
# (lag) when the face moves quickly.

class LowPassFilter:
    """Low pass filter that works on scalars as well as on numpy arrays."""

    def __init__(self):
        self.hat_x_prev: Optional[np.ndarray] = None

    def filter(self, x, alpha):
        x = np.asarray(x, dtype=np.float64)
        if self.hat_x_prev is None or self.hat_x_prev.shape != x.shape:
            self.hat_x_prev = x.copy()
            return self.hat_x_prev
        alpha = np.asarray(alpha, dtype=np.float64)
        self.hat_x_prev = alpha * x + (1.0 - alpha) * self.hat_x_prev
        return self.hat_x_prev

    def reset(self):
        self.hat_x_prev = None


def alpha_from_cutoff(cutoff, dt: float, shape: tuple) -> np.ndarray:
    """Convert a cut-off frequency (Hz) into the low pass filter alpha."""
    tau = 1.0 / (2.0 * np.pi * np.asarray(cutoff, dtype=np.float64))
    alpha = 1.0 / (1.0 + tau / dt)
    return np.broadcast_to(alpha, shape).astype(np.float64)


class OneEuroFilterSet:
    """Vectorised 1€ filter for a set of 2D points of shape (N, 2).

    Every coordinate is filtered independently, so a single instance can smooth
    the 5 ArcFace keypoints or the full 203 point landmark set.
    """

    def __init__(self, freq: float = 30.0, min_cutoff: float = 1.0, beta: float = 0.01, d_cutoff: float = 1.0):
        self.freq = max(float(freq), 1.0)
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.last_raw: Optional[np.ndarray] = None
        self.last_time: Optional[float] = None

    def reset(self):
        self.x_filter.reset()
        self.dx_filter.reset()
        self.last_raw = None
        self.last_time = None

    def filter(self, values: np.ndarray, timestamp: Optional[float] = None) -> np.ndarray:
        values = np.asarray(values, dtype=np.float64)
        original_dtype = np.asarray(values).dtype

        if timestamp is None:
            timestamp = 0.0 if self.last_time is None else self.last_time + 1.0 / self.freq

        # First sample, or the point count changed (different landmark model):
        # no history to filter against, pass the value through unchanged.
        if self.last_time is None or self.last_raw is None or self.last_raw.shape != values.shape:
            self.reset()
            self.last_time = timestamp
            self.last_raw = values.copy()
            self.x_filter.filter(values, np.ones_like(values))
            self.dx_filter.filter(np.zeros_like(values), np.ones_like(values))
            return values.astype(original_dtype, copy=False)

        dt = timestamp - self.last_time
        if dt <= 0.0:
            dt = 1.0 / self.freq

        dx = (values - self.last_raw) / dt
        dx_hat = self.dx_filter.filter(dx, alpha_from_cutoff(self.d_cutoff, dt, values.shape))
        cutoff = self.min_cutoff + self.beta * np.abs(dx_hat)
        x_hat = self.x_filter.filter(values, alpha_from_cutoff(cutoff, dt, values.shape))

        self.last_time = timestamp
        self.last_raw = values.copy()
        return x_hat.astype(original_dtype, copy=False)
