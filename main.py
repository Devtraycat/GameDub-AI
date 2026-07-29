"""
GameDub AI - Ana Giriş Noktası
==============================

Akış:
Capture -> OCR -> Analyzer  ==(kuyruk)==>  Translation -> Speaker -> Voice(+Cache) -> Audio
                                                                            \\-> Overlay

Tkinter mainloop'u (Kontrol Paneli + Overlay) ana thread'i kullanır -
Tkinter thread-safe değildir, bu yüzden GUI'ye dokunan her şey ana
thread üzerinden, `after()` ile zamanlanmış olarak yapılır (bkz.
overlay_engine.py, control_panel.py).

v1.6 değişiklikleri (performans taraması sonrası - "sistem aşırı yavaş"):
- ÖNCE: Capture -> OCR -> Analiz -> Çeviri -> TTS -> Ses, TEK bir worker
  thread'de, tamamen SIRALI çalışıyordu. Çeviri/TTS ağ çağrıları (deepl,
  google, edge_tts) birkaç saniye sürebildiğinden, bu süre boyunca bir
  sonraki kare hiç yakalanmıyordu - ekran donmuş gibi davranıyordu ve
  yeni diyalog satırları kaçırılıyordu.
- ŞİMDİ: Pipeline ikiye bölündü.
    1) "GameDubPipeline" thread'i: sadece Capture -> OCR -> Analiz yapar,
       kararlı yeni bir altyazı bulunca `_subtitle_queue`'ya koyar ve HİÇ
       BEKLEMEDEN bir sonraki kareye geçer.
    2) "GameDubSpeech" thread'i: kuyruktan altyazı alır, çeviri + TTS +
       ses + overlay işini yapar. Bu iş ne kadar yavaş olursa olsun,
       yakalama/OCR asla bloklanmaz.
  Kuyruk doluysa (TTS/çeviri OCR'dan çok daha yavaş kalırsa) en eski
  bekleyen altyazı atılır - amaç geçmişi yetiştirmek değil, ekranla
  senkron kalmaktır (AudioEngine'in "interrupt_on_new_line" mantığıyla
  tutarlı).
- Değişmeyen kare artık OCR'den hiç geçirilmiyor (`capture.skip_unchanged`).
  Oyun ekranında altyazı sabit kaldığı ya da hiç altyazı olmadığı sürece
  (ki oyun zamanının büyük bölümü budur) bu, en pahalı adım olan OCR'yi
  tamamen atlar.
- Çeviri artık önbelleğe alınıyor: aynı cümle tekrar geldiğinde (çok
  yaygın - menüler, tekrarlanan barklar vb.) çeviri sağlayıcısına HİÇ
  gidilmiyor; eskiden bu her seferinde yeniden çevriliyordu (yalnızca
  TTS sesi önbellekten geliyordu, ama çeviri ağ çağrısı yine de
  yapılıyordu - gereksiz gecikmenin büyük bölümü buradan geliyordu).
- "direct_tts" modu: oyun zaten Türkçe altyazılıysa çeviri adımı komple
  atlanır, OCR metni doğrudan TTS'e gider (bkz. _handle_subtitle).
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
import traceback

import numpy as np

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
from utils.log_bus import configure_logging
from utils.settings_store import save_region

log = logging.getLogger(__name__)


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

        # v1.7: "algılandıktan sonra sese dönene kadar yavaş" şikayetinin bir
        # parçası, TTS motorunun (özellikle Piper - model dosyası indirme/
        # onnxruntime oturumu açma) İLK gerçek replikte "soğuk" başlamasıydı.
        # Bu maliyeti oyuna başlamadan önce, arka planda karşılıyoruz; kontrol
        # paneli/bölge seçimiyle uğraşırken sessizce tamamlanır.
        threading.Thread(target=self._preload_voice, daemon=True, name="GameDubVoicePreload").start()

        self._stop_event = threading.Event()
        self._stop_event.set()  # başlangıçta "durdurulmuş" say
        self._worker: threading.Thread | None = None
        self._speech_worker: threading.Thread | None = None

        # v1.6: OCR/analiz thread'i ile çeviri/TTS thread'i arasındaki köprü.
        # Küçük tutulur ve doluyken en ESKİ öğe atılır: amaç geriye dönük
        # her repliği yetiştirmek değil, ekranla senkron kalmaktır.
        self._subtitle_queue: "queue.Queue[dict]" = queue.Queue(
            maxsize=max(2, config.audio.queue_max_size // 2)
        )

        # v1.6: aynı cümlenin tekrar tekrar ağ üzerinden çevrilmesini önler.
        self._translation_cache: dict[str, str] = {}
        self._translation_cache_lock = threading.Lock()

        # v1.6: değişmeyen kareyi atlamak için önceki karenin küçültülmüş imzası.
        self._last_frame_signature: np.ndarray | None = None

        self._status_lock = threading.Lock()
        self._status = {
            "running": False,
            "frame_count": 0,
            "frames_skipped": 0,
            "error_count": 0,
            "last_source": None,
            "last_translation": None,
        }

    # ------------------------------------------------------------ status

    def get_status(self) -> dict:
        with self._status_lock:
            status = dict(self._status)
        status["region_info"] = self.capture.get_region()
        return status

    def _update_status(self, **kwargs) -> None:
        with self._status_lock:
            self._status.update(kwargs)

    def _increment_status(self, key: str) -> None:
        with self._status_lock:
            self._status[key] = self._status.get(key, 0) + 1

    # ------------------------------------------------------------ region

    def update_region(self, region: tuple) -> None:
        """Bölge seçme aracından çağrılır: canlı günceller + diske kalıcı kaydeder."""
        self.capture.set_region(region)
        save_region(region)
        self._last_frame_signature = None  # yeni bölge = farklı boyut, kıyaslama sıfırlansın
        log.info("Yeni bölge kaydedildi (bir sonraki açılışta da hatırlanacak): %s", region)

    # ----------------------------------------------------------- settings

    def apply_setting(self, path: str, value) -> None:
        """
        Kontrol Panelindeki "Ayarlar" sekmesinden çağrılır: config'e canlı
        yazar, diske kalıcı kaydeder ve gerekiyorsa (OCR motoru/dili, isim
        deseni gibi construction-time bağımlılığı olan) ilgili motoru
        yeniden oluşturur. Diğer tüm ayarlar (fps, eşikler, ses/overlay
        ayarları vb.) zaten CONFIG nesnesinden her seferinde canlı okunduğu
        için burada ekstra bir şey yapmaya gerek yoktur.
        """
        from config import set_path
        from utils.settings_store import save_schema_setting

        set_path(self.config, path, value)
        save_schema_setting(path, value)

        if path in ("ocr.engine", "ocr.lang"):
            self.ocr = OCREngine(self.config.ocr)
            log.info("OCR motoru yeniden yüklendi (%s = %s).", path, value)
        elif path == "analyzer.name_pattern":
            self.analyzer = SubtitleAnalyzer(self.config.analyzer)
            log.info("İsim etiketi deseni güncellendi.")

        log.info("Ayar güncellendi: %s = %r", path, value)

    # ---------------------------------------------------------- pipeline

    def _preload_voice(self) -> None:
        try:
            log.info("TTS motoru arka planda ön yükleniyor (ilk replik gecikmesini azaltmak için)...")
            self.voice.preload()
            log.info("TTS motoru hazır.")
        except Exception:
            log.exception("TTS ön yükleme sırasında hata (ilk replikte tekrar denenecek).")

    def _translate_cached(self, raw_text: str, normalized: str) -> str:
        """
        v1.6: Aynı normalize edilmiş cümle daha önce çevrildiyse (çok sık
        olur - tekrarlanan barklar, menü metinleri vb.) çeviri sağlayıcısına
        HİÇ gidilmez. Eskiden yalnızca TTS sesi önbelleğe alınıyordu; çeviri
        adımı önbellek isabet etse bile her seferinde tekrar çalışıyordu.
        """
        with self._translation_cache_lock:
            cached = self._translation_cache.get(normalized)
        if cached is not None:
            return cached

        translated = self.translator.translate(raw_text)
        with self._translation_cache_lock:
            self._translation_cache[normalized] = translated
            if len(self._translation_cache) > 5000:
                self._translation_cache.pop(next(iter(self._translation_cache)))
        return translated

    def _handle_subtitle(self, subtitle: dict) -> None:
        normalized = subtitle["normalized"]
        voice_id = self.speaker.resolve(subtitle)

        # v1.6: "direct_tts" -> oyun zaten hedef dilde (Türkçe) altyazılı,
        # çeviri adımı tamamen atlanır; OCR'nin okuduğu metin doğrudan
        # seslendirilir. source_lang == target_lang ise de aynı sonuç
        # otomatik olarak geçerli olur.
        cfg = self.config.translation
        skip_translation = getattr(cfg, "direct_tts", False) or cfg.source_lang == cfg.target_lang
        if skip_translation:
            turkish = subtitle["raw"]
        else:
            turkish = self._translate_cached(subtitle["raw"], normalized)

        log.info("Altyazı: %r -> %r (ses: %s)", subtitle["raw"], turkish, voice_id)

        wav_bytes = self.cache.get(normalized, voice_id)
        if wav_bytes is None:
            wav_bytes = self.voice.synthesize(turkish, voice_id)
            self.cache.put(normalized, voice_id, wav_bytes)
        else:
            log.debug("Seslendirme önbellekten alındı (yeniden sentez yok).")

        self.audio.enqueue(wav_bytes)
        self.overlay.show(translated_text=turkish, source_text=subtitle["raw"])
        self._update_status(last_source=subtitle["raw"], last_translation=turkish)

    def _frame_unchanged(self, frame) -> bool:
        """
        v1.7 düzeltmesi: eskiden TÜM bölgenin ortalama piksel farkına
        bakılıyordu. Küçük/ince bir altyazı (özellikle arka planı ayıracak
        bir panel yoksa) bölgenin küçük bir kısmını kapladığı için bu
        ortalamayı neredeyse hiç değiştirmiyordu -> "kare aynı" sanılıp OCR
        tamamen atlanıyor, altyazı HİÇ yakalanmıyordu.

        Şimdi bölge NxN hücreye bölünüp EN ÇOK değişen hücreye bakılıyor.
        Küçük bir metin bloğu bile düştüğü hücrede belirgin bir fark
        yaratır, dolayısıyla artık "değişti" olarak doğru tespit edilir.
        """
        if not self.config.capture.skip_unchanged:
            return False

        grid = max(1, self.config.capture.diff_grid)
        # Küçük bir ön-küçültme (::4) hesaplama maliyetini düşürür, hücre
        # bazlı karşılaştırmanın hassasiyetini bozmaz.
        small = frame[::4, ::4].astype(np.int16)
        prev = self._last_frame_signature
        self._last_frame_signature = small
        if prev is None or prev.shape != small.shape:
            return False

        h, w = small.shape[:2]
        gh, gw = max(1, h // grid), max(1, w // grid)
        if gh == 0 or gw == 0:
            diff = float(np.abs(small - prev).mean())
            return diff < self.config.capture.change_threshold

        diff_map = np.abs(small - prev)
        max_cell_diff = 0.0
        for i in range(0, h, gh):
            for j in range(0, w, gw):
                cell = diff_map[i:i + gh, j:j + gw]
                if cell.size == 0:
                    continue
                cell_mean = float(cell.mean())
                if cell_mean > max_cell_diff:
                    max_cell_diff = cell_mean
        return max_cell_diff < self.config.capture.change_threshold

    def _pipeline_loop(self) -> None:
        """Sadece Capture -> OCR -> Analiz. Asla ağ çağrısı beklemez."""
        log.info("Pipeline (yakalama/OCR) worker thread'i başladı.")
        for frame in self.capture.stream():
            if self._stop_event.is_set():
                break
            self._increment_status("frame_count")
            try:
                if self._frame_unchanged(frame):
                    self._increment_status("frames_skipped")
                    continue

                ocr_results = self.ocr.read(frame)
                subtitle = self.analyzer.process(ocr_results)
                if subtitle:
                    self._enqueue_subtitle(subtitle)
            except Exception:
                self._increment_status("error_count")
                log.error("Pipeline bir karede hata verdi (devam ediliyor):\n%s", traceback.format_exc())
        log.info("Pipeline (yakalama/OCR) worker thread'i durdu.")
        self._update_status(running=False)

    def _enqueue_subtitle(self, subtitle: dict) -> None:
        """
        Yeni altyazıyı çeviri/TTS thread'ine devreder. Kuyruk doluysa
        (yakalama çeviri+TTS'ten çok daha hızlı çalıştığı için bu olabilir)
        en eski bekleyeni atıp yenisini koyar - ekranla senkron kalmak,
        geride kalmış eski repliği geç söylemekten önceliklidir.
        """
        try:
            self._subtitle_queue.put_nowait(subtitle)
        except queue.Full:
            try:
                self._subtitle_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._subtitle_queue.put_nowait(subtitle)
            except queue.Full:
                pass

    def _speech_loop(self) -> None:
        """Çeviri -> Konuşmacı -> TTS(+önbellek) -> Ses/Overlay. Yakalamayı asla bloklamaz."""
        log.info("Konuşma (çeviri/TTS) worker thread'i başladı.")
        while not self._stop_event.is_set():
            try:
                subtitle = self._subtitle_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._handle_subtitle(subtitle)
            except Exception:
                self._increment_status("error_count")
                log.error(
                    "Konuşma worker'ı bir replikte hata verdi (devam ediliyor):\n%s",
                    traceback.format_exc(),
                )
        log.info("Konuşma (çeviri/TTS) worker thread'i durdu.")

    # -------------------------------------------------------- start/stop

    def start(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            log.warning("Zaten çalışıyor; tekrar başlatma isteği yok sayıldı.")
            return
        self._stop_event.clear()
        self._last_frame_signature = None
        self._update_status(running=True, error_count=0, frame_count=0, frames_skipped=0)
        self._worker = threading.Thread(target=self._pipeline_loop, daemon=True, name="GameDubPipeline")
        self._speech_worker = threading.Thread(target=self._speech_loop, daemon=True, name="GameDubSpeech")
        self._worker.start()
        self._speech_worker.start()
        log.info("Başlat komutu alındı.")

    def stop(self) -> None:
        if self._stop_event.is_set():
            return
        log.info("Durdur komutu alındı; mevcut iş bitince duracak.")
        self._stop_event.set()
        self._update_status(running=False)

    def shutdown(self) -> None:
        self.stop()
        self.audio.shutdown()

    # -------------------------------------------------------------- run

    def run(self) -> None:
        """
        Kontrol Panelini (ve overlay'i onun içine gömülü olarak) açar,
        Tk mainloop'unu ana thread'de çalıştırır. Pipeline, panel
        üzerindeki Başlat butonuna basılınca ayrı thread'de başlar.
        """
        from control_panel import ControlPanel
        from utils.log_bus import get_queue_handler

        panel = ControlPanel(self, log_queue=get_queue_handler().queue if get_queue_handler() else None)
        self.overlay.attach(master=panel.root)

        try:
            panel.run_forever()
        finally:
            self.shutdown()


if __name__ == "__main__":
    configure_logging()
    app = GameDubApp()
    app.run()
