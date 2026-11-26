"""Example LimitNotch connector template / Örnek LimitNotch bağlayıcı şablonu.

Copy this file into `baglayicilar/<tool>.py`, customize it, then register `<tool>`
in `baglayicilar/__init__.py` (`_BILINEN`) and `LimitNotch.spec` (`hiddenimports`).

Bu dosyayı `baglayicilar/<arac>.py` olarak kopyalayıp düzenleyin; ardından `<arac>`
adını `baglayicilar/__init__.py` (`_BILINEN`) ve `LimitNotch.spec` (`hiddenimports`)
listelerine ekleyin.
"""
import os
import shutil
import sys
import time

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

import durum_ortak as ortak  # noqa: E402
from baglayicilar.taban import Baglayici, KARARLI  # noqa: E402  # or/veya DENEYSEL


class OrnekBaglayici(Baglayici):
    kimlik = "ornek"
    ad = "Example Tool"
    kisa_ad = "EX"
    renk = "#60A5FA"
    durum = KARARLI  # KARARLI or DENEYSEL
    sira = 90
    okuma_yolu = "Aracın kendi yerel komutu (giriş bilgisine dokunulmaz)"

    def bul(self):
        """Fast local check (no subprocesses, no network). / Hızlı yerel kontrol."""
        try:
            return shutil.which("example-cli") is not None
        except Exception:
            return False

    def yenile(self, yol=None):
        """Read limits via the tool's own CLI and write atomically. / Limiti okuyup atomik yaz."""
        yol = yol or ortak.DURUM_DOSYASI
        try:
            # 1) Run tool CLI or read local state (never read credentials/cookies).
            #    Aracın kendi CLI'sını çalıştır veya yerel durumu oku (şifre/çerez yok).
            alanlar = {
                "kaynak": "Auto (refreshed)",
                "bes_saat": {"kalan": 80.0, "resets_at": time.time() + 3600},
                "haftalik": {"kalan": 92.0, "resets_at": time.time() + 86400 * 3},
            }
            # 2) Write under ortak.KILIT; preserve existing data on failure.
            #    ortak.KILIT altında yaz; hata olursa mevcut veriyi koru.
            with ortak.KILIT:
                if not ortak.guncelle(self.kimlik, alanlar, yol):
                    return False, "Example: failed to write durum.json"
            return True, "Example limits refreshed"
        except Exception as h:
            return False, f"Example read failed ({type(h).__name__})"


BAGLAYICI = OrnekBaglayici()
