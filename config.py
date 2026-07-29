"""
GameDub AI - Merkezi Ayarlar
Tüm modüller buradan ayar okur. Hiçbir modül birbirine sabit (hardcoded) değer geçirmez.
"""

from dataclasses import dataclass, field


@dataclass
class CaptureConfig:
    mode: str = "region"          # "fullscreen" | "region" | "window"
    region: tuple = (100, 800, 1800, 1000)   # (left, top, right, bottom) - altyazı alanı
    window_title: str | None = None
    fps: int = 3                   # saniyede kaç kare yakalansın (OCR için yüksek fps gereksiz)
    monitor_index: int = 0
    # v1.6: değişmeyen kareyi tekrar OCR'den geçirmeyi atla (en büyük CPU/hız kazancı).
    skip_unchanged: bool = True
    # v1.7: eskiden TÜM bölgenin ORTALAMA farkı tek bir sayıya indirgeniyordu
    # -> küçük/ince bir altyazı belirdiğinde ortalamayı yeterince değiştirmediği
    # için "değişmedi" sanılıp OCR atlanıyor, altyazı HİÇ yakalanmıyordu. Artık
    # bölge küçük karelere (grid) bölünüp EN ÇOK değişen karenin farkına
    # bakılıyor - küçük bir metin bloğu bile o kareyi net şekilde değiştirir.
    change_threshold: float = 8.0   # bir "hücre"nin bu farkın üstüne çıkması yeter
    diff_grid: int = 6              # bölge kaça bölünüp karşılaştırılsın (6x6)


@dataclass
class OCRConfig:
    engine: str = "rapidocr"       # plugins/ocr/ içindeki dosya adına karşılık gelir
    lang: str = "en"               # "en" | "tr" - "tr" Türkçe karakter setine göre okunur
    min_confidence: float = 0.55
    # v1.7: küçük/ince/arka plansız beyaz yazıyı yakalamak için 2x büyütme +
    # kontrast güçlendirme (CLAHE) uygulansın mı? (bkz. engines/ocr_engine.py)
    enhance_contrast: bool = True
    # Tesseract.exe'nin PATH'te olmadığı Windows kurulumları için elle yol
    # (boşsa dokunulmaz, pytesseract PATH'ten kendi bulmaya çalışır)
    tesseract_cmd: str = ""


@dataclass
class AnalyzerConfig:
    similarity_threshold: float = 0.90   # aynı cümle sayılması için benzerlik eşiği
    stable_frames: int = 2               # bir altyazının "kesin" sayılması için kaç kare üst üste görünmeli
    max_history: int = 30
    # v1.6: konuşmacı ismini "Isim: replik" biçiminde, satırın/paragrafın HER
    # ZAMAN başında olma zorunluluğu olmadan, metnin içinde nerede geçerse
    # geçsin yakalar (bkz. subtitle_analyzer.py - re.search, anchor yok).
    name_pattern: str = r"([A-ZÇĞİÖŞÜ][a-zçğıöşüÇĞİÖŞÜ]*)\s*:\s*(.+)"


@dataclass
class TranslationConfig:
    # v1.5: tek sağlayıcı yerine öncelik sırasına göre fallback zinciri.
    # Argos başarısız olursa (dil paketi kurulmamışsa vb.) DeepL'e, o da
    # başarısız olursa Google'a düşer.
    engine: list = field(default_factory=lambda: ["argos", "deepl", "google"])
    source_lang: str = "en"
    target_lang: str = "tr"
    # v1.6: oyun zaten Türkçe altyazılıysa çeviri adımı tamamen atlanır;
    # OCR'nin okuduğu metin doğrudan TTS'e gönderilir (bkz. main.py).
    direct_tts: bool = False


@dataclass
class SpeakerConfig:
    max_speakers: int = 4
    alternate_fallback: bool = True   # isim yoksa dönüşümlü konuşmacı varsayımı
    color_tolerance: float = 40.0     # v1.5: renk eşleştirmede izin verilen öklid mesafesi


@dataclass
class VoiceProfile:
    name: str
    pitch: float = 0.0     # -1.0 .. +1.0 arası göreli kaydırma
    speed: float = 1.0     # 0.9 .. 1.1 arası göreli hız


@dataclass
class VoiceConfig:
    # v1.7: "piper" (yerel, küçük ~60MB, ONNX tabanlı, internetsiz ve HIZLI
    # Türkçe TTS) artık İLK sırada. edge_tts (internet gerektirir, 100-500ms+
    # ağ gecikmesi ekler) ve pyttsx3 (OS sesi, Türkçe kalitesi genelde zayıf)
    # sadece piper hiç kurulamazsa (model indirilemedi vb.) devreye giren
    # yedek zincirdir. Bkz. plugins/tts/piper_plugin.py.
    engine: list = field(default_factory=lambda: ["piper", "edge_tts", "pyttsx3"])
    profiles: dict = field(default_factory=lambda: {
        "A": VoiceProfile("A", pitch=-1.0, speed=0.98),
        "B": VoiceProfile("B", pitch=1.0, speed=1.03),
        "NARRATOR": VoiceProfile("NARRATOR", pitch=0.0, speed=1.0),
    })


@dataclass
class AudioConfig:
    interrupt_on_new_line: bool = True
    queue_max_size: int = 20


@dataclass
class CacheConfig:
    enabled: bool = True
    dir: str = "cache"
    max_entries: int = 5000


@dataclass
class OverlayConfig:
    enabled: bool = True
    show_source: bool = False       # İngilizce de gösterilsin mi
    font_size: int = 22
    position: str = "bottom"        # "bottom" | "top"


@dataclass
class AppConfig:
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    analyzer: AnalyzerConfig = field(default_factory=AnalyzerConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    speaker: SpeakerConfig = field(default_factory=SpeakerConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)



# ---------------------------------------------------------------------------
# v1.6: Kontrol panelindeki "Ayarlar" sekmesi bu şemadan otomatik üretilir.
# Her giriş `section.field` şeklinde CONFIG içindeki gerçek dataclass alanına
# karşılık gelir; UI hiçbir alanı elle tekrar tanımlamak zorunda kalmaz, yeni
# bir ayar eklemek için sadece buraya bir satır eklemek yeterlidir.
# ---------------------------------------------------------------------------
SETTINGS_SCHEMA = [
    # --- Yakalama ---
    {"path": "capture.fps", "label": "Yakalama FPS", "type": "int", "min": 1, "max": 15,
     "group": "Yakalama"},
    {"path": "capture.skip_unchanged", "label": "Değişmeyen kareyi atla (hız)", "type": "bool",
     "group": "Yakalama"},
    {"path": "capture.change_threshold", "label": "Kare değişim hassasiyeti (düşük = daha hassas)",
     "type": "float", "min": 0.5, "max": 50.0, "group": "Yakalama"},
    {"path": "capture.diff_grid", "label": "Değişim algılama grid boyutu (NxN)", "type": "int",
     "min": 2, "max": 12, "group": "Yakalama"},

    # --- OCR / Dil ---
    {"path": "ocr.lang", "label": "Altyazı dili (ekranda okunan)", "type": "choice",
     "choices": ["en", "tr"], "group": "Dil ve OCR"},
    {"path": "ocr.engine", "label": "OCR motoru", "type": "choice",
     "choices": ["rapidocr", "tesseract"], "group": "Dil ve OCR"},
    {"path": "ocr.min_confidence", "label": "Min. OCR güven eşiği", "type": "float",
     "min": 0.0, "max": 1.0, "group": "Dil ve OCR"},
    {"path": "ocr.enhance_contrast", "label": "Küçük/soluk yazı için kontrast güçlendirme",
     "type": "bool", "group": "Dil ve OCR"},
    {"path": "ocr.tesseract_cmd", "label": "Tesseract.exe yolu (PATH'te değilse)",
     "type": "text", "group": "Dil ve OCR"},
    {"path": "translation.direct_tts", "label": "Oyun zaten Türkçe altyazılı (çeviriyi atla, doğrudan seslendir)",
     "type": "bool", "group": "Dil ve OCR"},

    # --- Konuşmacı / Ton ---
    {"path": "analyzer.name_pattern", "label": "İsim etiketi deseni (regex, 'İsim: replik')",
     "type": "text", "group": "Konuşmacı ve Ton"},
    {"path": "speaker.max_speakers", "label": "Maksimum farklı konuşmacı sesi", "type": "int",
     "min": 1, "max": 10, "group": "Konuşmacı ve Ton"},
    {"path": "speaker.alternate_fallback", "label": "İsim/renk yoksa dönüşümlü ses varsay",
     "type": "bool", "group": "Konuşmacı ve Ton"},
    {"path": "speaker.color_tolerance", "label": "Renk eşleştirme toleransı", "type": "float",
     "min": 0.0, "max": 200.0, "group": "Konuşmacı ve Ton"},

    # --- Ses / Overlay ---
    {"path": "audio.interrupt_on_new_line", "label": "Yeni replikte önceki sesi kes", "type": "bool",
     "group": "Ses ve Görünüm"},
    {"path": "overlay.enabled", "label": "Altyazı overlay'i göster", "type": "bool",
     "group": "Ses ve Görünüm"},
    {"path": "overlay.show_source", "label": "İngilizce orijinali de göster", "type": "bool",
     "group": "Ses ve Görünüm"},
    {"path": "overlay.font_size", "label": "Overlay yazı boyutu", "type": "int",
     "min": 10, "max": 48, "group": "Ses ve Görünüm"},
    {"path": "overlay.position", "label": "Overlay konumu", "type": "choice",
     "choices": ["bottom", "top"], "group": "Ses ve Görünüm"},

    # --- Önbellek ---
    {"path": "cache.enabled", "label": "Seslendirme önbelleği aktif", "type": "bool",
     "group": "Önbellek"},
    {"path": "cache.max_entries", "label": "Maksimum önbellek kaydı", "type": "int",
     "min": 100, "max": 100000, "group": "Önbellek"},
]


def get_path(cfg: AppConfig, path: str):
    """'capture.fps' gibi noktalı bir yolu takip edip değeri döner."""
    obj = cfg
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def set_path(cfg: AppConfig, path: str, value) -> None:
    """'capture.fps' gibi noktalı bir yola, şemadaki tipe göre dönüştürülmüş değeri yazar."""
    section_name, field_name = path.rsplit(".", 1)
    section = cfg
    for part in section_name.split("."):
        section = getattr(section, part)

    spec = next((s for s in SETTINGS_SCHEMA if s["path"] == path), None)
    kind = spec["type"] if spec else None
    if kind == "int":
        value = int(value)
    elif kind == "float":
        value = float(value)
    elif kind == "bool":
        value = bool(value)
    # "choice"/"text" -> zaten string, dönüşüm gerekmez

    setattr(section, field_name, value)


def _apply_saved_overrides(cfg: AppConfig) -> AppConfig:
    """
    Kullanıcının kontrol panelindeki "Ayarlar" sekmesi veya bölge seçme
    aracıyla daha önce kaydettiği ayarları (varsa) varsayılanların üzerine
    uygular. Dosya yoksa, okunamazsa ya da tek tek bir alan artık geçerli
    değilse (ör. eski bir sürümden kalan alan) sessizce atlanır - bu,
    tek bir bozuk kayıt yüzünden tüm uygulamanın varsayılanlara bile
    dönemeyip açılmamasındansa çok daha güvenlidir.
    """
    try:
        from utils.settings_store import load_region, load_settings

        saved_region = load_region()
        if saved_region is not None:
            cfg.capture.region = saved_region
            cfg.capture.mode = "region"

        saved = load_settings().get("schema_settings", {})
        for path, value in saved.items():
            try:
                set_path(cfg, path, value)
            except Exception:
                # Tek bir ayarın uygulanamaması diğerlerini/uygulamayı etkilemesin.
                continue
    except Exception:
        # Ayar yükleme başarısız olsa bile uygulama varsayılanlarla açılabilmeli.
        pass
    return cfg


CONFIG = _apply_saved_overrides(AppConfig())
