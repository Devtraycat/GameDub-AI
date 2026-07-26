"""
edge-tts eklentisi.
Microsoft Edge'in bulut TTS motorunu kullanır (ücretsiz, ama internet gerektirir).
Türkçe için pyttsx3'ten belirgin şekilde daha doğal seslere sahiptir.
pip install edge-tts

Pitch/speed, SSML "rate" ve "pitch" parametrelerine çevrilir.
"""

import asyncio
import io

# Konuşmacı profillerini gerçek Edge seslerine eşliyoruz
VOICE_MAP = {
    "A": "tr-TR-AhmetNeural",
    "B": "tr-TR-EmelNeural",
    "NARRATOR": "tr-TR-AhmetNeural",
}


def _to_rate_str(speed: float) -> str:
    pct = int(round((speed - 1.0) * 100))
    return f"{pct:+d}%"


def _to_pitch_str(pitch: float) -> str:
    hz = int(round(pitch * 20))
    return f"{hz:+d}Hz"


class TTSPlugin:
    def __init__(self):
        try:
            import edge_tts  # noqa: F401
        except ImportError as e:
            raise RuntimeError("edge-tts kurulu değil. `pip install edge-tts`") from e

    def synthesize(self, text: str, pitch: float = 0.0, speed: float = 1.0,
                    voice_id: str = "NARRATOR") -> bytes:
        import edge_tts

        voice = VOICE_MAP.get(voice_id, VOICE_MAP["NARRATOR"])
        rate = _to_rate_str(speed)
        pitch_str = _to_pitch_str(pitch)

        async def _run() -> bytes:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch_str)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue()

        return asyncio.run(_run())
