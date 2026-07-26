"""
Argos Translate eklentisi.
Tamamen offline çalışan açık kaynak çeviri motoru.
pip install argostranslate

İlk çalıştırmada gerekli dil paketini indirir (internet gerektirir, bir kerelik).
"""


class TranslatorPlugin:
    def __init__(self, source_lang: str = "en", target_lang: str = "tr"):
        try:
            import argostranslate.package
            import argostranslate.translate
        except ImportError as e:
            raise RuntimeError(
                "argostranslate kurulu değil. `pip install argostranslate`"
            ) from e

        self._argostranslate = argostranslate.translate
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._ensure_language_pair(argostranslate.package)

    def _ensure_language_pair(self, package_module) -> None:
        installed = self._argostranslate.get_installed_languages()
        from_lang = next((l for l in installed if l.code == self.source_lang), None)
        to_lang = next((l for l in installed if l.code == self.target_lang), None)
        if from_lang and to_lang:
            self._translation = from_lang.get_translation(to_lang)
            return

        # Dil paketi kurulu değilse indirip kur (tek seferlik, internet gerekir)
        package_module.update_package_index()
        available = package_module.get_available_packages()
        pkg = next(
            (p for p in available
             if p.from_code == self.source_lang and p.to_code == self.target_lang),
            None,
        )
        if pkg is None:
            raise RuntimeError(
                f"{self.source_lang}->{self.target_lang} için Argos dil paketi bulunamadı."
            )
        package_module.install_from_path(pkg.download())

        installed = self._argostranslate.get_installed_languages()
        from_lang = next(l for l in installed if l.code == self.source_lang)
        to_lang = next(l for l in installed if l.code == self.target_lang)
        self._translation = from_lang.get_translation(to_lang)

    def translate(self, text: str) -> str:
        return self._translation.translate(text)
