"""
Translation Engine
-------------------
Tek görevi: translate(text) -> text
Gerçek çeviri işini plugins/translator/ altındaki eklentiye devreder.

v1.5 değişiklikleri:
- Çoklu çeviri sağlayıcısı desteği: `config.engine` bir liste olabilir
  (örn. ["argos", "deepl", "google"]). İlk sağlayıcı başarısız olursa
  (paket kurulu değil, API anahtarı yok, internet yok vb.) otomatik
  olarak bir sonrakine geçilir.
"""

import importlib
import sys
import traceback


class TranslationEngine:
    def __init__(self, config):
        self.config = config
        engine_names = config.engine if isinstance(config.engine, list) else [config.engine]
        self._engine_names = engine_names
        self._backends: dict[str, object] = {}
        self._last_working_engine: str | None = None

        # İlk sağlayıcıyı hemen yükle; diğerleri ilk gerçek ihtiyaçta yüklenir
        self._load_backend(engine_names[0])

    def _load_backend(self, name: str):
        if name in self._backends:
            return self._backends[name]
        module = importlib.import_module(f"plugins.translator.{name}_plugin")
        backend = module.TranslatorPlugin(
            source_lang=self.config.source_lang, target_lang=self.config.target_lang
        )
        self._backends[name] = backend
        return backend

    def translate(self, text: str) -> str:
        if not text:
            return ""

        last_error: Exception | None = None
        ordered = self._engine_names
        if self._last_working_engine and self._last_working_engine in ordered:
            ordered = [self._last_working_engine] + [
                e for e in ordered if e != self._last_working_engine
            ]

        for name in ordered:
            try:
                backend = self._load_backend(name)
                result = backend.translate(text)
                self._last_working_engine = name
                return result
            except Exception:
                last_error = sys.exc_info()[1]
                print(f"[TranslationEngine] '{name}' sağlayıcısı başarısız oldu, "
                      f"sıradakine geçiliyor:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                continue

        raise RuntimeError(
            f"Tüm çeviri sağlayıcıları başarısız oldu ({ordered}). Son hata: {last_error}"
        )
