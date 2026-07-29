"""
OCR Engine
----------
Tek görevi: image -> text.
Gerçek OCR işini plugins/ocr/ altındaki eklentiye devreder.
Yarın OCR motoru değişirse sadece plugin dosyası değişir, burası değişmez.

v1.7 - acil düzeltmeler:
------------------------
1) "Türkçe karakterler İngilizce gibi okunuyor": RapidOCR'ın gömülü tanıma
   sözlüğü ç/ğ/ı/ö/ş/ü/İ karakterlerini İÇERMİYOR - motor "tr" seçilse
   bile en yakın Latin harfe indirger. Tek gerçek çözüm Tesseract'ın "tur"
   dil paketini kullanmak. Kullanıcı Ayarlar'dan sadece dili "tr" yapıp
   motoru "rapidocr"da unutsa bile YANLIŞ sonuç almaması için, `lang=="tr"`
   olduğunda motor burada OTOMATİK olarak tesseract'a zorlanır (kullanıcı
   ayrıca motoru elle "rapidocr" seçse de).
2) "Küçük / arka planı olmayan beyaz yazıyı hiç algılamıyor": OCR'ye
   verilmeden önce görüntü 2x büyütülüp kontrastı güçlendiriliyor (CLAHE).
   İnce/küçük fontlar ve arka plandan ayıracak bir panel olmayan altyazılar
   için tanıma oranını ciddi şekilde artırır.
"""

import logging
import importlib
import numpy as np

log = logging.getLogger(__name__)

try:
    import cv2
except ImportError:
    cv2 = None


class OCREngine:
    def __init__(self, config):
        self.config = config

        engine_name = config.engine
        if config.lang == "tr" and engine_name != "tesseract":
            log.warning(
                "ocr.lang='tr' seçili ama motor '%s'. RapidOCR Türkçe "
                "karakterleri (ç,ğ,ı,ö,ş,ü,İ) doğru tanıyamadığı için motor "
                "otomatik olarak 'tesseract'a zorlanıyor.",
                engine_name,
            )
            engine_name = "tesseract"

        module = importlib.import_module(f"plugins.ocr.{engine_name}_plugin")
        if engine_name == "tesseract":
            self._backend = module.OCRPlugin(
                lang=config.lang, tesseract_cmd=getattr(config, "tesseract_cmd", "")
            )
        else:
            self._backend = module.OCRPlugin(lang=config.lang)
        self._active_engine = engine_name

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Küçük/ince/arka plansız altyazı metnini yakalama oranını artırmak
        için: 2x büyütme + kontrast güçlendirme (CLAHE). OCR motoruna göre
        değil, tamamen bu katmanda yapılır - böylece hem rapidocr hem
        tesseract aynı iyileştirmeden faydalanır.
        """
        if cv2 is None or not getattr(self.config, "enhance_contrast", True):
            return image

        h, w = image.shape[:2]
        # Çok küçük bölgelerde büyütme ucuzdur ve gecikmeye neredeyse hiç
        # etki etmez; çok büyük bölgelerde (ör. tam ekran yanlışlıkla
        # seçildiyse) maliyeti kontrol altında tutmak için atla.
        if h * w > 3_000_000:
            return image

        upscaled = cv2.resize(image, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray)
        # Tekrar 3 kanala çevir: bazı OCR eklentileri (ör. rapidocr) renkli
        # görüntü bekliyor; tek kanallı gri veriyorsak da recognize()
        # içindeki cvtColor çağrıları zaten gri kabul ediyor.
        enhanced = cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)
        return enhanced

    def read(self, image: np.ndarray) -> list[dict]:
        """
        Döndürülen format:
        [{"text": str, "confidence": float, "box": (x1,y1,x2,y2), "color": (r,g,b) | None}, ...]

        Not: "color" örneklemesi orijinal (büyütülmemiş) görüntüden
        yapılmaya devam eder ki konuşmacı-renk eşleşmesi bozulmasın; bu
        yüzden renk örneklemesi backend'lerde zaten orijinal box koordinatına
        göre çalışıyor olsa da, büyütülmüş görüntüde box'lar 2x ölçekte
        döner. Bu yüzden burada box'ları geri 2'ye bölüyoruz.
        """
        processed = self._preprocess(image)
        scale = 2 if (processed is not image) else 1

        results = self._backend.recognize(processed)
        output = []
        for r in results:
            if r["confidence"] < self.config.min_confidence:
                continue
            if scale != 1 and r.get("box"):
                x1, y1, x2, y2 = r["box"]
                r = {**r, "box": (x1 / scale, y1 / scale, x2 / scale, y2 / scale)}
                # Renk büyütülmüş/gri görüntüden geldiği için orijinalden yeniden örnekle
                cx, cy = int((x1 / scale + x2 / scale) / 2), int((y1 / scale + y2 / scale) / 2)
                if 0 <= cy < image.shape[0] and 0 <= cx < image.shape[1]:
                    b, g, rr = image[cy, cx][:3]
                    r["color"] = (int(rr), int(g), int(b))
            output.append(r)
        return output
