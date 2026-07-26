"""
OCR Engine
----------
Tek görevi: image -> text.
Gerçek OCR işini plugins/ocr/ altındaki eklentiye devreder.
Yarın OCR motoru değişirse sadece plugin dosyası değişir, burası değişmez.
"""

import importlib
import numpy as np


class OCREngine:
    def __init__(self, config):
        self.config = config
        module = importlib.import_module(f"plugins.ocr.{config.engine}_plugin")
        self._backend = module.OCRPlugin(lang=config.lang)

    def read(self, image: np.ndarray) -> list[dict]:
        """
        Döndürülen format:
        [{"text": str, "confidence": float, "box": (x1,y1,x2,y2), "color": (r,g,b) | None}, ...]
        """
        results = self._backend.recognize(image)
        return [r for r in results if r["confidence"] >= self.config.min_confidence]
