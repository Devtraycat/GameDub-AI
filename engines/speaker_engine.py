"""
Speaker Engine
--------------
Konuşmacıyı tahmin eder. Öncelik sırası:
1) İsim satırı geldiyse -> isme sabit ses ata (kalıcı hafıza)
2) Renk bilgisi varsa -> renge göre ata
3) Hiçbiri yoksa -> dönüşümlü (alternating) heuristik

Diyalog geçmişini tutar; aynı karakter her zaman aynı sesle konuşur.
"""

from collections import deque


class SpeakerEngine:
    def __init__(self, config):
        self.config = config
        self._name_to_voice: dict[str, str] = {}
        self._color_to_voice: dict[tuple, str] = {}
        self._voice_pool = [chr(ord("A") + i) for i in range(config.max_speakers)]
        self._next_voice_idx = 0
        self._last_voice = None
        self._history = deque(maxlen=20)

    def _assign_new_voice(self) -> str:
        voice = self._voice_pool[self._next_voice_idx % len(self._voice_pool)]
        self._next_voice_idx += 1
        return voice

    def resolve(self, subtitle: dict) -> str:
        """
        subtitle: SubtitleAnalyzer.process() çıktısı
        Döner: voice_id (örn "A", "B")
        """
        name = subtitle.get("name")
        color = subtitle.get("color")

        if name:
            if name not in self._name_to_voice:
                self._name_to_voice[name] = self._assign_new_voice()
            voice = self._name_to_voice[name]

        elif color:
            if color not in self._color_to_voice:
                self._color_to_voice[color] = self._assign_new_voice()
            voice = self._color_to_voice[color]

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
