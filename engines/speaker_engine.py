"""
Speaker Engine
--------------
Konuşmacıyı tahmin eder. Öncelik sırası:
1) İsim satırı geldiyse -> isme sabit ses ata (kalıcı hafıza, isim normalize edilir)
2) Renk bilgisi varsa -> en yakın bilinen renge tolerans dahilinde eşle (v1.5)
3) Hiçbiri yoksa -> dönüşümlü (alternating) heuristik

Diyalog geçmişini tutar; aynı karakter her zaman aynı sesle konuşur.

v1.5 değişiklikleri:
- Renk eşlemesi artık birebir (exact match) değil, öklid mesafesine göre
  tolerans dahilinde en yakın renge atanıyor. Böylece OCR'nin piksel piksel
  okuduğu renkteki küçük sapmalar (anti-aliasing, sıkıştırma artefaktı vb.)
  farklı bir karaktermiş gibi yanlış yeni ses atanmasına yol açmıyor.
- İsimler normalize ediliyor (küçük harf + boşluk temizliği), böylece
  "John", "john", " John " aynı karaktere işaret ediyor.
"""

import math
from collections import deque


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _color_distance(c1: tuple, c2: tuple) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


class SpeakerEngine:
    def __init__(self, config):
        self.config = config
        self._name_to_voice: dict[str, str] = {}
        self._color_to_voice: list[tuple[tuple, str]] = []  # [(color, voice_id), ...]
        self._voice_pool = [chr(ord("A") + i) for i in range(config.max_speakers)]
        self._next_voice_idx = 0
        self._last_voice = None
        self._history = deque(maxlen=20)

        # Renk toleransı: config'te yoksa makul bir varsayılan kullan
        self._color_tolerance = getattr(config, "color_tolerance", 40.0)

    def _assign_new_voice(self) -> str:
        voice = self._voice_pool[self._next_voice_idx % len(self._voice_pool)]
        self._next_voice_idx += 1
        return voice

    def _resolve_by_color(self, color: tuple) -> str:
        best_match = None
        best_distance = float("inf")
        for known_color, voice_id in self._color_to_voice:
            d = _color_distance(color, known_color)
            if d < best_distance:
                best_distance = d
                best_match = voice_id

        if best_match is not None and best_distance <= self._color_tolerance:
            return best_match

        # Yeterince yakın bilinen renk yok -> yeni karakter, yeni ses ata
        voice_id = self._assign_new_voice()
        self._color_to_voice.append((color, voice_id))
        return voice_id

    def resolve(self, subtitle: dict) -> str:
        """
        subtitle: SubtitleAnalyzer.process() çıktısı
        Döner: voice_id (örn "A", "B")
        """
        name = subtitle.get("name")
        color = subtitle.get("color")

        if name:
            key = _normalize_name(name)
            if key not in self._name_to_voice:
                self._name_to_voice[key] = self._assign_new_voice()
            voice = self._name_to_voice[key]

        elif color:
            voice = self._resolve_by_color(color)

        elif self.config.alternate_fallback:
            # dönüşümlü konuşmacı varsayımı: A -> B -> A -> B ...
            if self._last_voice is None:
                voice = self._voice_pool[0]
            else:
                idx = self._voice_pool.index(self._last_voice)
                voice = self._voice_pool[(idx + 1) % len(self._voice_pool)]
        else:
            voice = self._voice_pool[0]

        self._last_voice = voice
        self._history.append((subtitle.get("normalized"), voice))
        return voice
