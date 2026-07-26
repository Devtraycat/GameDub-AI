"""
Audio Engine
------------
TTS ve ses çalma işini ayrı bir thread'de, kuyruk (queue) üzerinden yapar.
OCR/analiz thread'i asla burada beklemez.

Yeni bir konuşma geldiğinde (interrupt_on_new_line=True ise) o anki
oynatılan ses durdurulup yenisi çalınır.
"""

import io
import queue
import threading

try:
    import simpleaudio as sa
except ImportError:
    sa = None


class AudioEngine:
    def __init__(self, config):
        self.config = config
        self._queue: queue.Queue = queue.Queue(maxsize=config.queue_max_size)
        self._current_playback = None
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def enqueue(self, wav_bytes: bytes) -> None:
        if self.config.interrupt_on_new_line:
            self._stop_current()
            # kuyrukta bekleyen eski sesleri temizle, en güncel öncelikli
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
        try:
            self._queue.put_nowait(wav_bytes)
        except queue.Full:
            pass  # kuyruk doluysa en yeni sesi feda etmek yerine sessizce atla

    def _stop_current(self) -> None:
        if self._current_playback is not None:
            try:
                self._current_playback.stop()
            except Exception:
                pass

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                wav_bytes = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            self._play(wav_bytes)

    def _play(self, wav_bytes: bytes) -> None:
        if sa is None:
            return  # ses kütüphanesi yoksa sessizce geç (test ortamı vb.)
        wave_obj = sa.WaveObject.from_wave_file(io.BytesIO(wav_bytes))
        self._current_playback = wave_obj.play()

    def shutdown(self) -> None:
        self._stop_event.set()
        self._stop_current()
