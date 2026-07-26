"""
RapidOCR eklentisi.
Küçük, CPU'da hızlı çalışan, PyTorch bağımlılığı olmayan bir OCR motoru.
pip install rapidocr-onnxruntime
"""

import numpy as np


class OCRPlugin:
    def __init__(self, lang: str = "en"):
        self.lang = lang
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as e:
            raise RuntimeError(
                "rapidocr-onnxruntime kurulu değil. "
                "`pip install rapidocr-onnxruntime` çalıştırın."
            ) from e
        self._engine = RapidOCR()

    def recognize(self, image: np.ndarray) -> list[dict]:
        result, _ = self._engine(image)
        output = []
        if not result:
            return output
        for box, text, confidence in result:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)

            # Kutunun ortalama rengini örnekle (konuşmacı-renk eşlemesi için)
            cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
            color = None
            if 0 <= cy < image.shape[0] and 0 <= cx < image.shape[1]:
                b, g, r = image[cy, cx][:3]
                color = (int(r), int(g), int(b))

            output.append({
                "text": text,
                "confidence": float(confidence),
                "box": (x1, y1, x2, y2),
                "color": color,
            })
        return output
