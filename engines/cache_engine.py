"""
Cache Engine
------------
"Hello." 100 kere geldiyse 100 kere TTS yapılmasın.
normalized_text + voice_id -> wav dosyası eşlemesi tutar.
"""

import os
import hashlib
import json


class CacheEngine:
    def __init__(self, config):
        self.config = config
        os.makedirs(config.dir, exist_ok=True)
        self._index_path = os.path.join(config.dir, "index.json")
        self._index: dict[str, str] = {}
        if os.path.exists(self._index_path):
            with open(self._index_path, "r", encoding="utf-8") as f:
                self._index = json.load(f)

    def _key(self, normalized_text: str, voice_id: str) -> str:
        raw = f"{normalized_text}|{voice_id}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def get(self, normalized_text: str, voice_id: str) -> bytes | None:
        if not self.config.enabled:
            return None
        key = self._key(normalized_text, voice_id)
        rel_path = self._index.get(key)
        if not rel_path:
            return None
        full_path = os.path.join(self.config.dir, rel_path)
        if not os.path.exists(full_path):
            return None
        with open(full_path, "rb") as f:
            return f.read()

    def put(self, normalized_text: str, voice_id: str, wav_bytes: bytes) -> None:
        if not self.config.enabled:
            return
        key = self._key(normalized_text, voice_id)
        rel_path = f"{key}.wav"
        full_path = os.path.join(self.config.dir, rel_path)
        with open(full_path, "wb") as f:
            f.write(wav_bytes)

        if len(self._index) >= self.config.max_entries:
            # basit LRU değil ama sınırı aşınca en eskiyi at
            oldest_key = next(iter(self._index))
            old_file = os.path.join(self.config.dir, self._index.pop(oldest_key))
            if os.path.exists(old_file):
                os.remove(old_file)

        self._index[key] = rel_path
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False)
