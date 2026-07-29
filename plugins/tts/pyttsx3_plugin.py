"""
pyttsx3 eklentisi.
Tamamen offline, işletim sisteminin kurulu seslerini kullanır
(Windows: SAPI5, Linux: espeak, macOS: NSSpeechSynthesizer).

NOT: pyttsx3, motoru işletim sistemine devrettiği için pitch kontrolü
sınırlıdır (bazı platformlarda hiç yoktur). Hız (rate) her platformda
çalışır ve karakterleri ayırt etmek için genelde yeterlidir.

v1.7 - kritik hız düzeltmesi:
-----------------------------
Eskiden HER `synthesize()` çağrısında `pyttsx3.init()` yeniden
çalıştırılıyordu. Bu, işletim sisteminin TTS motorunu (SAPI5/espeak/NSSS)
sıfırdan ayağa kaldırmak anlamına gelir ve tek başına yüzlerce
milisaniye - bazı sistemlerde saniyeler - sürebilir. "Algılandıktan sonra
sese dönene kadar yavaş" şikayetinin büyük bölümü, bu motor bu zincirde
devredeyken buradan kaynaklanıyordu. Artık motor sadece bir kez
başlatılıp önbelleğe alınıyor (Piper zaten birincil motor olduğu için bu
eklenti artık yalnızca YEDEK olarak devreye giriyor, ama yedek olarak da
hızlı olmalı).
"""

import logging
import os
import tempfile

log = logging.getLogger(__name__)


class TTSPlugin:
    def __init__(self):
        try:
            import pyttsx3
        except ImportError as e:
            raise RuntimeError("pyttsx3 kurulu değil. `pip install pyttsx3`") from e
        self._pyttsx3 = pyttsx3
        self._engine = None
        self._base_rate = None

    def _get_engine(self):
        # v1.7: motor bir kez kurulur, sonraki her çağrıda aynısı kullanılır.
        if self._engine is None:
            self._engine = self._pyttsx3.init()
            self._base_rate = self._engine.getProperty("rate")
        return self._engine

    def synthesize(self, text: str, pitch: float = 0.0, speed: float = 1.0,
                    voice_id: str = "NARRATOR") -> bytes:
        engine = self._get_engine()
        engine.setProperty("rate", int(self._base_rate * speed))

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            with open(tmp_path, "rb") as f:
                wav_bytes = f.read()
        except Exception:
            # Bazı platformlarda (özellikle Windows/SAPI5) tekrar kullanılan
            # motor örneği bir istekten sonra "takılabiliyor". Böyle bir
            # durumda motoru bir kereliğine yeniden kurup tekrar dene -
            # sürekli her seferinde yeniden kurmaktan çok daha ucuz.
            log.warning("pyttsx3 motoru yeniden başlatılıyor (bir defalık).")
            self._engine = None
            engine = self._get_engine()
            engine.setProperty("rate", int(self._base_rate * speed))
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            with open(tmp_path, "rb") as f:
                wav_bytes = f.read()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        return wav_bytes
