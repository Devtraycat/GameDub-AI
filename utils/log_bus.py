"""
Log Bus
-------
Merkezi logging kurulumu.

Neden gerekli?
Eskiden uygulama hiçbir yere log basmıyordu; pipeline çalışsa da
çalışmasa da konsolda sessizlik oluyordu. Bu modül üç şeyi birden
sağlar:
1) Konsola (stdout) okunaklı log çıktısı
2) logs/gamedub.log dosyasına kalıcı log
3) Kontrol panelindeki log ekranına canlı log akışı

GUI'ye log basmak thread-safe DEĞİLDİR (Tkinter ana thread dışından
dokunulamaz). Bu yüzden `QueueLogHandler` logları doğrudan widget'a
yazmaz; thread-safe bir `queue.Queue`'ya koyar. Kontrol paneli bu
kuyruğu ana thread'den `after()` ile periyodik olarak boşaltıp
widget'a yazar.
"""

from __future__ import annotations

import logging
import os
import queue
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "gamedub.log")

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


class QueueLogHandler(logging.Handler):
    """Log kayıtlarını GUI'nin okuyabileceği thread-safe bir kuyruğa yazar."""

    def __init__(self, maxsize: int = 2000):
        super().__init__()
        self.queue: "queue.Queue[str]" = queue.Queue(maxsize=maxsize)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        try:
            self.queue.put_nowait(msg)
        except queue.Full:
            # Kuyruk taştıysa en eski kaydı at, yenisini ekle (GUI geride kalmasın)
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.queue.put_nowait(msg)
            except queue.Full:
                pass


_queue_handler: QueueLogHandler | None = None
_configured = False


def configure_logging(level: int = logging.INFO) -> QueueLogHandler:
    """
    Root logger'ı bir kere kurar (konsol + dosya + GUI kuyruğu).
    Tekrar çağrılırsa aynı handler'ı döner (idempotent).
    """
    global _queue_handler, _configured

    if _configured and _queue_handler is not None:
        return _queue_handler

    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # Dosyaya yazamıyorsak (izin, salt-okunur dizin vb.) sessizce geç,
        # en azından konsol + GUI logu çalışmaya devam etsin.
        pass

    _queue_handler = QueueLogHandler()
    _queue_handler.setFormatter(formatter)
    root.addHandler(_queue_handler)

    _configured = True
    root.info("Logging kuruldu (konsol + dosya: %s + GUI).", LOG_FILE)
    return _queue_handler


def get_queue_handler() -> QueueLogHandler | None:
    return _queue_handler
