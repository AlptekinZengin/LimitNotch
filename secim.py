"""Limit Çubuğu - hangi araçların çubukta gösterileceği (seçim).

Seçim durum.json'da "araclar" anahtarında kimlik listesi olarak tutulur.
Yalnızca standart kütüphane + durum_ortak + baglayicilar; tkinter yok.
Hiçbir fonksiyon istisna fırlatmaz.
"""
import baglayicilar
import durum_ortak as ortak
from baglayicilar import taban

AYAR_ANAHTARI = "araclar"

_YEDEK_BILGI = {"renk": "#94A3B8", "durum": taban.KARARLI, "okuma_yolu": ""}


def kayitli_secim(durum):
    """Kayıtlı seçim (str listesi) ya da None."""
    try:
        deger = durum.get(AYAR_ANAHTARI)
        if isinstance(deger, list):
            return [k for k in deger if isinstance(k, str)]
    except Exception:
        pass
    return None


def _kayitli_kimlikler():
    try:
        return list(baglayicilar.kimlikler())
    except Exception:
        return []


def _eski_kullanici(durum, tum):
    """Durumda bölümü (dict) olan kayıtlı kimlikler, kayıt defteri sırasıyla."""
    try:
        return [k for k in tum if isinstance(durum.get(k), dict)]
    except Exception:
        return []


def etkin_kimlikler(durum):
    """Çubukta gösterilecek kimlikler, her zaman kayıt defteri sırasıyla."""
    try:
        tum = _kayitli_kimlikler()
        secim = kayitli_secim(durum)
        if secim is not None:
            eslesen = [k for k in tum if k in secim]
            if eslesen:
                return eslesen
        eski = _eski_kullanici(durum, tum)
        if eski:
            return eski
        try:
            kararli = {b.kimlik for b in baglayicilar.bulunanlar()
                       if getattr(b, "durum", None) == taban.KARARLI}
        except Exception:
            kararli = set()
        bulunan = [k for k in tum if k in kararli]
        return bulunan if bulunan else tum
    except Exception:
        return []


def kurulum_gerekli(durum):
    """Kayıtlı seçim yok ve eski kullanıcı izi de yoksa True."""
    try:
        if kayitli_secim(durum) is not None:
            return False
        return not _eski_kullanici(durum, _kayitli_kimlikler())
    except Exception:
        return False


def secimi_kaydet(kimlikler, yol=None):
    """Seçimi durum.json'a yazar -> bool."""
    try:
        return ortak.ayar_guncelle({AYAR_ANAHTARI: list(kimlikler)}, yol or ortak.DURUM_DOSYASI)
    except Exception:
        return False


def bilgi(kimlik):
    """Kimlik için görünüm bilgisi: ad, kisa_ad, renk, durum, okuma_yolu."""
    try:
        b = baglayicilar.getir(kimlik)
        if b is not None:
            yol_metni = b.gorunen_okuma_yolu() if hasattr(b, "gorunen_okuma_yolu") else b.okuma_yolu
            return {"ad": b.ad or kimlik, "kisa_ad": b.gorunen_kisa_ad(), "renk": b.renk,
                    "durum": b.durum, "okuma_yolu": yol_metni}
    except Exception:
        pass
    return {"ad": kimlik, "kisa_ad": kimlik, **_YEDEK_BILGI}
