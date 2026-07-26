"""
Voice Engine
------------
TTS'i yönetir. Tek bir ses yerine pitch/speed varyasyonuyla birden
fazla "karakter" hissi verir. Gerçek sentezi plugins/tts/ eklentisine
devreder.
"""

import importlib


class VoiceEngine:
    def __init__(self, config):
        self.config = config
        module = importlib.import_module(f"plugins.tts.{config.engine}_plugin")
        self._backend = module.TTSPlugin()

    def synthesize(self, text: str, voice_id: str) -> bytes:
        """
        text: Türkçe metin
        voice_id: "A", "B", "NARRATOR" gibi profil anahtarı
        Döner: wav bytes
        """
        profile = self.config.profiles.get(voice_id, self.config.profiles["NARRATOR"])
        return self._backend.synthesize(
            text, pitch=profile.pitch, speed=profile.speed, voice_id=voice_id
        )
