"""
GameDub AI - Ana Giriş Noktası
==============================

Akış:
Capture -> OCR -> Analyzer -> Translation -> Speaker -> Voice(+Cache) -> Audio
                                                    \\-> Overlay

OCR/analiz döngüsü ayrı bir thread'de çalışır, Overlay'in tkinter
mainloop'u ana thread'i kullanır (tkinter thread-safe değildir).
"""

import sys
import threading
import traceback

from config import CONFIG
from engines.capture_engine import CaptureEngine
from engines.ocr_engine import OCREngine
from engines.subtitle_analyzer import SubtitleAnalyzer
from engines.translation_engine import TranslationEngine
from engines.speaker_engine import SpeakerEngine
from engines.voice_engine import VoiceEngine
from engines.cache_engine import CacheEngine
from engines.audio_engine import AudioEngine
from engines.overlay_engine import OverlayEngine


class GameDubApp:
    def __init__(self, config=CONFIG):
        self.config = config
        self.capture = CaptureEngine(config.capture)
        self.ocr = OCREngine(config.ocr)
        self.analyzer = SubtitleAnalyzer(config.analyzer)
        self.translator = TranslationEngine(config.translation)
        self.speaker = SpeakerEngine(config.speaker)
        self.voice = VoiceEngine(config.voice)
        self.cache = CacheEngine(config.cache)
        self.audio = AudioEngine(config.audio)
        self.overlay = OverlayEngine(config.overlay)

        self._running = threading.Event()
        self._running.set()

    def _handle_subtitle(self, subtitle: dict) -> None:
        normalized = subtitle["normalized"]
        voice_id = self.speaker.resolve(subtitle)

        turkish = self.translator.translate(subtitle["raw"])

        wav_bytes = self.cache.get(normalized, voice_id)
        if wav_bytes is None:
            wav_bytes = self.voice.synthesize(turkish, voice_id)
            self.cache.put(normalized, voice_id, wav_bytes)

        self.audio.enqueue(wav_bytes)
        self.overlay.show(translated_text=turkish, source_text=subtitle["raw"])

    def _pipeline_loop(self) -> None:
        for frame in self.capture.stream():
            if not self._running.is_set():
                break
            try:
                ocr_results = self.ocr.read(frame)
                subtitle = self.analyzer.process(ocr_results)
                if subtitle:
                    self._handle_subtitle(subtitle)
            except Exception:
                # Pipeline bir kare için patlarsa tüm uygulamayı düşürmesin
                traceback.print_exc(file=sys.stderr)

    def run(self) -> None:
        worker = threading.Thread(target=self._pipeline_loop, daemon=True)
        worker.start()
        try:
            if self.config.overlay.enabled:
                self.overlay.run_forever()   # ana thread'i tkinter'a devret
            else:
                worker.join()
        except KeyboardInterrupt:
            pass
        finally:
            self._running.clear()
            self.audio.shutdown()


if __name__ == "__main__":
    app = GameDubApp()
    app.run()
