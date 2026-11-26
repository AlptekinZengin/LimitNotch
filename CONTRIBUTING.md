# Contributing to LimitNotch

Thanks for wanting to add a connector or improve LimitNotch!

## Adding a new AI tool connector

Each supported tool lives in a single file under `baglayicilar/` (e.g. `baglayicilar/mytool.py`). LimitNotch discovers files in that folder automatically. Start from the template in [docs/ornek_baglayici.py](docs/ornek_baglayici.py).

### 1. Contract

Export a module-level `BAGLAYICI` instance subclassing `baglayicilar.taban.Baglayici`:

- `kimlik`: ASCII lowercase key stored in `durum.json` (e.g. `"mytool"`)
- `ad`: Display name shown in setup & cards (e.g. `"MyTool"`)
- `kisa_ad`: Short label for the compact notch (e.g. `"MT"`)
- `renk`: Brand hex color `"#RRGGBB"`
- `durum`: `KARARLI` (official CLI/RPC) or `DENEYSEL` (undocumented local/CLI endpoint; may break on updates)
- `sira`: Sort order integer (smaller appears first)
- `okuma_yolu` / `okuma_yolu_anahtari`: One-line description of where limits come from (shown in setup UI & README)
- `bul() -> bool`: Fast check whether the tool appears installed locally. **No subprocesses, no network requests, never raises.**
- `yenile(yol=None) -> (bool, str)`: Reads limits, writes atomically to `yol or ortak.DURUM_DOSYASI` under `ortak.KILIT`, and returns `(success, short_message)`. On failure, **do not modify existing data** and **never raise**.

### 2. Strict Rules (Non-Negotiable)

- **No credentials, tokens, or cookies:** Never read auth/credential files, browser cookies, or session tokens. Never make direct HTTP calls to external APIs. Only invoke the tool's own official CLI/local server or read non-secret local state files it writes.
- **Respect Terms of Service:** Do not add connectors that rely on ToS-prohibited scraping or cookie extraction (e.g., Cursor personal accounts).
- **No manual input:** LimitNotch has no manual paste/edit mode. If a tool cannot be read automatically, do not add it.
- **Single-EXE registration:** Also add your module name to `_BILINEN` in `baglayicilar/__init__.py` and `hiddenimports` in `LimitNotch.spec`.
- **Tests:** Add unit tests (`test_<tool>.py`) using mocked subprocesses/files and temporary paths. Do not touch `%USERPROFILE%\.limit-cubugu\durum.json`.

### 3. Running tests

```powershell
py -3 -m unittest discover -p "test_*.py"
py -3 tara.py
```

---

# LimitNotch'a Katkı Rehberi (Türkçe)

Yeni bir araç bağlayıcısı eklemek için `baglayicilar/` klasörü altına tek bir Python dosyası eklemeniz yeterlidir (`docs/ornek_baglayici.py` şablonunu başlangıç noktası olarak kullanabilirsiniz).

### 1. Bağlayıcı sözleşmesi

Modül düzeyinde `baglayicilar.taban.Baglayici` sınıfından türeyen `BAGLAYICI` nesnesi dışa aktarılır:

- `kimlik`: `durum.json` anahtarı (küçük harf ASCII)
- `ad` / `kisa_ad`: Panel/kartta ve dar çentikte görünen ad
- `renk`: `#RRGGBB` biçiminde marka rengi
- `durum`: `KARARLI` (resmi CLI/sunucu yolu) veya `DENEYSEL` (belgesiz yerel/CLI yolu; güncellemeyle bozulabilir)
- `sira`: Gösterim sırası
- `okuma_yolu` / `okuma_yolu_anahtari`: Okuma kaynağının tek satırlık açıklaması
- `bul() -> bool`: Araç kurulu mu? Hızlı, alt süreçsiz, ağsız olmalı ve istisna fırlatmamalıdır.
- `yenile(yol=None) -> (bool, str)`: Limitleri okuyup `ortak.KILIT` altında `yol or ortak.DURUM_DOSYASI` dosyasına atomik yazar. Hata durumunda mevcut veriyi korur ve istisna fırlatmaz.

### 2. Değişmez Kurallar

- **Şifre, anahtar, çerez yok:** Hiçbir aracın giriş/kimlik dosyası okunmaz, tarayıcı çerezine dokunulmaz, internete doğrudan istek atılmaz. Yalnız aracın kendi programı veya yerel dosyası kullanılır.
- **Kullanım şartlarına aykırı yol yok:** Şartların yasakladığı yöntemler (ör. Cursor kişisel hesap çerezi) eklenmez.
- **Elle giriş yok:** Kendiliğinden okunamayan araç eklenmez.
- **Tek `.exe` uyumu:** Yeni modül adını `baglayicilar/__init__.py` içindeki `_BILINEN` listesine ve `LimitNotch.spec` içindeki `hiddenimports` listesine ekleyin.
- **Testler:** Geçici dosya ve sahte (mock) yanıtlarla birim testi (`test_<arac>.py`) ekleyin.
