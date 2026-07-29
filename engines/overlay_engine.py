"""
Overlay Engine
--------------
İsteğe bağlı: ekranın üstüne şeffaf, tıklanamaz bir altyazı katmanı çizer.
Tkinter ile basit bir "always-on-top" pencere kullanır.

Önemli - thread güvenliği:
Tkinter widget'larına yalnızca pencerenin mainloop'unu çalıştıran
thread'den dokunulabilir. Eskiden `show()` worker (OCR/pipeline)
thread'inden çağrılıp doğrudan `self._label.config(...)` yapıyordu;
bu donma/çökme riski taşıyordu. Artık `show()` sadece thread-safe bir
`queue.Queue`'ya veri koyar; asıl widget güncellemesi ana thread'de
`after()` ile periyodik çalışan `_poll()` içinde yapılır.
"""

from __future__ import annotations

import logging
import queue
import tkinter as tk

log = logging.getLogger(__name__)

_POLL_MS = 40  # bekleyen altyazı güncellemesi için yoklama aralığı


class OverlayEngine:
    def __init__(self, config):
        self.config = config
        self._root = None
        self._label = None
        self._owns_root = False
        self._pending: "queue.Queue[tuple[str, str | None]]" = queue.Queue(maxsize=1)
        self._built = False

    def attach(self, master: tk.Misc | None = None) -> None:
        """
        Overlay penceresini oluşturur.
        `master` verilirse (kontrol paneli gibi) bir `Toplevel` olarak,
        verilmezse bağımsız bir `Tk()` kökü olarak açılır.
        Config'te overlay kapalıysa hiçbir şey yapmaz.
        """
        if self._built or not self.config.enabled:
            return
        self._build_window(master)
        self._built = True
        self._schedule_poll()

    def _build_window(self, master: tk.Misc | None) -> None:
        if master is not None:
            self._root = tk.Toplevel(master)
            self._owns_root = False
        else:
            self._root = tk.Tk()
            self._owns_root = True

        self._root.overrideredirect(True)       # kenarlıksız
        self._root.attributes("-topmost", True)  # her zaman üstte
        self._root.attributes("-alpha", 0.85)
        self._root.configure(bg="black")

        screen_w = self._root.winfo_screenwidth()
        y = 40 if self.config.position == "top" else self._root.winfo_screenheight() - 120
        self._root.geometry(f"{screen_w - 200}x80+100+{y}")

        self._label = tk.Label(
            self._root,
            text="",
            fg="white",
            bg="black",
            font=("Segoe UI", self.config.font_size),
            wraplength=screen_w - 240,
            justify="center",
        )
        self._label.pack(expand=True, fill="both")
        log.info("Overlay penceresi oluşturuldu (position=%s).", self.config.position)

    def show(self, translated_text: str, source_text: str | None = None) -> None:
        """
        Herhangi bir thread'den güvenle çağrılabilir. Widget'a doğrudan
        dokunmaz; sadece en güncel metni kuyruğa koyar.
        """
        if not self.config.enabled or not self._built:
            return
        # Kuyruk kapasitesi 1: eski (henüz işlenmemiş) güncellemeyi at,
        # her zaman en son altyazı gösterilsin.
        try:
            self._pending.get_nowait()
        except queue.Empty:
            pass
        try:
            self._pending.put_nowait((translated_text, source_text))
        except queue.Full:
            pass

    def _schedule_poll(self) -> None:
        self._root.after(_POLL_MS, self._poll)

    def _poll(self) -> None:
        try:
            translated_text, source_text = self._pending.get_nowait()
        except queue.Empty:
            pass
        else:
            text = translated_text
            if self.config.show_source and source_text:
                text = f"{source_text}\n{translated_text}"
            self._label.config(text=text)
        self._schedule_poll()

    def clear(self) -> None:
        self.show("")

    def run_forever(self) -> None:
        """Sadece bağımsız (master'sız) kullanımda ana thread'i devralır."""
        if self._root and self._owns_root:
            self._root.mainloop()
