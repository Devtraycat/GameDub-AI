"""
Settings Store
--------------
`config.py` uygulamanın *varsayılan* ayarlarını tutar (kod içinde).
Ama kullanıcı bölge seçme aracıyla kendi ekranına uygun bir bölge
seçtiğinde, bunun bir sonraki çalıştırmada da hatırlanması gerekir.

Bu modül basit bir JSON dosyası (runtime_settings.json) üzerinden bunu
sağlar. Sadece kullanıcının GUI üzerinden değiştirebileceği küçük bir
ayar seti burada tutulur; mimari ayarlar (fps, motor sırası vb.) hâlâ
config.py'de kalır.
"""

from __future__ import annotations

import json
import logging
import os
import threading

log = logging.getLogger(__name__)

_SETTINGS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SETTINGS_PATH = os.path.join(_SETTINGS_DIR, "runtime_settings.json")

_lock = threading.Lock()


def load_settings() -> dict:
    with _lock:
        if not os.path.exists(_SETTINGS_PATH):
            return {}
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("runtime_settings.json okunamadı, varsayılanlar kullanılacak: %s", e)
            return {}


def save_settings(update: dict) -> None:
    with _lock:
        current = {}
        if os.path.exists(_SETTINGS_PATH):
            try:
                with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    current = json.load(f)
            except (json.JSONDecodeError, OSError):
                current = {}
        current.update(update)
        try:
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.warning("runtime_settings.json yazılamadı: %s", e)


def save_region(region: tuple) -> None:
    save_settings({"capture_region": list(region)})


def load_region() -> tuple | None:
    data = load_settings()
    region = data.get("capture_region")
    if region and len(region) == 4:
        return tuple(int(v) for v in region)
    return None


def save_schema_setting(path: str, value) -> None:
    """
    Kontrol panelindeki "Ayarlar" sekmesinden tek bir alanı (ör.
    "capture.fps") kalıcı olarak kaydeder. Bir sonraki açılışta
    config.py:_apply_saved_overrides bunu okuyup uygular.
    """
    with _lock:
        current = {}
        if os.path.exists(_SETTINGS_PATH):
            try:
                with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    current = json.load(f)
            except (json.JSONDecodeError, OSError):
                current = {}
        schema_settings = current.get("schema_settings", {})
        schema_settings[path] = value
        current["schema_settings"] = schema_settings
        try:
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.warning("runtime_settings.json yazılamadı: %s", e)


def load_schema_settings() -> dict:
    return load_settings().get("schema_settings", {})
