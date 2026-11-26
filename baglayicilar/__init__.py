"""Limit Çubuğu - bağlayıcı kayıt defteri (otomatik bulma).

`baglayicilar/` klasöründeki her modül `BAGLAYICI` adıyla bir taban.Baglayici nesnesi verir;
bu dosya onları tembel olarak (ilk `hepsi()` çağrısında) bulup yükler. Hiçbir genel
fonksiyon dışarı istisna fırlatmaz; yüklenemeyen modüller `yukleme_hatalari()`nda görünür.
"""
import importlib
import pkgutil
import threading

from . import taban

_BILINEN = ("claude", "codex", "antigravity", "copilot")  # iter_modules ad bulamazsa (tek .exe) denenir
_HATALAR = {}
_ONBELLEK = None
_KILIT = threading.RLock()


def _modulleri_yukle():
    """Paketteki bağlayıcı modüllerini bulup yükler -> list[modül]. Hatalıyı atlar."""
    moduller = []
    try:
        adlar = sorted(a for _, a, _ in pkgutil.iter_modules(__path__))
    except Exception:
        adlar = []
    adlar = [a for a in adlar if a != "taban" and not a.startswith("_")]
    if not adlar:
        adlar = list(_BILINEN)
    denenen = set()

    def dene(ad):
        denenen.add(ad)
        try:
            moduller.append(importlib.import_module(f"{__name__}.{ad}"))
        except Exception as h:
            _HATALAR[ad] = f"{type(h).__name__}: {h}"

    for ad in adlar:
        dene(ad)
    if not moduller:
        for ad in _BILINEN:
            if ad not in denenen:
                dene(ad)
    return moduller


def hepsi():
    """Geçerli tüm bağlayıcılar, (sira, kimlik) sıralı. Önbellekli, iş parçacığı güvenli."""
    global _ONBELLEK
    with _KILIT:
        if _ONBELLEK is not None:
            return list(_ONBELLEK)
        _HATALAR.clear()
        try:
            moduller = _modulleri_yukle()
        except Exception as h:
            _HATALAR["_yukleme"] = f"{type(h).__name__}: {h}"
            moduller = []
        bulunan = {}
        for m in moduller:
            ad = getattr(m, "__name__", repr(m)).rsplit(".", 1)[-1]
            try:
                b = getattr(m, "BAGLAYICI", None)
                if not isinstance(b, taban.Baglayici):
                    _HATALAR[ad] = "BAGLAYICI yok ya da Baglayici örneği değil"
                    continue
                if not isinstance(b.kimlik, str) or not b.kimlik.strip():
                    _HATALAR[ad] = "BAGLAYICI kimliği geçersiz ya da boş"
                    continue
                if isinstance(b.sira, bool) or not isinstance(b.sira, (int, float)):
                    _HATALAR[ad] = "BAGLAYICI sırası sayı değil"
                    continue
                if b.kimlik in bulunan:
                    _HATALAR[ad] = f"kimlik tekrarı: {b.kimlik}"
                    continue
                bulunan[b.kimlik] = b
            except Exception as h:
                _HATALAR[ad] = f"{type(h).__name__}: {h}"
        liste = list(bulunan.values())
        try:
            liste = sorted(liste, key=lambda x: (x.sira, x.kimlik))
        except Exception as h:
            _HATALAR["_sirala"] = f"{type(h).__name__}: {h}"
        _ONBELLEK = liste
        return list(_ONBELLEK)


def getir(kimlik):
    """Kimliğe göre bağlayıcı; yoksa None."""
    try:
        for b in hepsi():
            if b.kimlik == kimlik:
                return b
    except Exception:
        pass
    return None


def kimlikler():
    """Bağlayıcı kimlikleri (hepsi() sırasıyla)."""
    try:
        return tuple(b.kimlik for b in hepsi())
    except Exception:
        return ()


def bulunanlar():
    """bul() True dönen bağlayıcılar; bul() istisna fırlatırsa yok sayılır."""
    sonuc = []
    try:
        for b in hepsi():
            try:
                if b.bul():
                    sonuc.append(b)
            except Exception:
                pass
    except Exception:
        pass
    return sonuc


def yukleme_hatalari():
    """Yükleme/doğrulama hatalarının kopyası: {modül adı: mesaj}."""
    try:
        with _KILIT:
            return dict(_HATALAR)
    except Exception:
        return {}


def yeniden_yukle():
    """Önbelleği ve hata kaydını temizler; sonraki hepsi() yeniden yükler."""
    global _ONBELLEK
    with _KILIT:
        _ONBELLEK = None
        _HATALAR.clear()
