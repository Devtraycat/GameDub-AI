"""
DeepL Translate eklentisi.
En yüksek çeviri kalitesini sunan sağlayıcılardan biri, ama API anahtarı
ve internet gerektirir. Ücretsiz plan aylık karakter limitine sahiptir.

pip install deepl

Kullanım: ortam değişkeni olarak DEEPL_API_KEY tanımlayın:
    export DEEPL_API_KEY="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx"
"""

import os


class TranslatorPlugin:
    def __init__(self, source_lang: str = "en", target_lang: str = "tr"):
        try:
            import deepl
        except ImportError as e:
            raise RuntimeError("deepl kurulu değil. `pip install deepl`") from e

        api_key = os.environ.get("DEEPL_API_KEY")
        if not api_key:
            raise RuntimeError(
                "DEEPL_API_KEY ortam değişkeni tanımlı değil. "
                "DeepL hesabınızdan aldığınız anahtarı ayarlayın."
            )

        self._client = deepl.Translator(api_key)
        self.source_lang = source_lang.upper()
        self.target_lang = target_lang.upper()

    def translate(self, text: str) -> str:
        result = self._client.translate_text(
            text, source_lang=self.source_lang, target_lang=self.target_lang
        )
        return result.text
