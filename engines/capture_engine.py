"""
Capture Engine
--------------
Tek görevi: ekran görüntüsü yakalamak.
Girdi: yok (config'ten okur)
Çıktı: numpy array (BGR image)

Başka hiçbir modülü bilmez. OCR'ye, çeviriye karışmaz.

Önemli - thread güvenliği:
`mss` kütüphanesi thread-safe DEĞİLDİR; resmi dokümantasyonu her
thread'in kendi `mss.mss()` örneğini oluşturmasını şart koşar
(python-mss dokümantasyonu, "Multithreading" bölümü). Bu uygulamada
yakalama işlemi ayrı bir worker thread'de çalışır; bu yüzden `_sct`
burada `threading.local()` ile thread-başına saklanır. Eskiden
`__init__` içinde (ana thread'de) tek bir örnek oluşturulup worker
thread'den kullanılıyordu; bu bazı sistemlerde sessiz donmalara/
hatalara yol açabiliyordu.
"""

from __future__ import annotations

import logging
import threading
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

log = logging.getLogger(__name__)


class CaptureEngine:
    def __init__(self, config):
        self.config = config
        if mss is None:
            raise RuntimeError(
                "mss kütüphanesi kurulu değil. `pip install mss` çalıştırın."
            )
        self._local = threading.local()
        self._lock = threading.Lock()  # config.mode/region gibi paylaşılan alanları korur
        log.info(
            "CaptureEngine başlatıldı (mode=%s, region=%s, fps=%s)",
            config.mode, config.region, config.fps,
        )

    def _sct(self):
        """Çağrıldığı thread'e özel bir `mss` örneği döner (lazy, thread-local)."""
        inst = getattr(self._local, "sct", None)
        if inst is None:
            inst = mss.mss()
            self._local.sct = inst
            log.debug(
                "Bu thread için yeni mss örneği oluşturuldu: %s",
                threading.current_thread().name,
            )
        return inst

    def set_region(self, region: tuple) -> None:
        """Bölge seçme aracından çağrılır; çalışan yakalamayı canlı günceller."""
        with self._lock:
            self.config.mode = "region"
            self.config.region = tuple(int(v) for v in region)
        log.info("Yakalama bölgesi güncellendi: %s", self.config.region)

    def get_region(self):
        with self._lock:
            return self.config.mode, self.config.region

    def _get_bbox(self, sct):
        with self._lock:
            mode = self.config.mode
            region = self.config.region
            monitor_index = self.config.monitor_index
            window_title = self.config.window_title

        if mode == "fullscreen":
            monitor = sct.monitors[monitor_index + 1]
            return monitor
        elif mode == "region":
            left, top, right, bottom = region
            return {
                "left": left,
                "top": top,
                "width": max(1, right - left),
                "height": max(1, bottom - top),
            }
        elif mode == "window":
            if gw is None:
                raise RuntimeError(
                    "Pencere modu için `pip install pygetwindow` gerekli."
                )
            windows = gw.getWindowsWithTitle(window_title or "")
            if not windows:
                raise RuntimeError(f"Pencere bulunamadı: {window_title}")
            w = windows[0]
            return {"left": w.left, "top": w.top, "width": w.width, "height": w.height}
        else:
            raise ValueError(f"Bilinmeyen capture modu: {mode}")

    def grab(self) -> np.ndarray:
        """Tek kare yakalar ve numpy array (H, W, 3 - BGR) olarak döner."""
        sct = self._sct()
        bbox = self._get_bbox(sct)
        shot = sct.grab(bbox)
        img = np.array(shot)  # BGRA
        return img[:, :, :3]  # BGR

    def stream(self):
        """Config'teki fps'e göre sürekli kare üretir (generator)."""
        log.info("Yakalama döngüsü başladı (fps=%s).", self.config.fps)
        frame_count = 0
        while True:
            interval = 1.0 / max(self.config.fps, 1)
            t0 = time.time()
            try:
                frame = self.grab()
            except Exception:
                log.exception("Kare yakalanırken hata oluştu; 1 sn sonra tekrar denenecek.")
                time.sleep(1.0)
                continue
            frame_count += 1
            if frame_count == 1:
                log.info("İlk kare başarıyla yakalandı: shape=%s", frame.shape)
            yield frame
            elapsed = time.time() - t0
            time.sleep(max(0.0, interval - elapsed))
