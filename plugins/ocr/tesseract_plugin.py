"""
Tesseract fallback OCR eklentisi.
RapidOCR kurulamayan sistemlerde (ör. bazı Linux/ARM kurulumları) yedek olarak kullanılır.
pip install pytesseract  (+ sistemde tesseract-ocr kurulu olmalı)
"""

import numpy as np


class OCRPlugin:
    def __init__(self, lang: str = "en"):
        self.lang = lang
        try:
            import pytesseract
            import cv2
        except ImportError as e:
            raise RuntimeError(
                "pytesseract/opencv kurulu değil. `pip install pytesseract opencv-python`"
            ) from e
        self._pytesseract = pytesseract
        self._cv2 = cv2

    def recognize(self, image: np.ndarray) -> list[dict]:
        gray = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2GRAY)
        data = self._pytesseract.image_to_data(
            gray, lang=self.lang, output_type=self._pytesseract.Output.DICT
        )
        output = []
        n = len(data["text"])
        for i in range(n):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])
            if not text or conf < 0:
                continue
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            output.append({
                "text": text,
                "confidence": conf / 100.0,
                "box": (x, y, x + w, y + h),
                "color": None,
            })
        return output
