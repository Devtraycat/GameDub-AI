"""
Google Translate fallback eklentisi (deep-translator üzerinden, ücretsiz uç nokta).
İnternet gerektirir. Argos kurulamayan/istenmeyen durumlarda kullanılabilir.
pip install deep-translator
"""


class TranslatorPlugin:
    def __init__(self, source_lang: str = "en", target_lang: str = "tr"):
        try:
            from deep_translator import GoogleTranslator
        except ImportError as e:
            raise RuntimeError(
                "deep-translator kurulu değil. `pip install deep-translator`"
            ) from e
        self._translator = GoogleTranslator(source=source_lang, target=target_lang)

    def translate(self, text: str) -> str:
        return self._translator.translate(text)
