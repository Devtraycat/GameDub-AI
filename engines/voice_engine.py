"""
Voice Engine
------------
TTS'i yönetir. Tek bir ses yerine pitch/speed varyasyonuyla birden
fazla "karakter" hissi verir. Gerçek sentezi plugins/tts/ eklentisine
devreder.

v1.5 değişiklikleri:
- Çoklu TTS motoru desteği: `config.engine` artık tek bir string değil,
  öncelik sırasına göre denenecek bir liste de olabilir (örn.
  ["edge_tts", "pyttsx3"]). İlk motor internet yokluğu/hata gibi bir
  sebeple başarısız olursa otomatik olarak bir sonrakine düşülür.
- Böylece internet kesildiğinde uygulama sessizce çökmek yerine offline
  motora geçip çalışmaya devam eder.
"""

import importlib
import sys
import traceback


class VoiceEngine:
    def __init__(self, config):
        self.config = config
        engine_names = config.engine if isinstance(config.engine, list) else [config.engine]
        self._engine_names = engine_names
        self._backends: dict[str, object] = {}
        self._last_working_engine: str | None = None

        # İlk motoru hemen yükle; diğerleri ilk gerçek ihtiyaçta (lazy) yüklenir
        self._load_backend(engine_names[0])

    def _load_backend(self, name: str):
        if name in self._backends:
            return self._backends[name]
        module = importlib.import_module(f"plugins.tts.{name}_plugin")
        backend = module.TTSPlugin()
        self._backends[name] = backend
        return backend

    def preload(self) -> None:
        """
        v1.7: Uygulama açılışında (ilk gerçek replikten ÖNCE), arka planda
        bir thread'den çağrılır. Yalnızca `preload()` metodunu destekleyen
        motorlar için anlamlıdır (ör. piper - model dosyalarını indirip
        belleğe yükler, ilk gerçek repliğe binen maliyeti önceden karşılar).
        Desteklemeyen motorlar (edge_tts, pyttsx3) için no-op'tur.
        """
        for name in self._engine_names:
            try:
                backend = self._load_backend(name)
            except Exception:
                continue
            preload_fn = getattr(backend, "preload", None)
            if callable(preload_fn):
                try:
                    preload_fn()
                except Exception:
                    print(f"[VoiceEngine] '{name}' ön yükleme başarısız (ilk replikte tekrar denenecek).",
                          file=sys.stderr)

    def synthesize(self, text: str, voice_id: str) -> bytes:
        """
        text: Türkçe metin
        voice_id: "A", "B", "NARRATOR" gibi profil anahtarı
        Döner: wav bytes

        Öncelik sırasındaki motorları sırayla dener; biri hata verirse
        (örn. internet yok) bir sonrakine geçer. Hepsi başarısız olursa
        son hatayı fırlatır.
        """
        profile = self.config.profiles.get(voice_id, self.config.profiles["NARRATOR"])
        last_error: Exception | None = None

        # Daha önce çalıştığı bilinen motoru öncelikli dene (gereksiz tekrar denemeyi azaltır)
        ordered = self._engine_names
        if self._last_working_engine and self._last_working_engine in ordered:
            ordered = [self._last_working_engine] + [
                e for e in ordered if e != self._last_working_engine
            ]

        for name in ordered:
            try:
                backend = self._load_backend(name)
                wav_bytes = backend.synthesize(
                    text, pitch=profile.pitch, speed=profile.speed, voice_id=voice_id
                )
                self._last_working_engine = name
                return wav_bytes
            except Exception:
                last_error = sys.exc_info()[1]
                print(f"[VoiceEngine] '{name}' motoru başarısız oldu, sıradakine geçiliyor:",
                      file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                continue

        raise RuntimeError(
            f"Tüm TTS motorları başarısız oldu ({ordered}). Son hata: {last_error}"
        )
