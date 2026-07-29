"""
Audio Engine
------------
TTS ve ses çalma işini ayrı bir thread'de, kuyruk (queue) üzerinden yapar.
OCR/analiz thread'i asla burada beklemez.

Yeni bir konuşma geldiğinde (interrupt_on_new_line=True ise) o anki
oynatılan ses durdurulup yenisi çalınır.

Neden sounddevice (eski simpleaudio yerine)?
- simpleaudio yıllardır bakımı yapılmıyor, Windows'ta derleyici (Visual C++
  Build Tools) gerektiriyor, yeni Python sürümleriyle wheel uyumsuzlukları
  yaşanabiliyor. Özel bir hız avantajı da yok — native API'yi minimal
  şekilde sarmalıyor.
- sounddevice, aktif bakımlı PortAudio üzerine kurulu; tüm platformlar için
  derleyicisiz prebuilt wheel sağlıyor, düşük gecikmeli ve numpy ile
  doğrudan çalışıyor.

Neden soundfile ile decode?
- TTS motorları her zaman WAV döndürmüyor: örn. edge-tts varsayılan olarak
  MP3 üretir, pyttsx3 ise WAV üretir. soundfile hem WAV hem MP3'ü (libsndfile
  1.1+ ile) aynı arayüzle numpy array'e çözer; formatın ne olduğunu ayrıca
  bilmemize gerek kalmaz.
"""

import io
import logging
import queue
import sys
import threading

log = logging.getLogger(__name__)

try:
    import sounddevice as sd
except (ImportError, OSError):
    # `sounddevice` paketi kurulu olsa bile, altındaki native PortAudio
    # kütüphanesi sistemde yoksa `import sounddevice` bir ImportError değil
    # OSError fırlatır ("PortAudio library not found"). Sadece ImportError
    # yakalamak bu durumda tüm uygulamayı import anında çökertiyordu.
    sd = None

try:
    import soundfile as sf
except (ImportError, OSError):
    sf = None


class AudioEngine:
    def __init__(self, config):
        self.config = config
        self._queue: queue.Queue = queue.Queue(maxsize=config.queue_max_size)
        self._stop_event = threading.Event()
        if sd is None or sf is None:
            log.warning(
                "Ses çalma devre dışı: sounddevice/soundfile veya altındaki "
                "PortAudio kütüphanesi bulunamadı. Altyazılar üretilecek ama "
                "sesli seslendirme duyulmayacak."
            )
        self._thread = threading.Thread(target=self._worker, daemon=True, name="GameDubAudio")
        self._thread.start()

    def enqueue(self, audio_bytes: bytes) -> None:
        if self.config.interrupt_on_new_line:
            self._stop_current()
            # kuyrukta bekleyen eski sesleri temizle, en güncel öncelikli
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
        try:
            self._queue.put_nowait(audio_bytes)
        except queue.Full:
            pass  # kuyruk doluysa en yeni sesi feda etmek yerine sessizce atla

    def _stop_current(self) -> None:
        if sd is not None:
            try:
                sd.stop()
            except Exception:
                pass

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                audio_bytes = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._play(audio_bytes)
            except Exception as e:
                # Ses cihazı hatası (ör. cihaz yok/çıkarıldı) tüm thread'i
                # öldürmemeli; sıradaki repliği çalmaya devam etsin.
                print(f"[AudioEngine] Çalma hatası, bu replik atlanıyor: {e}",
                      file=sys.stderr)

    def _play(self, audio_bytes: bytes) -> None:
        if sd is None or sf is None:
            return  # ses kütüphaneleri yoksa sessizce geç (test ortamı vb.)
        data, samplerate = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        sd.play(data, samplerate)
        sd.wait()  # bu worker thread'i zaten ayrı; ana thread'i bloklamaz

    def shutdown(self) -> None:
        self._stop_event.set()
        self._stop_current()
