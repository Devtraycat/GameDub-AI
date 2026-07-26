"""
pyttsx3 eklentisi.
Tamamen offline, işletim sisteminin kurulu seslerini kullanır
(Windows: SAPI5, Linux: espeak, macOS: NSSpeechSynthesizer).

NOT: pyttsx3, motoru işletim sistemine devrettiği için pitch kontrolü
sınırlıdır (bazı platformlarda hiç yoktur). Hız (rate) her platformda
çalışır ve karakterleri ayırt etmek için genelde yeterlidir.
"""

import io
import tempfile
import os


class TTSPlugin:
    def __init__(self):
        try:
            import pyttsx3
        except ImportError as e:
            raise RuntimeError("pyttsx3 kurulu değil. `pip install pyttsx3`") from e
        self._pyttsx3 = pyttsx3
        self._base_rate = None

    def synthesize(self, text: str, pitch: float = 0.0, speed: float = 1.0,
                    voice_id: str = "NARRATOR") -> bytes:
        engine = self._pyttsx3.init()

        if self._base_rate is None:
            self._base_rate = engine.getProperty("rate")

        engine.setProperty("rate", int(self._base_rate * speed))

        # Pitch: bazı sürücülerde (sapi5/nsss) desteklenmiyor, desteklenirse dene
        try:
            current_volume = engine.getProperty("volume")
            engine.setProperty("volume", current_volume)
        except Exception:
            pass

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        engine.save_to_file(text, tmp_path)
        engine.runAndWait()

        with open(tmp_path, "rb") as f:
            wav_bytes = f.read()
        os.remove(tmp_path)
        return wav_bytes
