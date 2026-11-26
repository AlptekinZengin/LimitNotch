"""Otomatik arka plan yenilemesinin saf mantik katmani (arayuzden bagimsiz)."""
import sys
import threading
import time


def pilde_mi():
    """Windows'ta sebeke yoksa (pilde) True; hata veya Windows disinda False."""
    try:
        if sys.platform != "win32":
            return False
        import ctypes
        from ctypes import wintypes

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [("ACLineStatus", wintypes.BYTE),
                        ("BatteryFlag", wintypes.BYTE),
                        ("BatteryLifePercent", wintypes.BYTE),
                        ("SystemStatusFlag", wintypes.BYTE),
                        ("BatteryLifeTime", wintypes.DWORD),
                        ("BatteryFullLifeTime", wintypes.DWORD)]

        durum = SYSTEM_POWER_STATUS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(durum)):
            return False
        return durum.ACLineStatus == 0
    except Exception:
        return False


class OtomatikPlan:
    """Hangi aracin ne zaman yenilenecegini hesaplar; thread guvenlidir."""

    def __init__(self, aralik_sn=300, pil_aralik_sn=900,
                 geri_cekilme_sn=(300, 600, 1200, 1800), zaman=None, pilde_mi=None):
        self._aralik = aralik_sn
        self._pil_aralik = pil_aralik_sn
        self._geri = tuple(geri_cekilme_sn)
        self._zaman = zaman or time.time
        self._pilde = pilde_mi if pilde_mi is not None else globals()["pilde_mi"]
        self._kilit = threading.Lock()
        self._son = {}
        self._hata = {}
        self._suren = set()

    def _simdi(self, simdi):
        return self._zaman() if simdi is None else simdi

    def _aralik_hesapla(self, arac, pilde):
        temel = self._pil_aralik if pilde else self._aralik
        hata = self._hata.get(arac, 0)
        if hata > 0 and self._geri:
            temel = max(temel, self._geri[min(hata - 1, len(self._geri) - 1)])
        return temel

    def vadesi_gelenler(self, araclar, simdi=None):
        """Vadesi gelen araclari girdi sirasiyla dondurur."""
        t = self._simdi(simdi)
        try:
            pilde = bool(self._pilde())
        except Exception:
            pilde = False
        with self._kilit:
            sonuc = []
            for arac in araclar:
                if arac in self._suren:
                    continue
                son = self._son.get(arac)
                if son is None or t - son >= self._aralik_hesapla(arac, pilde):
                    sonuc.append(arac)
            return sonuc

    def basladi(self, arac, simdi=None):
        """Yenileme basladi; bitene kadar arac tekrar vadeli sayilmaz."""
        with self._kilit:
            self._suren.add(arac)

    def sonuc_bildir(self, arac, basarili, simdi=None):
        """Yenileme sonucunu kaydeder; hata sayacini gunceller."""
        t = self._simdi(simdi)
        with self._kilit:
            self._suren.discard(arac)
            self._hata[arac] = 0 if basarili else self._hata.get(arac, 0) + 1
            self._son[arac] = t

    def hata_sayisi(self, arac):
        """Ardisik hata sayisi."""
        with self._kilit:
            return self._hata.get(arac, 0)

    def son_deneme(self, arac):
        """Son deneme zamani (yoksa None)."""
        with self._kilit:
            return self._son.get(arac)
