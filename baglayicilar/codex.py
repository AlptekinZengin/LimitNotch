"""Limit Çubuğu - Codex bağlayıcısı.

Codex'in 5 saatlik ve haftalık kullanım limitlerini aracın kendi yerel sunucusu
(`codex app-server` rate limit sorgusu) üzerinden, mevcut `yenileyici` modülünü
çağırarak okur. Giriş bilgisine veya kimlik dosyalarına dokunulmaz.
"""
import os
import sys

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

import dil  # noqa: E402
import yenileyici  # noqa: E402
from baglayicilar.taban import Baglayici, KARARLI  # noqa: E402


class CodexBaglayici(Baglayici):
    kimlik = "codex"
    ad = "Codex"
    kisa_ad = "Codex"
    renk = "#10B981"
    durum = KARARLI
    sira = 20
    okuma_yolu = "Codex'in kendi sunucusu: codex app-server, rate limit sorgusu (giriş bilgisine dokunulmaz)"
    okuma_yolu_anahtari = "yol_codex"

    def bul(self):
        try:
            return yenileyici.codex_komutu() is not None
        except Exception:
            return False

    def yenile(self, yol=None):
        try:
            return yenileyici.yenile_codex(yol)
        except Exception as h:
            return False, dil.t("codex_okunamadi_kisa", detay=type(h).__name__)


BAGLAYICI = CodexBaglayici()
