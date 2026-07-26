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


@dataclass
class OCRConfig:
    engine: str = "rapidocr"       # plugins/ocr/ içindeki dosya adına karşılık gelir
    lang: str = "en"
    min_confidence: float = 0.55


@dataclass
class AnalyzerConfig:
    similarity_threshold: float = 0.90   # aynı cümle sayılması için benzerlik eşiği
    stable_frames: int = 2               # bir altyazının "kesin" sayılması için kaç kare üst üste görünmeli
    max_history: int = 30


@dataclass
class TranslationConfig:
    # v1.5: tek sağlayıcı yerine öncelik sırasına göre fallback zinciri.
    # Argos başarısız olursa (dil paketi kurulmamışsa vb.) DeepL'e, o da
    # başarısız olursa Google'a düşer.
    engine: list = field(default_factory=lambda: ["argos", "deepl", "google"])
    source_lang: str = "en"
    target_lang: str = "tr"


@dataclass
class SpeakerConfig:
    max_speakers: int = 4
    name_pattern: str = r"^([A-ZÇĞİÖŞÜ][a-zçğıöşü]+):\s*(.*)$"
    alternate_fallback: bool = True   # isim yoksa dönüşümlü konuşmacı varsayımı
    color_tolerance: float = 40.0     # v1.5: renk eşleştirmede izin verilen öklid mesafesi


@dataclass
class VoiceProfile:
    name: str
    pitch: float = 0.0     # -1.0 .. +1.0 arası göreli kaydırma
    speed: float = 1.0     # 0.9 .. 1.1 arası göreli hız


@dataclass
class VoiceConfig:
    # v1.5: tek motor yerine öncelik sırasına göre fallback zinciri.
    # edge_tts başarısız olursa (ör. internet yoksa) otomatik pyttsx3'e düşer.
    engine: list = field(default_factory=lambda: ["edge_tts", "pyttsx3"])
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


CONFIG = AppConfig()
