"""Limit Çubuğu - Claude Code bağlayıcısı.

Claude Code'un 5 saatlik ve haftalık kullanım limitlerini aracın kendi yerel
komutu (`claude -p /usage`) üzerinden, mevcut `yenileyici` modülünü çağırarak
okur. Giriş bilgisine veya kimlik dosyalarına dokunulmaz.
"""
import os
import sys

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

import dil  # noqa: E402
import yenileyici  # noqa: E402
from baglayicilar.taban import Baglayici, KARARLI  # noqa: E402


class ClaudeBaglayici(Baglayici):
    kimlik = "claude"
    ad = "Claude Code"
    kisa_ad = "Claude"
    renk = "#D97757"
    durum = KARARLI
    sira = 10
    okuma_yolu = "Claude Code'un kendi komutu: claude -p /usage (giriş bilgisine dokunulmaz)"
    okuma_yolu_anahtari = "yol_claude"

    def bul(self):
        try:
            return yenileyici.claude_komutu() is not None
        except Exception:
            return False

    def yenile(self, yol=None):
        try:
            return yenileyici.yenile_claude(yol)
        except Exception as h:
            return False, dil.t("claude_okunamadi_kisa", detay=type(h).__name__)


BAGLAYICI = ClaudeBaglayici()
