"""
Overlay Engine
--------------
İsteğe bağlı: ekranın üstüne şeffaf, tıklanamaz bir altyazı katmanı çizer.
Tkinter ile basit bir "always-on-top" pencere kullanır.
"""

import tkinter as tk


class OverlayEngine:
    def __init__(self, config):
        self.config = config
        self._root = None
        self._label = None
        if config.enabled:
            self._build_window()

    def _build_window(self) -> None:
        self._root = tk.Tk()
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

    def show(self, translated_text: str, source_text: str | None = None) -> None:
        if not self.config.enabled or self._label is None:
            return
        text = translated_text
        if self.config.show_source and source_text:
            text = f"{source_text}\n{translated_text}"
        self._label.config(text=text)
        self._root.update_idletasks()
        self._root.update()

    def clear(self) -> None:
        self.show("")

    def run_forever(self) -> None:
        if self._root:
            self._root.mainloop()
