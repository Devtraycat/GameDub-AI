"""
Capture Engine
--------------
Tek görevi: ekran görüntüsü yakalamak.
Girdi: yok (config'ten okur)
Çıktı: numpy array (BGR image)

Başka hiçbir modülü bilmez. OCR'ye, çeviriye karışmaz.
"""

import time
import numpy as np

try:
    import mss
except ImportError:
    mss = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None


class CaptureEngine:
    def __init__(self, config):
        self.config = config
        if mss is None:
            raise RuntimeError(
                "mss kütüphanesi kurulu değil. `pip install mss` çalıştırın."
            )
        self._sct = mss.mss()

    def _get_bbox(self):
        cfg = self.config
        if cfg.mode == "fullscreen":
            monitor = self._sct.monitors[cfg.monitor_index + 1]
            return monitor
        elif cfg.mode == "region":
            left, top, right, bottom = cfg.region
            return {
                "left": left,
                "top": top,
                "width": right - left,
                "height": bottom - top,
            }
        elif cfg.mode == "window":
            if gw is None:
                raise RuntimeError(
                    "Pencere modu için `pip install pygetwindow` gerekli."
                )
            windows = gw.getWindowsWithTitle(cfg.window_title or "")
            if not windows:
                raise RuntimeError(f"Pencere bulunamadı: {cfg.window_title}")
            w = windows[0]
            return {"left": w.left, "top": w.top, "width": w.width, "height": w.height}
        else:
            raise ValueError(f"Bilinmeyen capture modu: {cfg.mode}")

    def grab(self) -> np.ndarray:
        """Tek kare yakalar ve numpy array (H, W, 3 - BGR) olarak döner."""
        bbox = self._get_bbox()
        shot = self._sct.grab(bbox)
        img = np.array(shot)  # BGRA
        return img[:, :, :3]  # BGR

    def stream(self):
        """Config'teki fps'e göre sürekli kare üretir (generator)."""
        interval = 1.0 / max(self.config.fps, 1)
        while True:
            t0 = time.time()
            yield self.grab()
            elapsed = time.time() - t0
            time.sleep(max(0.0, interval - elapsed))
