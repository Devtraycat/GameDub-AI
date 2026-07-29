"""
Tesseract fallback OCR eklentisi.
RapidOCR kurulamayan sistemlerde (ör. bazı Linux/ARM kurulumları) yedek olarak kullanılır.
pip install pytesseract  (+ sistemde tesseract-ocr kurulu olmalı)

v1.6: Türkçe altyazı yakalama desteği
--------------------------------------
RapidOCR'ın varsayılan (ch_ppocr tabanlı) tanıma modeli İngilizce + Çince
karakter setine göre eğitilmiştir; ç, ğ, ı, ö, ş, ü, İ gibi Türkçeye özgü
karakterler bu sözlükte yer almaz ve genelde en yakın Latin harfe (ör. "ş"
-> "s") indirgenir ya da düşük güven skoruyla tamamen atlanır. Bu yüzden
`ocr.lang == "tr"` olduğunda (yani oyun zaten Türkçe altyazılıysa ve
doğrudan TTS'e gönderilecekse) bu eklenti kullanılmalı - Tesseract'ın
`tur` dil paketi Türkçe karakter setini tam olarak kapsar.

Not: Tesseract dil paketleri ISO 639-1 değil kendi üç harfli kodlarını
kullanır (`tur`, `eng`), bu yüzden config'teki "tr"/"en" burada eşlenir.
"""

import logging
import numpy as np

log = logging.getLogger(__name__)

# ISO 639-1 (config.ocr.lang) -> tesseract dil paketi kodu
_LANG_MAP = {
    "tr": "tur",
    "en": "eng",
}


class OCRPlugin:
    def __init__(self, lang: str = "en", tesseract_cmd: str = ""):
        self.lang = lang
        self._tess_lang = _LANG_MAP.get(lang, lang)
        try:
            import pytesseract
            import cv2
        except ImportError as e:
            raise RuntimeError(
                "pytesseract/opencv kurulu değil. `pip install pytesseract opencv-python`"
            ) from e
        self._pytesseract = pytesseract
        self._cv2 = cv2

        # v1.7: sabit bir yol koda gömülmez - Windows'ta tesseract.exe PATH'te
        # değilse kullanıcı bunu Ayarlar penceresinden ("Tesseract.exe yolu")
        # girer; boşsa dokunulmaz ve pytesseract PATH üzerinden kendi bulur.
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        if self._tess_lang == "tur":
            try:
                available = pytesseract.get_languages(config="")
            except Exception:
                available = None
            if available is not None and "tur" not in available:
                raise RuntimeError(
                    "Tesseract 'tur' (Türkçe) dil paketi kurulu değil. "
                    "Linux: `sudo apt-get install tesseract-ocr-tur` | "
                    "Windows: Tesseract kurulumunda 'Turkish' dil paketini işaretleyin."
                )

    def recognize(self, image: np.ndarray) -> list[dict]:
        gray = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2GRAY)
        # PSM 6: "tek bir düzgün metin bloğu" - oyun altyazıları için OCR
        # gürültüsünü azaltır ve Türkçe karakterlerin komşu harflerle
        # karışıp yanlış segmentlenmesini engellemeye yardımcı olur.
        config_str = "--psm 6"
        data = self._pytesseract.image_to_data(
            gray, lang=self._tess_lang, config=config_str,
            output_type=self._pytesseract.Output.DICT,
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
