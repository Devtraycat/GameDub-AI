# GameDub AI

Gerçek zamanlı oyun altyazısı yakalama, çeviri ve yapay zekâ dublaj sistemi.

```
Ekran -> OCR -> Analiz -> Çeviri -> Konuşmacı Tahmini -> TTS (+cache) -> Ses + Overlay
```

Mimari, dokümandaki tasarıma göre tamamen modülerdir: her `engines/` dosyası
tek bir işten sorumludur ve gerçek "motor" seçimleri `plugins/` altında
değiştirilebilir eklentilerdir.

## Kurulum

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

pip install -r requirements.txt
```

Linux'ta ses için ek olarak gerekebilir:
```bash
sudo apt-get install espeak libasound2-dev
```

## Ayarları yapılandırma

Tüm ayarlar `config.py` içinde. En önemlileri:

- `CONFIG.capture.mode` / `region` → altyazının ekranda hangi bölgede olduğu
- `CONFIG.capture.window_title` → belirli bir oyun penceresini hedeflemek için (`mode="window"`)
- `CONFIG.ocr.engine` → `"rapidocr"` (varsayılan) veya `"tesseract"`
- `CONFIG.translation.engine` → `"argos"` (offline, varsayılan) veya `"google"` (online, deep-translator)
- `CONFIG.voice.engine` → `"edge_tts"` (varsayılan, internet gerektirir, Türkçe kalitesi çok iyi) veya `"pyttsx3"` (tamamen offline, kalite daha robotik)

**Not:** Projedeki hiçbir bileşen PyTorch kullanmaz. OCR için ONNX Runtime (RapidOCR),
çeviri için CTranslate2 (Argos Translate), TTS için işletim sistemi motoru (pyttsx3) veya
bulut servisi (edge-tts) tercih edildi — hepsi hafif ve hızlı başlar, GPU/büyük model
indirme gerektirmez.

## Çalıştırma

1. Oyunu pencere modunda açın (fullscreen değil, "borderless windowed" tavsiye edilir).
2. `config.py` içinde `capture.region` değerini, altyazıların çıktığı ekran
   koordinatlarına göre ayarlayın (ör. ekran görüntüsü alıp piksel ölçün).
3. Çalıştırın:

```bash
python main.py
```

İlk çalıştırmada:
- RapidOCR modelini otomatik indirir (küçük, birkaç saniye sürer).
- Argos Translate, `en->tr` dil paketini otomatik indirir (tek seferlik, internet gerekir).

Bundan sonrası tamamen offline çalışır (edge_tts / google plugin'lerini seçmediyseniz).

## Yeni bir eklenti eklemek

Örnek: yeni bir OCR motoru eklemek istiyorsanız:

```
plugins/ocr/benim_ocr_plugin.py
```

içinde `OCRPlugin` sınıfını, `recognize(image) -> list[dict]` metoduyla
tanımlayın, sonra `config.py`'de:

```python
CONFIG.ocr.engine = "benim_ocr"
```

Ana sistemde tek satır bile değişmez.

## Yol Haritası

- [x] Sürüm 1.0 — Capture, RapidOCR, Argos, pyttsx3, cache, temel konuşmacı ayrımı, overlay
- [ ] Sürüm 1.5 — Gelişmiş konuşmacı analizi (renk/isim eşleme iyileştirmesi), çoklu TTS
- [ ] Sürüm 2.0 — Oyun profilleri, eklenti ekosistemi, gerçek zamanlı önceliklendirme

## Bilinen Sınırlamalar

- `pyttsx3` pitch kontrolünü platforma göre kısıtlı destekler; iki karakteri
  daha belirgin ayırt etmek isterseniz `edge_tts` eklentisine geçin (internet gerektirir).
- Konuşmacı tespiti şu an isim-satırı / renk / dönüşümlü heuristiğe dayanır;
  görsel karakter tanıma (avatar vb.) kapsamda değildir.
- Overlay, `tkinter` kullanır; bazı Linux masaüstü ortamlarında
  "always-on-top" davranışı pencere yöneticisine göre değişebilir.