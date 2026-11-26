"""Limit Çubuğu - bağlayıcı sözleşmesi.

Her yapay zekâ aracı `baglayicilar/` klasöründe tek bir dosyadır. Dosya, bu sınıftan
türeyen bir nesneyi modül düzeyinde `BAGLAYICI` adıyla verir:

    from baglayicilar.taban import Baglayici, KARARLI

    class ClaudeBaglayici(Baglayici):
        kimlik = "claude"
        ...
    BAGLAYICI = ClaudeBaglayici()

Kurallar (her bağlayıcı için):
- Aracın şifre / giriş anahtarı dosyası okunmaz, tarayıcı çerezine dokunulmaz.
- İnternete doğrudan istek atılmaz. Yalnız aracın kendi programı çalıştırılır, aracın
  bilgisayara yazdığı dosya okunur ya da aracın yalnız bu bilgisayarda (localhost) açtığı
  kapıya sorulur.
- `bul()` hızlıdır: alt süreç başlatmaz, ağa çıkmaz, istisna fırlatmaz.
- `yenile()` istisna fırlatmaz; başarısızsa durum.json'daki mevcut veriye dokunmaz.

Yalnızca standart kütüphane kullanır.
"""

KARARLI = "kararli"   # resmi ya da aracın kendi programı üzerinden okuma
DENEYSEL = "deneysel"  # belgesiz yol; araç güncellenince bozulabilir
DURUMLAR = (KARARLI, DENEYSEL)


class Baglayici:
    """Tüm bağlayıcıların taban sınıfı. Alt sınıf sınıf özniteliklerini doldurur."""

    kimlik = ""          # durum.json anahtarı, küçük harf ascii, ör. "claude"
    ad = ""              # görünen ad, ör. "Claude Code"
    kisa_ad = ""         # çubukta dar yer için kısa ad, ör. "AGY"; boşsa ad kullanılır
    renk = "#888888"     # kartta ve noktada kullanılan renk (#RRGGBB)
    durum = KARARLI      # KARARLI ya da DENEYSEL
    okuma_yolu = ""      # tek satır, Türkçe: limit nereden okunuyor (README ve panelde gösterilir)
    okuma_yolu_anahtari = ""  # dil.py içindeki çeviri anahtarı (isteğe bağlı)
    sira = 100           # gösterim sırası; küçük olan önce

    def bul(self):
        """Araç bu bilgisayarda kurulu görünüyor mu? -> bool. Hızlı, ağsız, alt süreçsiz."""
        return False

    def yenile(self, yol=None):
        """Limitleri canlı okuyup durum.json'a yazar -> (basarili: bool, kisa_mesaj: str).

        yol: durum.json yolu (None ise varsayılan). Asla istisna fırlatmaz.
        """
        try:
            import dil
            return False, dil.t("hata_yenileme_tanimsiz", ad=self.ad or self.kimlik)
        except Exception:
            return False, f"{self.ad or self.kimlik}: yenileme tanımlı değil"

    def gorunen_okuma_yolu(self):
        """Etkin dildeki okuma yolu açıklamasını döner."""
        if self.okuma_yolu_anahtari:
            try:
                import dil
                return dil.t(self.okuma_yolu_anahtari)
            except Exception:
                pass
        return self.okuma_yolu

    def gorunen_kisa_ad(self):
        return self.kisa_ad or self.ad or self.kimlik

    def __repr__(self):
        return f"<Baglayici {self.kimlik} ({self.durum})>"
