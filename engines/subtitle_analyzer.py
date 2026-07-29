"""
Subtitle Analyzer
------------------
OCR'nin ürettiği ham metni normalize eder, tekrarları eler, kararlı
(stable) altyazıyı tespit eder.

"Hello.", "Hello...", "HELLO", "Hello!" hepsi aynı cümleye indirgenir.
"""

import logging
import re
import difflib
from collections import deque

log = logging.getLogger(__name__)


def normalize(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"[.\-_~`]+$", "", t)          # sondaki noktalama
    t = re.sub(r"[^\w\s'çğıöşüÇĞİÖŞÜ]", "", t)  # noktalama işaretleri
    t = re.sub(r"\s+", " ", t)
    return t.strip()


class SubtitleAnalyzer:
    def __init__(self, config):
        self.config = config
        self._recent = deque(maxlen=config.max_history)
        self._pending_text = None
        self._pending_count = 0

        # v1.6: isim etiketi artık metnin BAŞINDA olmak zorunda değil.
        # Eskiden `re.match(r"^İsim: ...$")` kullanılıyordu; bu, OCR'nin
        # birden fazla kutuyu (ör. isim etiketi + diyalog kutusu) tek bir
        # satırda birleştirdiği ya da isim etiketinin altyazının hemen
        # başında değil ortasında/başka bir öğeden sonra çıktığı durumlarda
        # hiç eşleşmiyordu -> konuşmacı hep "isimsiz" (renk/dönüşümlü)
        # yoluna düşüyor, ton hep aynı kalıyordu. `re.search` ile, desen
        # metnin neresinde geçerse geçsin yakalanır.
        pattern = getattr(config, "name_pattern", None) or (
            r"([A-ZÇĞİÖŞÜ][a-zçğıöşüÇĞİÖŞÜ]*)\s*:\s*(.+)"
        )
        try:
            self._name_re = re.compile(pattern)
        except re.error:
            log.warning("Geçersiz isim etiketi deseni (%r), varsayılana dönülüyor.", pattern)
            self._name_re = re.compile(r"([A-ZÇĞİÖŞÜ][a-zçğıöşüÇĞİÖŞÜ]*)\s*:\s*(.+)")

    def _is_similar(self, a: str, b: str) -> bool:
        if not a or not b:
            return False
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        return ratio >= self.config.similarity_threshold

    def process(self, ocr_results: list[dict]) -> dict | None:
        """
        Bir kare için OCR sonuçlarını alır, normalize eder.
        Sadece "kararlı" (stable_frames kere üst üste görülen) yeni bir
        altyazı olduğunda dict döner, yoksa None döner (gürültü/aynı kare).

        Dönüş: {"raw": str, "normalized": str, "name": str|None, "color": tuple|None}
        """
        if not ocr_results:
            self._pending_text = None
            self._pending_count = 0
            return None

        raw_text = " ".join(r["text"] for r in ocr_results).strip()
        norm = normalize(raw_text)
        color = ocr_results[0].get("color")

        # İsim etiketi tespiti: "John: Hello." gibi, metnin başında olması
        # ZORUNLU değil - OCR birden fazla kutuyu birleştirdiğinde ("HUD John:
        # Hello." gibi) veya isim ayrı bir satırda gelip diğer metinle
        # birleştiğinde de yakalanır (bkz. __init__ - re.search, anchor yok).
        name = None
        name_match = self._name_re.search(raw_text)
        if name_match:
            name = name_match.group(1)
            raw_text = name_match.group(2)
            norm = normalize(raw_text)

        # Aynı altyazı zaten işlendiyse -> gürültü, atla
        if self._recent and self._is_similar(norm, self._recent[-1]):
            return None

        # Kararlılık kontrolü: aynı metin art arda kaç kare geldi
        if self._pending_text and self._is_similar(norm, self._pending_text):
            self._pending_count += 1
        else:
            self._pending_text = norm
            self._pending_count = 1

        if self._pending_count < self.config.stable_frames:
            return None  # henüz kararlı değil, bekle

        # Kararlı ve yeni -> kabul et
        self._recent.append(norm)
        self._pending_text = None
        self._pending_count = 0

        return {"raw": raw_text.strip(), "normalized": norm, "name": name, "color": color}
