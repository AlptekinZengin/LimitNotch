"""Limit Çubuğu - ortak veri katmanı.

durum.json yapısı:
{
  "surum": 1,
  "claude":      {"kaynak": "otomatik"|"elle", "guncellendi": <epoch sn>,
                  "bes_saat": {"kalan": 78.0, "resets_at": <epoch sn|null>},
                  "haftalik": {"kalan": 91.0, "resets_at": <epoch sn|null>}},
  "codex":       {...},
  "antigravity": {...}
}
Yalnızca standart kütüphane kullanır. Hiçbir ağ / kimlik bilgisi erişimi yoktur.
"""
import json
import math
import os
import tempfile
import threading
import time
from datetime import datetime

VERI_KLASORU = os.path.join(os.path.expanduser("~"), ".limit-cubugu")
# Testler gerçek dosyaya dokunmasın diye LIMIT_CUBUGU_DOSYA ile yol değiştirilebilir.
DURUM_DOSYASI = os.environ.get("LIMIT_CUBUGU_DOSYA") or os.path.join(VERI_KLASORU, "durum.json")

ARACLAR = ("claude", "codex", "antigravity")
PENCERELER = ("bes_saat", "haftalik")


# Oku-değiştir-yaz yapan herkes bunu tutar (yenile() araç başına iş parçacığında çalışır).
KILIT = threading.RLock()


def bos_durum():
    return {"surum": 1}


def oku(yol=DURUM_DOSYASI):
    """durum.json'u okur; dosya yoksa ya da bozuksa boş durum döner (asla hata fırlatmaz)."""
    try:
        with open(yol, "r", encoding="utf-8") as f:
            veri = json.load(f)
        if isinstance(veri, dict):
            return veri
    except Exception:
        pass
    return bos_durum()


def yaz(veri, yol=DURUM_DOSYASI):
    """Atomik yazım: aynı klasörde geçici dosya + os.replace."""
    klasor = os.path.dirname(os.path.abspath(yol))
    if klasor:
        os.makedirs(klasor, exist_ok=True)
    fd, gecici = tempfile.mkstemp(prefix=".durum-", suffix=".tmp", dir=klasor)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Windows'ta okuyucu dosyayı o an açık tutuyorsa replace kısa süre başarısız olabilir.
        for deneme in range(10):
            try:
                os.replace(gecici, yol)
                return True
            except PermissionError:
                time.sleep(0.02 * (deneme + 1))
        return False
    finally:
        if os.path.exists(gecici):
            try:
                os.remove(gecici)
            except OSError:
                pass


def guncelle(arac, alanlar, yol=DURUM_DOSYASI):
    """Oku-değiştir-yaz: yalnızca verilen aracın bölümünü günceller."""
    with KILIT:
        veri = oku(yol)
        bolum = veri.get(arac)
        if not isinstance(bolum, dict):
            bolum = {}
        for anahtar, deger in alanlar.items():
            if anahtar in PENCERELER and isinstance(deger, dict):
                eski = bolum.get(anahtar) if isinstance(bolum.get(anahtar), dict) else {}
                eski.update(deger)
                bolum[anahtar] = eski
            else:
                bolum[anahtar] = deger
        bolum["guncellendi"] = time.time()
        veri[arac] = bolum
        veri.setdefault("surum", 1)
        return yaz(veri, yol)


def ayar_guncelle(alanlar, yol=DURUM_DOSYASI):
    """Üst düzey kullanıcı tercihlerini (ör. seçili monitör) durum.json'a kaydeder."""
    with KILIT:
        veri = oku(yol)
        veri.update(alanlar)
        veri.setdefault("surum", 1)
        return yaz(veri, yol)


def zaman_cevir(deger):
    """resets_at değerini epoch saniyeye çevirir (sn, ms ya da ISO 8601 metin)."""
    if deger is None or isinstance(deger, bool):
        return None
    if isinstance(deger, (int, float)):
        d = float(deger)
        if not math.isfinite(d):
            return None
        if d > 1e12:  # milisaniye
            d /= 1000.0
        return d if d > 0 else None
    if isinstance(deger, str):
        s = deger.strip()
        if not s:
            return None
        try:
            return zaman_cevir(float(s))
        except ValueError:
            pass
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            t = datetime.fromisoformat(s).timestamp()
            return t if math.isfinite(t) and t > 0 else None
        except ValueError:
            return None
    return None


def sayi(deger):
    try:
        if deger is None or isinstance(deger, bool):
            return None
        v = float(deger)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def pencere_durumu(bolum, pencere, simdi=None):
    """Bir pencere için (kalan, resets_at, yenilendi_mi) döner. Veri yoksa kalan=None.

    resets_at geçmişte kaldıysa pencere yenilenmiş sayılır: kalan=100.
    """
    simdi = time.time() if simdi is None else simdi
    if not isinstance(bolum, dict):
        return None, None, False
    p = bolum.get(pencere)
    if not isinstance(p, dict):
        return None, None, False
    kalan = sayi(p.get("kalan"))
    reset = zaman_cevir(p.get("resets_at"))
    if kalan is None:
        return None, reset, False
    kalan = max(0.0, min(100.0, kalan))
    if reset is not None and reset <= simdi:
        return 100.0, reset, True
    return kalan, reset, False
