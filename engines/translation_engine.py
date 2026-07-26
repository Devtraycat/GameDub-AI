"""
Translation Engine
-------------------
Tek görevi: translate(text) -> text
Gerçek çeviri işini plugins/translator/ altındaki eklentiye devreder.
"""

import importlib


class TranslationEngine:
    def __init__(self, config):
        self.config = config
        module = importlib.import_module(f"plugins.translator.{config.engine}_plugin")
        self._backend = module.TranslatorPlugin(
            source_lang=config.source_lang, target_lang=config.target_lang
        )

    def translate(self, text: str) -> str:
        if not text:
            return ""
        return self._backend.translate(text)
