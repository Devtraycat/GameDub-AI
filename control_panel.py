"""
Kontrol Paneli
--------------
Kullanıcının "çalışıyor mu, çalışmıyor mu, hata mı aldık, nerede
sıkıntı var?" sorularına doğrudan cevap veren küçük bir masaüstü
arayüzü:

- Başlat / Durdur butonları
- Canlı durum (çalışıyor/durduruldu, kare sayacı, son altyazı, hata sayacı)
- Kaydırılabilir canlı log ekranı (konsola giden her şey burada da görünür)
- "Bölge Seç" butonu (tools/region_selector.py aracını açar)

Bu pencere, Tkinter mainloop'unu elinde tutan ana pencere (root)'dur;
altyazı overlay'i buna bağlı bir Toplevel olarak eklenir (aynı anda
iki ayrı `tk.Tk()` kökü açmak yerine).
"""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox

from tools.region_selector import pick_region
from config import SETTINGS_SCHEMA, get_path

log = logging.getLogger(__name__)

_REFRESH_MS = 300


class ControlPanel:
    def __init__(self, app, log_queue: "queue.Queue[str] | None" = None):
        self.app = app
        self.log_queue = log_queue

        self.root = tk.Tk()
        self.root.title("GameDub AI - Kontrol Paneli")
        self.root.geometry("640x460")
        self.root.minsize(520, 380)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_widgets()
        self._schedule_refresh()

    # ------------------------------------------------------------------ UI

    def _build_widgets(self) -> None:
        top = tk.Frame(self.root, padx=10, pady=10)
        top.pack(fill="x")

        self.start_btn = tk.Button(top, text="▶ Başlat", width=12, command=self._on_start)
        self.start_btn.pack(side="left", padx=(0, 6))

        self.stop_btn = tk.Button(top, text="⏹ Durdur", width=12, command=self._on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 6))

        self.region_btn = tk.Button(top, text="🖱 Bölge Seç", width=14, command=self._on_pick_region)
        self.region_btn.pack(side="left", padx=(0, 6))

        self.settings_btn = tk.Button(top, text="⚙ Ayarlar", width=12, command=self._on_open_settings)
        self.settings_btn.pack(side="left", padx=(0, 6))

        self.status_dot = tk.Label(top, text="●", fg="#c0392b", font=("Segoe UI", 14))
        self.status_dot.pack(side="right")
        self.status_label = tk.Label(top, text="Durduruldu", font=("Segoe UI", 11, "bold"))
        self.status_label.pack(side="right", padx=(0, 6))

        info = tk.LabelFrame(self.root, text="Durum", padx=10, pady=8)
        info.pack(fill="x", padx=10)

        self.region_val = self._info_row(info, "Yakalama bölgesi:", 0)
        self.frame_val = self._info_row(info, "Yakalanan kare sayısı:", 1)
        self.last_source_val = self._info_row(info, "Son altyazı (kaynak):", 2)
        self.last_translation_val = self._info_row(info, "Son çeviri:", 3)
        self.error_val = self._info_row(info, "Hata sayısı:", 4)

        log_frame = tk.LabelFrame(self.root, text="Canlı Log", padx=6, pady=6)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(8, 10))

        self.log_widget = scrolledtext.ScrolledText(
            log_frame, height=12, state="disabled", bg="#111318", fg="#d8dee9",
            insertbackground="#d8dee9", font=("Consolas", 9),
        )
        self.log_widget.pack(fill="both", expand=True)

    def _info_row(self, parent: tk.Widget, label_text: str, row: int) -> tk.Label:
        tk.Label(parent, text=label_text, anchor="w", width=22, font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, sticky="w", pady=2
        )
        value = tk.Label(parent, text="-", anchor="w", font=("Segoe UI", 9))
        value.grid(row=row, column=1, sticky="w", pady=2)
        return value

    # ------------------------------------------------------------- actions

    def _on_start(self) -> None:
        try:
            self.app.start()
        except Exception:
            log.exception("Başlatma sırasında beklenmeyen hata.")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def _on_stop(self) -> None:
        self.app.stop()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def _on_pick_region(self) -> None:
        region = pick_region(master=self.root)
        if region is None:
            log.info("Bölge seçimi iptal edildi.")
            return
        self.app.update_region(region)

    def _on_open_settings(self) -> None:
        SettingsWindow(self.root, self.app)

    def _on_close(self) -> None:
        try:
            self.app.stop()
        except Exception:
            pass
        self.root.destroy()

    # ------------------------------------------------------------ refresh

    def _schedule_refresh(self) -> None:
        self.root.after(_REFRESH_MS, self._refresh)

    def _refresh(self) -> None:
        self._drain_logs()
        self._refresh_status()
        self._schedule_refresh()

    def _drain_logs(self) -> None:
        if self.log_queue is None:
            return
        drained_any = False
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_widget.configure(state="normal")
            self.log_widget.insert("end", line + "\n")
            drained_any = True
        if drained_any:
            self.log_widget.see("end")
            self.log_widget.configure(state="disabled")

    def _refresh_status(self) -> None:
        status = self.app.get_status()

        running = status.get("running", False)
        self.status_label.config(text="Çalışıyor" if running else "Durduruldu")
        self.status_dot.config(fg="#27ae60" if running else "#c0392b")

        mode, region = status.get("region_info", ("region", None))
        self.region_val.config(text=f"{mode}: {region}")
        self.frame_val.config(text=str(status.get("frame_count", 0)))
        self.last_source_val.config(text=status.get("last_source") or "-")
        self.last_translation_val.config(text=status.get("last_translation") or "-")
        self.error_val.config(text=str(status.get("error_count", 0)))

    # ------------------------------------------------------------- run

    def run_forever(self) -> None:
        self.root.mainloop()


class SettingsWindow:
    """
    v1.6: `config.py:SETTINGS_SCHEMA` içindeki HER ayarı (yeni bir ayar
    eklendiğinde otomatik olarak burada da görünür - şemadan üretilir,
    elle senkronize edilmesi gerekmez) sekmeler halinde gösterir.

    "💾 Kaydet": her değişen alan için `app.apply_setting(path, value)`
    çağrılır -> hem CONFIG'e anında yazılır hem diske kalıcı kaydedilir
    (gerekiyorsa ilgili motor - ör. OCR - yeniden yüklenir).

    v1.7 - kritik düzeltme:
    -----------------------
    Eskiden buton satırı, TÜM sekme içeriği (`expand=True` ile) paketlendikten
    SONRA paketleniyordu. Sekmelerdeki ayar sayısı arttıkça ya da pencere
    varsayılan boyuttan küçük bir ekranda açıldığında, buton satırı görünür
    alanın DIŞINA itiliyor ve kullanıcı "Kaydet" butonunu hiç GÖRMÜYORDU -
    buton çalışıyordu ama erişilemiyordu. Şimdi:
      1) Buton satırı pencereye İLK önce, sabit ve `side="bottom"` ile
         eklenir - bu yüzden içerik ne kadar uzarsa uzasın her zaman görünür.
      2) Her sekme artık kaydırılabilir (Canvas + Scrollbar) - hiçbir ayar
         "ekranın altında kalıp" erişilemez hale gelmez.
      3) Kaydetme sonrası açıkça "✓ Kaydedildi" onayı gösterilir (sessizce
         loglamak yerine) - böylece kullanıcı kaydın gerçekten olduğunu görür.
    """

    def __init__(self, master: tk.Misc, app):
        self.app = app
        self.win = tk.Toplevel(master)
        self.win.title("Ayarlar")
        self.win.geometry("620x560")
        self.win.minsize(480, 360)
        self.win.transient(master)

        # --- 1) Buton satırı ÖNCE ve sabit: içerik ne kadar uzun olursa
        # olsun her zaman görünür kalır (bkz. yukarıdaki v1.7 notu).
        btn_row = tk.Frame(self.win, padx=8, pady=8)
        btn_row.pack(side="bottom", fill="x")
        self.status_label = tk.Label(btn_row, text="", fg="#2e7d32")
        self.status_label.pack(side="left")
        tk.Button(btn_row, text="Kapat", command=self.win.destroy).pack(side="right")
        tk.Button(btn_row, text="💾 Kaydet", command=self._on_save,
                  default="active").pack(side="right", padx=(0, 6))

        notebook = ttk.Notebook(self.win)
        notebook.pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))

        self._vars: dict[str, tk.Variable] = {}

        groups: dict[str, list[dict]] = {}
        for spec in SETTINGS_SCHEMA:
            groups.setdefault(spec["group"], []).append(spec)

        for group_name, specs in groups.items():
            tab_container = self._make_scrollable_tab(notebook, group_name)
            for row, spec in enumerate(specs):
                self._build_row(tab_container, row, spec)

    def _make_scrollable_tab(self, notebook: ttk.Notebook, title: str) -> tk.Frame:
        """
        v1.7: her sekme artık bir Canvas + dikey Scrollbar içine sarılıyor.
        Ekran küçük olsa ya da bir gruba çok fazla ayar eklense bile hiçbir
        satır erişilemez hale gelmiyor - kaydırarak her zaman ulaşılabiliyor.
        """
        outer = tk.Frame(notebook)
        notebook.add(outer, text=title)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, padx=10, pady=10)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            delta = -1 * (event.delta // 120) if event.delta else (1 if event.num == 5 else -1)
            canvas.yview_scroll(delta, "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return inner

    def _build_row(self, parent: tk.Widget, row: int, spec: dict) -> None:
        path = spec["path"]
        current = get_path(self.app.config, path)

        tk.Label(parent, text=spec["label"], anchor="w", wraplength=320, justify="left").grid(
            row=row, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        kind = spec["type"]
        if kind == "bool":
            var = tk.BooleanVar(value=bool(current))
            widget = tk.Checkbutton(parent, variable=var)
        elif kind == "choice":
            var = tk.StringVar(value=str(current))
            widget = ttk.Combobox(parent, textvariable=var, values=spec["choices"],
                                   state="readonly", width=18)
        else:  # "int" | "float" | "text"
            var = tk.StringVar(value=str(current))
            widget = tk.Entry(parent, textvariable=var, width=32)

        widget.grid(row=row, column=1, sticky="w", pady=4)
        self._vars[path] = var

    def _on_save(self) -> None:
        changed: list[str] = []
        errors: list[str] = []

        for spec in SETTINGS_SCHEMA:
            path = spec["path"]
            var = self._vars[path]
            raw_value = var.get()
            current = get_path(self.app.config, path)

            try:
                if spec["type"] == "bool":
                    new_value = bool(raw_value)
                elif spec["type"] == "int":
                    new_value = int(raw_value)
                elif spec["type"] == "float":
                    new_value = float(raw_value)
                else:
                    new_value = raw_value
            except (ValueError, TypeError):
                errors.append(f"{spec['label']}: geçersiz değer ({raw_value!r})")
                log.warning("Geçersiz değer atlandı: %s = %r", path, raw_value)
                continue

            if new_value == current:
                continue  # değişmemiş -> gereksiz motor yeniden yüklemesi yapma

            try:
                self.app.apply_setting(path, new_value)
                changed.append(spec["label"])
            except Exception as e:
                errors.append(f"{spec['label']}: {e}")
                log.exception("Ayar uygulanırken hata oluştu: %s", path)

        # v1.7: sessizce loglamak yerine kullanıcıya AÇIKÇA ne olduğunu göster.
        if errors:
            messagebox.showerror(
                "Bazı ayarlar kaydedilemedi",
                "Aşağıdaki ayarlar uygulanamadı:\n\n" + "\n".join(errors),
                parent=self.win,
            )
        if changed:
            self.status_label.config(text=f"✓ Kaydedildi ({len(changed)} ayar)")
            messagebox.showinfo(
                "Kaydedildi",
                "Şu ayarlar güncellendi ve diske kalıcı kaydedildi:\n\n" + "\n".join(changed),
                parent=self.win,
            )
        elif not errors:
            self.status_label.config(text="Değişiklik yok")
