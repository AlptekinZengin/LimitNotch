"""Limit Çubuğu - Antigravity bağlayıcısı.

Antigravity'nin 5 saatlik ve haftalık kota bilgilerini aracın bu bilgisayarda
açtığı yerel kapı (`hub_*.json` + `RetrieveUserQuotaSummary`) üzerinden, mevcut
`yenileyici` modülünü çağırarak okur. Giriş bilgisine dokunulmaz.
"""
import os
import sys

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

import dil  # noqa: E402
import yenileyici  # noqa: E402
from baglayicilar.taban import Baglayici, DENEYSEL  # noqa: E402


class AntigravityBaglayici(Baglayici):
    kimlik = "antigravity"
    ad = "Antigravity"
    kisa_ad = "AGY"
    renk = "#38BDF8"
    durum = DENEYSEL
    sira = 30
    okuma_yolu = (
        "Antigravity'nin bu bilgisayarda açtığı yerel kapı "
        "(hub_*.json + RetrieveUserQuotaSummary); belgesiz, güncellemeyle bozulabilir"
    )
    okuma_yolu_anahtari = "yol_antigravity"

    def bul(self):
        try:
            if bool(yenileyici.antigravity_hub_dosyalari()):
                return True
        except Exception:
            pass
        try:
            return os.path.isdir(
                os.path.join(os.path.expanduser("~"), ".gemini", "antigravity")
            )
        except Exception:
            return False

    def yenile(self, yol=None):
        try:
            return yenileyici.yenile_antigravity(yol)
        except Exception as h:
            return False, dil.t("agy_okunamadi_kisa", detay=type(h).__name__)


BAGLAYICI = AntigravityBaglayici()
