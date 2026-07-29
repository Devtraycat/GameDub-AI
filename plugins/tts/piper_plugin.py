"""
Piper TTS eklentisi - yerel, küçük, HIZLI Türkçe seslendirme.
=============================================================

Neden Piper?
- Tamamen yerel/offline çalışır: internet gecikmesi yok (edge_tts'in aksine).
- Çok küçük ONNX modeli (~60MB, ~15M parametre) - proje zaten OCR için
  onnxruntime kullandığından ek bir ağır bağımlılık (ör. PyTorch) gerekmez.
- CPU'da gerçek zamanlıdan çok daha hızlı sentez yapar; bu da "algılandıktan
  sonra sese dönene kadar geçen süre"yi ve TTS'in diyalog hızına
  yetişememesini doğrudan iyileştirir.
- pip install piper-tts

Türkçe ses seçenekleri (hepsi "medium" kalite, şu an tek kalite seviyesi
mevcut - x_low/low Türkçe modeli henüz yok, yani "medium" zaten en küçük
seçenektir):
  - fahrettin (erkek)
  - fettah    (erkek)
  - dfki      (kadın)

v1.7: Pitch kaydırma yerine (Piper VITS tabanlı olduğu için pitch
parametresi desteklemez) farklı konuşmacı profillerine FARKLI ses modelleri
atanıyor - bu, ton çeşitliliğini yapay bir pitch efektinden çok daha doğal
şekilde sağlıyor.
"""

from __future__ import annotations

import io
import logging
import os
import urllib.request
import wave

log = logging.getLogger(__name__)

# Proje kökü altında sabit bir model klasörü - kullanıcının çalıştığı dizine
# göre değişmez, bu yüzden nereden başlatılırsa başlatılsın aynı yeri bulur.
_MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "piper",
)

_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/refs%2Fpr%2F25/tr/tr_TR"

# ses adı -> huggingface'teki göreli yol (uzantısız)
_VOICE_FILES = {
    "fahrettin": "fahrettin/medium/tr_TR-fahrettin-medium",
    "fettah": "fettah/medium/tr_TR-fettah-medium",
    "dfki": "dfki/medium/tr_TR-dfki-medium",
}

# Konuşmacı profili -> hangi yerel Piper sesi kullanılsın.
# Şemadaki "A"/"B"/"NARRATOR" için sabit bir eşleme; tanımlı olmayan bir
# voice_id gelirse (ör. "C", "D") aşağıdaki _FALLBACK_ORDER'dan sırayla atanır.
VOICE_MAP = {
    "A": "fahrettin",
    "B": "dfki",
    "NARRATOR": "fettah",
}
_FALLBACK_ORDER = ["fahrettin", "dfki", "fettah"]


def _ensure_model(name: str) -> tuple[str, str]:
    """
    Model dosyaları yerelde yoksa Hugging Face'ten bir kereliğine indirir.
    Sonraki her çalıştırmada zaten diskte olduğu için indirme yapılmaz -
    bu, ilk açılıştan sonraki tüm oturumlarda tamamen offline çalışmayı
    sağlar.
    """
    rel = _VOICE_FILES[name]
    onnx_path = os.path.join(_MODELS_DIR, f"{name}.onnx")
    json_path = os.path.join(_MODELS_DIR, f"{name}.onnx.json")
    os.makedirs(_MODELS_DIR, exist_ok=True)

    if not os.path.exists(onnx_path):
        log.info("Piper modeli indiriliyor (~60MB, sadece ilk seferde): %s", name)
        urllib.request.urlretrieve(f"{_HF_BASE}/{rel}.onnx", onnx_path)
    if not os.path.exists(json_path):
        urllib.request.urlretrieve(f"{_HF_BASE}/{rel}.onnx.json", json_path)

    return onnx_path, json_path


class TTSPlugin:
    def __init__(self):
        try:
            from piper import PiperVoice
        except ImportError as e:
            raise RuntimeError(
                "piper-tts kurulu değil. `pip install piper-tts`"
            ) from e
        self._PiperVoice = PiperVoice
        # Modeller ilk ihtiyaç duyulduğunda yüklenir ve önbelleğe alınır -
        # her sentez çağrısında yeniden yüklemek (saniyeler sürer) yerine
        # bir kere yükleyip bellekte tutmak, tekrarlanan repliklerde ve
        # aynı konuşmacının ardışık replikerinde büyük hız kazandırır.
        self._voices: dict[str, object] = {}

    def _resolve_voice_name(self, voice_id: str) -> str:
        name = VOICE_MAP.get(voice_id)
        if name is not None:
            return name
        idx = abs(hash(voice_id)) % len(_FALLBACK_ORDER)
        return _FALLBACK_ORDER[idx]

    def _load_voice(self, name: str):
        if name in self._voices:
            return self._voices[name]
        onnx_path, json_path = _ensure_model(name)
        voice = self._PiperVoice.load(onnx_path, config_path=json_path, use_cuda=False)
        self._voices[name] = voice
        log.info("Piper sesi belleğe yüklendi: %s", name)
        return voice

    def preload(self, voice_ids: list[str] | None = None) -> None:
        """
        v1.7: Uygulama başlarken (ilk gerçek altyazıdan ÖNCE) çağrılır -
        model indirme/yükleme maliyeti oyun oturumu başlamadan önce
        karşılanır. Aksi halde bu maliyet ilk repliğe biner ve "ilk
        replik neden bu kadar geç geldi / kayboldu" hissine yol açar.
        """
        names = {self._resolve_voice_name(v) for v in (voice_ids or list(VOICE_MAP))}
        for name in names:
            try:
                self._load_voice(name)
            except Exception:
                log.exception("Piper sesi önceden yüklenemedi: %s", name)

    def synthesize(self, text: str, pitch: float = 0.0, speed: float = 1.0,
                    voice_id: str = "NARRATOR") -> bytes:
        name = self._resolve_voice_name(voice_id)
        voice = self._load_voice(name)

        # Piper'da length_scale hızla TERS orantılıdır: küçük değer = hızlı.
        speed = max(0.1, speed)
        length_scale = 1.0 / speed

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            try:
                voice.synthesize(text, wav_file, length_scale=length_scale)
            except TypeError:
                # Piper'ın bazı sürümlerinde parametre imzası farklı olabilir
                # (ör. bir SynthesisConfig nesnesi beklenebilir). Böyle bir
                # durumda en azından temel sentezin çalışmasını garanti et;
                # hız ayarı bu yolda uygulanmamış olur ama sessiz kalmaktan
                # iyidir.
                try:
                    from piper.voice import SynthesisConfig  # bazı sürümlerde mevcut
                    voice.synthesize(text, wav_file, syn_config=SynthesisConfig(length_scale=length_scale))
                except Exception:
                    voice.synthesize(text, wav_file)

        return buf.getvalue()
