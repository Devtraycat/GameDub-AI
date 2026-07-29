"""
Bölge Seçme Aracı (Region Selector)
------------------------------------
Kullanıcının fare ile ekranda bir dikdörtgen çizerek altyazı yakalama
bölgesini seçmesini sağlayan küçük, bağımsız da çalışabilen bir araç.

Neden gerekliydi?
`config.py`'deki varsayılan bölge (100,800 - 1800,1000) rastgele bir
örnekti. Kullanıcının kendi ekran çözünürlüğüne uymuyorsa yakalama
boş bir alanı okur, OCR hiçbir şey bulamaz ve hiçbir hata da vermez -
"sessizce hiçbir şey olmuyor" hissi verir. Bu araç, doğru bölgeyi
görsel olarak seçip anında (ve kalıcı olarak) ayarlamayı sağlar.

Kullanım:
- Kontrol panelinden "Bölge Seç" butonuyla (uygulama içinden), veya
- `python -m tools.region_selector` ile bağımsız olarak.

Çoklu monitör: mss kuruluysa tüm sanal masaüstünü (tüm monitörler)
kaplayan bir seçim penceresi açılır; mss yoksa birincil ekranla
sınırlı kalınır.
"""

from __future__ import annotations

import logging
import tkinter as tk

log = logging.getLogger(__name__)

try:
    import mss
except ImportError:
    mss = None


def _virtual_desktop_bbox(fallback_root: tk.Misc) -> tuple[int, int, int, int]:
    """(left, top, width, height) - tüm monitörleri kapsayan sanal masaüstü."""
    if mss is not None:
        try:
            with mss.mss() as sct:
                m = sct.monitors[0]  # index 0 = tüm monitörlerin birleşimi
                return m["left"], m["top"], m["width"], m["height"]
        except Exception:
            log.warning("mss ile sanal masaüstü boyutu alınamadı, tekil ekrana düşülüyor.", exc_info=True)
    return 0, 0, fallback_root.winfo_screenwidth(), fallback_root.winfo_screenheight()


class _RegionSelectorWindow:
    """Sürükle-bırak ile dikdörtgen seçimi yapan tam ekran yarı saydam pencere."""

    def __init__(self, master: tk.Misc):
        self.result: tuple[int, int, int, int] | None = None

        left, top, width, height = _virtual_desktop_bbox(master)

        self.top = tk.Toplevel(master)
        self.top.geometry(f"{width}x{height}+{left}+{top}")
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.attributes("-alpha", 0.30)
        self.top.configure(bg="gray12")
        self.top.config(cursor="cross")

        self._origin_x = left
        self._origin_y = top

        self.canvas = tk.Canvas(self.top, bg="gray12", highlightthickness=0, cursor="cross")
        self.canvas.pack(fill="both", expand=True)

        self.hint_id = self.canvas.create_text(
            width // 2, 30,
            text="Altyazı alanının etrafına bir dikdörtgen çizin (bırakınca onaylanır)  •  İptal: Esc",
            fill="white", font=("Segoe UI", 14),
        )

        self._start = None
        self._rect_id = None
        self._size_label_id = None

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.top.bind("<Escape>", self._on_cancel)

        self.top.focus_force()
        self.canvas.focus_set()

    def _on_press(self, event) -> None:
        self._start = (event.x, event.y)
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
        self._rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#00ff88", width=2,
        )

    def _on_drag(self, event) -> None:
        if self._start is None or self._rect_id is None:
            return
        x0, y0 = self._start
        self.canvas.coords(self._rect_id, x0, y0, event.x, event.y)

        w, h = abs(event.x - x0), abs(event.y - y0)
        label_text = f"{w} x {h}"
        if self._size_label_id is None:
            self._size_label_id = self.canvas.create_text(
                event.x + 12, event.y + 12, text=label_text,
                fill="#00ff88", font=("Segoe UI", 11), anchor="nw",
            )
        else:
            self.canvas.coords(self._size_label_id, event.x + 12, event.y + 12)
            self.canvas.itemconfigure(self._size_label_id, text=label_text)

    def _on_release(self, event) -> None:
        if self._start is None:
            return
        x0, y0 = self._start
        x1, y1 = event.x, event.y
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))

        # Çok küçük (yanlışlıkla tek tık) seçimleri yok say
        if (right - left) < 10 or (bottom - top) < 10:
            self._on_cancel(event)
            return

        self.result = (
            left + self._origin_x,
            top + self._origin_y,
            right + self._origin_x,
            bottom + self._origin_y,
        )
        self.top.destroy()

    def _on_cancel(self, _event=None) -> None:
        self.result = None
        self.top.destroy()


def pick_region(master: tk.Misc | None = None) -> tuple[int, int, int, int] | None:
    """
    Kullanıcıya bölge seçtirir, (left, top, right, bottom) döner.
    İptal edilirse (Esc) None döner.

    `master` verilirse mevcut bir Tk uygulamasının (kontrol paneli)
    içine gömülür; verilmezse kendi bağımsız kökünü açıp kapatır.
    """
    owns_root = False
    if master is None:
        master = tk.Tk()
        master.withdraw()
        owns_root = True

    selector = _RegionSelectorWindow(master)
    master.wait_window(selector.top)

    if owns_root:
        master.destroy()

    return selector.result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    region = pick_region()
    if region:
        print(f"Seçilen bölge: {region}")
    else:
        print("Seçim iptal edildi.")
