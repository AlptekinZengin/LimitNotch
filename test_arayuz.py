"""Limit Çubuğu arayüz/mantık testi.

Gerçek durum.json'a dokunmaz: LIMIT_CUBUGU_DOSYA ile test_cikti/durum.json kullanır.
Gerçek Codex/Claude'u çağırmaz: sorgular sahte fonksiyonla değiştirilir.
Üst orta Dinamik Ada çentiği, açık yatay kapsül, alt detay kartı, çift monitör geçişi,
otomatik yenilemenin kapalı olması ve tekil/toplu Yenile düğmelerini doğrular, sonra kendini kapatır.
Çalıştırma:  py -3 test_arayuz.py
"""
import importlib.util
import math
import os
import subprocess
import sys
import time
import uuid
from types import SimpleNamespace
from unittest.mock import patch

BURASI = os.path.dirname(os.path.abspath(__file__))
CIKTI = os.path.join(BURASI, "test_cikti")
os.makedirs(CIKTI, exist_ok=True)
os.environ["LIMIT_CUBUGU_DOSYA"] = os.path.join(CIKTI, "durum.json")
os.environ["LIMIT_CUBUGU_BASLANGIC_SN"] = "0.25"
os.environ["LIMIT_CUBUGU_OTOMATIK"] = "0"
os.environ["LIMIT_CUBUGU_KURULUM"] = "0"
os.environ["LIMITNOTCH_DIL"] = "tr"
sys.path.insert(0, BURASI)

import durum_ortak as ortak  # noqa: E402
import yenileyici  # noqa: E402

spec = importlib.util.spec_from_file_location("limit_cubugu", os.path.join(BURASI, "limit_cubugu.pyw"))
lc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lc)

hatalar = []


def kontrol(kosul, ad):
    print(("TAMAM " if kosul else "HATA  ") + ad)
    if not kosul:
        hatalar.append(ad)


# ---------------------------------------------------------- mantık testleri
simdi = time.time()
kontrol(lc.durum_rengi(78) == lc.YESIL and lc.durum_rengi(35) == lc.AMBER
        and lc.durum_rengi(10) == lc.KIRMIZI and lc.durum_rengi(None) == lc.GRI, "renk eşikleri")
b = {"bes_saat": {"kalan": 12, "resets_at": simdi - 5}}
kontrol(ortak.pencere_durumu(b, "bes_saat", simdi) == (100.0, simdi - 5, True), "süresi dolan pencere %100 (yenilendi)")

# #4 küçük + orta mantık korumaları
kontrol(ortak.sayi(float("nan")) is None and ortak.sayi(float("inf")) is None
        and ortak.sayi(float("-inf")) is None and ortak.sayi("NaN") is None, "durum_ortak.sayi NaN/Inf koruması")
kontrol(ortak.zaman_cevir(float("nan")) is None and ortak.zaman_cevir(float("inf")) is None
        and ortak.zaman_cevir("inf") is None, "durum_ortak.zaman_cevir NaN/Inf koruması")
kontrol(lc.geometri_metni(136, 22, -1028, -50) == "136x22+-1028+-50", "negatif koordinat geometry biçimi (Tk sol-üst eksen)")
kontrol(lc.geometri_metni(136, 22, 1212, 0) == "136x22+1212+0", "pozitif koordinat geometry biçimi")

# Antigravity kaynak etiketi (model grubu)
kontrol(lc.antigravity_etiketi("Otomatik (yenilendi)", {
    "bes_saat": {"kalan": 80, "grup": "Gemini"},
    "haftalik": {"kalan": 70, "grup": "Gemini"},
}) == "Otomatik (yenilendi) · Gemini", "antigravity_etiketi: iki grup aynı")
kontrol(lc.antigravity_etiketi("Otomatik (yenilendi)", {
    "bes_saat": {"kalan": 80, "grup": "Gemini"},
    "haftalik": {"kalan": 70, "grup": "Claude/GPT"},
}) == "Otomatik (yenilendi) · 5s Gemini / hf Claude/GPT", "antigravity_etiketi: iki grup farklı")
kontrol(lc.antigravity_etiketi("Otomatik (yenilendi)", {
    "bes_saat": {"kalan": 80, "grup": "Gemini"},
    "haftalik": {"kalan": 70},
}) == "Otomatik (yenilendi) · 5s Gemini / hf ?", "antigravity_etiketi: bir grup eksik")
kontrol(lc.antigravity_etiketi("Otomatik (yenilendi)", {
    "bes_saat": {"kalan": 80},
    "haftalik": {"kalan": 70},
}) == "Otomatik (yenilendi)", "antigravity_etiketi: grup alanı yok")
kontrol(lc.antigravity_etiketi("Otomatik (yenilendi)", None) == "Otomatik (yenilendi)",
        "antigravity_etiketi: bolum None")

# Göreli yol yazımı (boş dizin koruması)
eski_cwd = os.getcwd()
try:
    os.chdir(CIKTI)
    goreli_ok = ortak.yaz({"surum": 1, "test": True}, yol="goreli_test.json")
    kontrol(goreli_ok and os.path.exists(os.path.join(CIKTI, "goreli_test.json")), "göreli yolda os.makedirs koruması")
    # Test çıktısı saklanır; proje kuralı gereği dosya silinmez.
finally:
    os.chdir(eski_cwd)

# ---------------------------------------------------------- yenileyici (Codex ayrıştırma + sahte sorgu)
GERCEK_CEVAP = {  # `py -3 yenileyici.py codex` ile alınan gerçek biçim (codex-cli 0.166.0)
    "accountId": "x", "ordinaryUsageAllowed": True, "rateLimitResetCredits": None, "rateLimitUpsell": None,
    "rateLimits": {"primary": {"usedPercent": 37, "windowDurationMins": 300, "resetsAt": 1795624205},
                   "secondary": {"usedPercent": 31, "windowDurationMins": 10080, "resetsAt": 1796133053}},
    "rateLimitsByLimitId": None,
}
a = yenileyici.codex_ayristir(GERCEK_CEVAP)
kontrol(a["bes_saat"] == {"kalan": 63.0, "resets_at": 1795624205.0}
        and a["haftalik"] == {"kalan": 69.0, "resets_at": 1796133053.0}, "Codex gerçek cevap biçimi ayrıştırılır")
a = yenileyici.codex_ayristir({"rate_limits": {"primary": {"used_percent": 120, "resets_at": "1795624205"},
                                               "secondary": {"used_percent": 10}}})
kontrol(a["bes_saat"]["kalan"] == 0.0 and a["haftalik"]["kalan"] == 90.0 and a["haftalik"]["resets_at"] is None,
        "Codex snake_case alanlar + kalan = max(0, 100 - kullanılan)")
try:
    yenileyici.codex_ayristir({"rateLimits": {"primary": None}})
    kontrol(False, "boş Codex cevabı reddedilir")
except yenileyici.CodexHatasi:
    kontrol(True, "boş Codex cevabı reddedilir")


def sahte_codex_basarili():
    time.sleep(0.3)  # "Yenileniyor..." durumu görülebilsin
    return GERCEK_CEVAP


def sahte_codex_hatali():
    raise yenileyici.CodexHatasi("zaman aşımı (9 sn)")


def gercek_codex_yasak():
    raise AssertionError("test sırasında gerçek codex çağrılmamalı")


_GERCEK_SORGULAR = (yenileyici.codex_sorgula, yenileyici.claude_sorgula, yenileyici.antigravity_sorgula)
yenileyici.codex_sorgula = gercek_codex_yasak


def sahte_claude_basarili():
    time.sleep(0.3)
    return "Current session: 56% used\nCurrent week (all models): 9% used\n"


def gercek_claude_yasak():
    raise AssertionError("test sırasında gerçek claude çağrılmamalı")


yenileyici.claude_sorgula = gercek_claude_yasak


def sahte_antigravity_basarili():
    return {"groups": [{"displayName": "Gemini", "buckets": [
        {"window": "5h", "remainingFraction": 0.88, "resetTime": time.time() + 3600},
        {"window": "weekly", "remainingFraction": 0.7, "resetTime": time.time() + 3 * 86400}]}]}


def gercek_antigravity_yasak():
    raise AssertionError("test sırasında gerçek Antigravity çağrılmamalı")


yenileyici.antigravity_sorgula = gercek_antigravity_yasak

# ---------------------------------------------------------- örnek veri
veri = ortak.bos_durum()
veri["codex"] = {"kaynak": "elle", "guncellendi": simdi - 180,
                 "bes_saat": {"kalan": 35, "resets_at": simdi + 3 * 3600 + 20 * 60},
                 "haftalik": {"kalan": 62, "resets_at": simdi + 4 * 86400}}
veri["antigravity"] = {"kaynak": "elle", "guncellendi": simdi - 7200,
                       "bes_saat": {"kalan": 12, "resets_at": simdi - 60},
                       "haftalik": {"kalan": 14, "resets_at": simdi + 2 * 86400}}
veri["claude"] = {"kaynak": "otomatik", "guncellendi": simdi,
                  "bes_saat": {"kalan": 78, "resets_at": simdi + 8040},
                  "haftalik": {"kalan": 91, "resets_at": simdi + 300000}}
ortak.yaz(veri)

# ---------------------------------------------------------- arayüz testi
try:
    from PIL import ImageGrab  # noqa: E402
except ImportError:
    ImageGrab = None

lc.dpi_farkindaligi()
kok = lc.tk.Tk()
uyg = lc.LimitCubugu(kok, baslangic_sn=0.25)
imlec = [(10, 500)]
kok.winfo_pointerxy = lambda: imlec[0]  # gerçek fareyi taklit et


def alan(w):
    w.update()
    return (w.winfo_rootx(), w.winfo_rooty(), w.winfo_rootx() + w.winfo_width(), w.winfo_rooty() + w.winfo_height())


def foto(ad, *pencereler, pay=12):
    if ImageGrab is None:
        return
    kok.update()
    time.sleep(0.12)
    kok.update()
    a = [alan(w) for w in pencereler]
    kutu = (min(x[0] for x in a) - pay, min(x[1] for x in a) - pay,
            max(x[2] for x in a) + pay, max(x[3] for x in a) + pay)
    try:
        ImageGrab.grab(bbox=kutu, all_screens=True).save(os.path.join(CIKTI, ad))
        print("       görüntü:", ad)
    except OSError as h:
        print("       (ekran görüntüsü alınamadı:", h, "- atlandı)")


def bekle(sn):
    son = time.time() + sn
    while time.time() < son:
        kok.update()
        time.sleep(0.01)


def kontrast(a, b):
    def parlaklik(renk):
        kanallar = [int(renk[i:i+2], 16) / 255 for i in (1, 3, 5)]
        lineer = [v / 12.92 if v <= 0.04045 else ((v+0.055)/1.055)**2.4 for v in kanallar]
        return sum(v * k for v, k in zip(lineer, (0.2126, 0.7152, 0.0722)))
    x, y = sorted((parlaklik(a), parlaklik(b)))
    return (y+0.05) / (x+0.05)


def metinler_sigiyor(c, g, y):
    for oge in c.find_all():
        if c.type(oge) != "text":
            continue
        x1, y1, x2, y2 = c.bbox(oge)
        if not (0 <= x1 < x2 <= g and 0 <= y1 < y2 <= y):
            print("       taşan metin:", c.itemcget(oge, "text"), (x1, y1, x2, y2))
            return False
    return True


def adimlar():
    # 0) İlk açılış görünürlüğü: 0.25 sn boyunca açık başlayıp sonra çentiğe daralmalı
    kontrol(uyg.acik, "ilk açılışta görünür (açık) başlar")
    bekle(0.55)
    kontrol(not uyg.acik, "açılış süresi dolunca çentiğe daralır")

    # 1) Kapalı çentik: seçili (birincil) monitörün üst ortasında
    k = alan(kok)
    sol, ust, sag, alt = uyg._ekran_alani()
    print("       aktif monitör:", uyg.secili_monitor["kisa_ad"], "ekran:", (sol, ust, sag, alt), "çentik:", k)
    beklenen_x = sol + (sag - sol - uyg.centik_g) // 2
    kontrol(k[2] - k[0] == uyg.centik_g and k[3] - k[1] == uyg.centik_y, "çentik boyutları doğru")
    kontrol(k[0] == beklenen_x and k[1] == ust, "çentik seçili monitörün en üst ortasında (y = top)")
    kontrol(156 <= uyg.centik_g / uyg.olcek <= 172 and 22 <= uyg.centik_y / uyg.olcek <= 26,
            "okunur çentik boyutu ~168x24")
    kontrol(metinler_sigiyor(uyg.tuval, uyg.centik_g, uyg.centik_y), "kapalı çentikte mini özet taşmaz")
    kontrol(float(kok.attributes("-alpha")) >= 0.94, "opaklık >= 0.94")
    foto("1_centik.png", kok, pay=24)

    # 2) #4 Orta 1: Kapalı çentiğe erken tıklama -> yalnız paneli açar, detay kartı takılı kalmaz
    uyg._panel_tik(SimpleNamespace(x=int(uyg.centik_g // 2), y=int(uyg.centik_y // 2)))
    bekle(0.05)
    kontrol(uyg.acik and uyg.kart_arac is None and not uyg.kart.winfo_viewable(),
            "kapalı çentiğe erken tıklama paneli açar, kartı takılı bırakmaz")
    bekle(0.95)
    kontrol(not uyg.acik and uyg.kart_arac is None, "erken tıklamayla açılan panel dışarıdayken kapanır")

    # 3) Kısa dokunuş açmamalı, ~180 ms sonra açılmalı
    k = alan(kok)
    imlec[0] = ((k[0] + k[2]) // 2, (k[1] + k[3]) // 2)
    bekle(0.08)
    kontrol(not uyg.acik, "80 ms üzerinde kalınca açılmaz")
    bekle(0.20)
    kontrol(uyg.acik, "~180 ms sonra yatay kapsül açılır")
    bekle(0.20)  # Açılma gecikmesinden sonra 160 ms genişleme tamamlanır.
    p = alan(kok)
    kontrol(p[1] == ust and p[0] == sol + (sag - sol - uyg.panel_g) // 2, "açık kapsül üst ortada")

    # 4) Codex simgesine gel -> kart simgenin hemen altında ortalanmış açılır
    cx, cy = uyg._simge_merkez(1)
    imlec[0] = (int(p[0] + cx), int(p[1] + cy))
    bekle(0.18)
    kontrol(uyg.kart_arac == "codex" and uyg.kart.winfo_viewable(), "Codex üzerinde detay kartı açılır")
    kr = alan(uyg.kart)
    kontrol(kr[1] >= p[3], "detay kartı panelin hemen altında açılır")
    foto("2_panel_codex.png", kok, uyg.kart)

    # 5) Antigravity kartına geçiş
    cx, cy = uyg._simge_merkez(2)
    imlec[0] = (int(p[0] + cx), int(p[1] + cy))
    bekle(0.18)
    kontrol(uyg.kart_arac == "antigravity", "Antigravity kartına geçer")
    foto("3_panel_antigravity.png", kok, uyg.kart)

    # 7) Çift monitör geçişi (gerçek çoklu monitör varsa doğrudan, tek monitörse sahte 2. monitörle negatif X testi)
    monitorler = lc.monitorleri_listele(kok)
    orijinal_listele = lc.monitorleri_listele
    if len(monitorler) < 2:
        sahte = [
            monitorler[0],
            {"ad": "\\\\.\\DISPLAY_TEST", "kisa_ad": "DISPLAY_TEST", "birincil": False,
             "ekran": (-1920, 0, 0, 1080), "calisma": (-1920, 0, 0, 1040)},
        ]
        lc.monitorleri_listele = lambda _kok=None: list(sahte)
    try:
        onceki_ad = uyg.secili_monitor["kisa_ad"]
        yeni_ad = uyg.ekran_degistir()
        bekle(0.1)
        kontrol(yeni_ad != onceki_ad, f"ekran değiştirme sıradaki monitöre geçer ({onceki_ad} -> {yeni_ad})")
        kontrol(ortak.oku().get("monitor") == yeni_ad, "seçili monitör durum.json'a kaydedilir")
        p2 = alan(kok)
        s2, u2, sg2, _ = uyg._ekran_alani()
        kontrol(p2[0] == s2 + (sg2 - s2 - uyg.panel_g) // 2 and p2[1] == u2,
                "yeni monitörde üst ortada konumlanır (negatif X dahil)")
        # Birincil monitöre geri dön
        uyg.ekran_degistir()
        bekle(0.1)
    finally:
        lc.monitorleri_listele = orijinal_listele

    # 8) Dışarı çıkınca ~500 ms sonra çentiğe döner
    p = alan(kok)
    imlec[0] = ((p[0] + p[2]) // 2, (p[1] + p[3]) // 2)
    bekle(0.08)
    imlec[0] = (10, 500)
    bekle(0.25)
    kontrol(uyg.acik, "500 ms dolmadan kapanmaz")
    bekle(0.50)
    kontrol(not uyg.acik and not uyg.kart.winfo_viewable(), "dışarıda ~500 ms sonra çentiğe döner")

    # 9) Sabitle
    uyg.ac(); uyg.sabit = True
    bekle(0.75)
    kontrol(uyg.acik, "sabitliyken açık kalır")
    uyg.sabit = False

    # 10) Otomatik yenileme kapalı: dışarıdan durum.json değişse de kendiliğinden okunmaz
    ortak.guncelle("antigravity", {"kaynak": "elle", "bes_saat": {"kalan": 88, "resets_at": time.time() + 3600}})
    ortak.guncelle("claude", {"kaynak": "otomatik", "bes_saat": {"kalan": 44}})
    bekle(2.5)
    kontrol(uyg._arac_ozeti("antigravity", time.time())[0][0] != 88
            and uyg._arac_ozeti("claude", time.time())[0][0] == 78,
            "otomatik durum.json taraması yok (2.5 sn sonra eski değer)")
    kontrol(not uyg.yenileniyor and not uyg.yenileme_notu, "kendiliğinden hiçbir yenileme başlamaz")

    # 11) Toplu Yenile düğmesi (panel): üç araç birden, arka planda
    yenileyici.codex_sorgula = sahte_codex_basarili
    yenileyici.claude_sorgula = sahte_claude_basarili
    yenileyici.antigravity_sorgula = sahte_antigravity_basarili
    uyg.ac(); uyg.sabit = True
    bekle(0.22)
    (yx, yy) = uyg._dugme_konumlari()[0]
    uyg._panel_tik(SimpleNamespace(x=int(yx), y=int(yy)))
    kontrol(uyg.yenileniyor == set(uyg.araclar), "panel Yenile üç aracı birden yenilemeye başlar")
    img_y1 = uyg._son_panel_img.tobytes() if uyg._son_panel_img else b""
    kontrol(bool(img_y1) and uyg._son_panel_img.size == (uyg.panel_g, uyg.panel_y),
            "panelde 3× 'Yenileniyor...' karesi çizilir")
    bekle(0.05)
    img_y2 = uyg._son_panel_img.tobytes() if uyg._son_panel_img else b""
    kontrol(bool(img_y2) and img_y1 != img_y2,
            "yenilemede mavi tarama ve dönen simge piksel düzeyinde canlı akar")
    foto("4_panel_yenileniyor.png", kok)
    son = time.time() + 3
    while uyg.yenileniyor and time.time() < son:
        bekle(0.05)
    img_y_son = uyg._son_panel_img.tobytes() if uyg._son_panel_img else b""
    kontrol(not uyg.yenileniyor and img_y_son != img_y2, "toplu yenileme biter, durum şeridi kalkar")
    bekle(0.05)
    kontrol(uyg._son_panel_img.tobytes() == img_y_son,
            "yenileme bitince tarama ve dönüş sonlanır")
    kontrol(uyg._arac_ozeti("antigravity", time.time())[0][0] == 88
            and uyg._arac_ozeti("claude", time.time())[0][0] == 44, "Yenile sonrası Claude canlı (mock /usage), Antigravity canlı (mock sunucu) okunur")
    c = ortak.oku()["codex"]
    kontrol(c["kaynak"] == "Otomatik (yenilendi)" and c["bes_saat"]["kalan"] == 63.0
            and c["haftalik"]["kalan"] == 69.0 and c["haftalik"]["resets_at"] == 1796133053.0,
            "mock Codex başarısı durum.json'a 'Otomatik (yenilendi)' olarak yazılır")
    kontrol(uyg.yenileme_notu["codex"][1] == lc.YESIL
            and uyg.yenileme_notu["antigravity"][0] == "Antigravity limitleri yenilendi",
            "araç başına yenileme notları")

    # 12) Detay kartında tekil Yenile: yalnız o araç (mock Codex hatası -> veri korunur)
    yenileyici.codex_sorgula = sahte_codex_hatali
    onceki = ortak.oku()["codex"]
    uyg.kart_goster("codex")
    bekle(0.05)
    ya = uyg._yenile_alan
    uyg._kart_tik(SimpleNamespace(x=int((ya[0] + ya[2]) / 2), y=int((ya[1] + ya[3]) / 2)))
    kontrol(uyg.yenileniyor == {"codex"}, "kart Yenile yalnız o aracı yeniler")
    son = time.time() + 3
    while uyg.yenileniyor and time.time() < son:
        bekle(0.05)
    notu, renk = uyg.yenileme_notu["codex"]
    kontrol(notu.startswith("Codex okunamadı, mevcut veri korundu") and renk == lc.AMBER,
            "Codex hatasında kartta sade uyarı")
    kontrol(ortak.oku()["codex"] == onceki, "Codex hatasında mevcut veri silinmez/bozulmaz")
    foto("5_kart_codex_hata.png", kok, uyg.kart)

    # 13) Claude canlı okuma hatası (mock): kısa uyarı, durum.json bozulmaz
    def sahte_claude_hatali():
        raise yenileyici.ClaudeHatasi("zaman aşımı (25 sn)")
    yenileyici.claude_sorgula = sahte_claude_hatali
    veri2 = ortak.oku(); veri2.pop("claude", None); ortak.yaz(veri2)
    uyg.yenile(["claude"])
    son = time.time() + 3
    while uyg.yenileniyor and time.time() < son:
        bekle(0.05)
    kontrol(uyg.yenileme_notu["claude"][0].startswith("Claude okunamadı, mevcut veri korundu")
            and uyg.yenileme_notu["claude"][1] == lc.AMBER and "claude" not in ortak.oku(),
            "Claude canlı okuma hatasında kısa uyarı, veri bozulmaz")
    yenileyici.claude_sorgula = gercek_claude_yasak

    # 14) Görsel/animasyon regresyonları: gerçek Tk geometrisi, alfa ve 3× Pillow kareleri.
    imlec[0] = (10, 500)
    uyg.kapat()
    bekle(0.22)
    nefes1 = uyg._son_centik_img.tobytes() if uyg._son_centik_img else b""
    bekle(0.35)
    nefes2 = uyg._son_centik_img.tobytes() if uyg._son_centik_img else b""
    kontrol(bool(nefes1) and nefes1 != nefes2, "kapalı çentik vurgusu yavaşça nefes alır")
    kontrol(all(kontrast(r, lc.ARKA) >= 4.5 and kontrast(r, lc.IZ) >= 4.5
                for r in (lc.YAZI, lc.SOLUK, lc.ALT_YAZI, lc.YESIL, lc.AMBER, lc.KIRMIZI)),
            "tüm metin renkleri koyu yüzeylerde yüksek kontrastlı")
    uyg.ac()
    bekle(0.05)
    ara = alan(kok)
    kontrol(uyg.centik_g < ara[2]-ara[0] < uyg.panel_g and uyg._ada_bas is not None,
            "ada 160 ms geçişte ara genişliklerden geçer")
    kontrol(abs((ara[0]+ara[2]) / 2 - (sol+sag) / 2) <= 1, "ada geçişte de ortadan genişler")
    bekle(0.18)
    kontrol(uyg._ada_bas is None and kok.winfo_width() == uyg.panel_g, "ada açılması tam hedefte biter")
    kontrol(uyg._son_panel_img.size == (uyg.panel_g, uyg.panel_y)
            and all(k in uyg._panel_hitboxes for k in ("claude", "codex", "antigravity", "yenile", "sabit", "ekran", "cikis")),
            "3× panel görseli ve tüm etkileşim kutuları eksiksiz")
    uyg.kart_goster("codex")
    bekle(0.04)
    kart_ara = uyg._son_kart_img.tobytes() if uyg._son_kart_img else b""
    kontrol(0 < float(uyg.kart.attributes("-alpha")) < lc.OPAKLIK
            and uyg.kart.winfo_rooty() <= uyg._kart_hedef[1], "kart 130 ms içinde opaklaşır ve aşağı süzülür")
    kontrol(0 < uyg._dolum < 1 and bool(kart_ara), "iki ilerleme çubuğu ara dolumla açılır")
    bekle(0.22)
    kart_son = uyg._son_kart_img.tobytes() if uyg._son_kart_img else b""
    kontrol(uyg._dolum == 1 and uyg._dolum_bas is None and uyg._kart_bas is None
            and abs(float(uyg.kart.attributes("-alpha"))-lc.OPAKLIK) < 0.01
            and kart_ara != kart_son,
            "kart ve çubuklar hedeflerine tamamlanır")
    for arac in uyg.araclar:
        uyg.kart_goster(arac)
        bekle(0.22)
        kontrol(uyg._son_kart_img.size == (uyg.kart_g, uyg.kart_y)
                and "yenile" in uyg._kart_hitboxes
                and "yapistir" not in uyg._kart_hitboxes
                and "duzenle" not in uyg._kart_hitboxes,
                f"{arac} 3× kartı ve yalnız yenile düğme kutusu tam boyutunda")
    p = alan(kok)
    panel_once = uyg._son_panel_img.tobytes()
    cx, cy = uyg._simge_merkez(1)
    imlec[0] = (int(p[0]+cx), int(p[1]+cy))
    bekle(0.24)
    kontrol(uyg._hover_arac == "codex" and uyg._son_panel_img.tobytes() != panel_once,
            "hover edilen araç marka rengiyle vurgulanır")
    uyg.kart_goster("claude")
    bekle(0.03)
    uyg.kart_gizle()
    imlec[0] = (10, 500)
    bekle(0.22)
    kontrol(uyg.kart_arac is None and not uyg.kart.winfo_viewable()
            and uyg._kart_bas is None and uyg._dolum_bas is None,
            "erken gizlenen kartın animasyonları iptal olur, kart geri belirmez")
    uyg.kapat()
    bekle(0.05)
    kontrol(uyg.centik_g < kok.winfo_width() < uyg.panel_g, "kapanırken ada yumuşakça daralır")
    uyg.ac()  # Devam eden kapanma güvenle tersine çevrilebilir.
    bekle(0.22)
    kontrol(uyg.acik and kok.winfo_width() == uyg.panel_g, "hızlı aç/kapat geçişi son hedefte biter")

    # 15) Çentikte canlı mini özet (v5 #4)
    t_test = time.time()
    eski_durum = dict(uyg.durum)
    uyg.durum = {"surum": 1}
    kontrol(uyg._centik_ozeti(t_test) == ("LİMİT", lc.VURGU), "veri yokken çentik özeti 'LİMİT'")
    uyg.durum = {
        "surum": 1,
        "claude": {"bes_saat": {"kalan": 78, "resets_at": t_test + 3600}},
        "codex": {"bes_saat": {"kalan": 63, "resets_at": t_test + 3600}},
    }
    kontrol(uyg._centik_ozeti(t_test) == ("Codex %63", lc.YESIL), "çentik en düşük kalan aracı gösterir (Codex %63)")
    uyg.durum["claude"] = {"bes_saat": {"kalan": 0, "resets_at": t_test + 370}}
    kontrol(uyg._centik_ozeti(t_test) == ("Claude 6dk", lc.KIRMIZI),
            "limiti dolan araç çentikte kırmızı geri sayımla gösterilir (Claude 6dk)")
    uyg.kapat()
    bekle(0.22)
    kontrol(metinler_sigiyor(uyg.tuval, uyg.centik_g, uyg.centik_y), "çentik mini özeti (Claude 6dk) taşmaz")

    # 16) Yenilenince bildirim + az kaldı uyarısı (v5 #1)
    uyg.bildirim_gizle()
    uyg.durum = {
        "surum": 1,
        "claude": {"bes_saat": {"kalan": 25.0, "resets_at": t_test - 2}},
        "codex": {"bes_saat": {"kalan": 12.0, "resets_at": t_test + 3600}},
    }
    uyg._onceki_durum = {
        ("claude", "bes_saat"): (25.0, t_test - 2, False),
        ("claude", "haftalik"): (None, None, False),
        ("codex", "bes_saat"): (12.0, t_test + 3600, False),
        ("codex", "haftalik"): (None, None, False),
        ("antigravity", "bes_saat"): (None, None, False),
        ("antigravity", "haftalik"): (None, None, False),
    }
    uyg._bildirim_kontrol(t_test)
    bekle(0.05)
    kontrol(uyg._parlama_bitis > t_test and uyg.bildirim.winfo_viewable()
            and f"{lc.arac_bilgi('claude')['ad']} yenilendi" in uyg._bildirim_metin
            and uyg._bildirim_renk == lc.YESIL,
            "süre dolunca yeşil çentik parlaması + yenilendi bildirimi çıkar")

    uyg.bildirim_gizle()
    uyg._az_uyarildi.clear()
    uyg._bildirim_kontrol(t_test, az_kontrol_araclar=["codex"])
    bekle(0.05)
    kontrol(uyg.bildirim.winfo_viewable() and "Codex limiti azaldı (%12)" in uyg._bildirim_metin
            and uyg._bildirim_renk == lc.AMBER, "kalan <=%15 için amber uyarı şeridi çıkar")
    uyg.bildirim_gizle()
    uyg._bildirim_kontrol(t_test, az_kontrol_araclar=["codex"])
    kontrol(not uyg.bildirim.winfo_viewable(), "aynı düşük limit durumu tekrar tekrar uyarmaz")
    uyg.durum = eski_durum

    # 17) Global klavye kısayolu Alt + X (v5 #3)
    uyg.sabit = False
    uyg.kapat()
    bekle(0.22)
    basili = set()
    uyg._kisayol_aktif = True
    uyg._kisayol_onceki = False
    uyg._tus_basili_fn = lambda vk: vk in basili
    # Ctrl+Alt+X açmamalı
    basili.update({0x11, 0x12, 0x58})
    uyg._kisayol_kontrol()
    kontrol(not uyg.acik, "Ctrl+Alt+X paneli yanlışlıkla açmaz")
    basili.clear()
    uyg._kisayol_kontrol()
    # Alt+X açmalı, basılı tutunca tekrar kapatmamalı
    basili.update({0x12, 0x58})
    uyg._kisayol_kontrol()
    kontrol(uyg.acik, "Alt+X kapalı paneli açar")
    uyg._kisayol_kontrol()
    kontrol(uyg.acik, "Alt+X basılı tutulunca panel titreşmez")
    # Bırakıp tekrar basınca kapatmalı
    basili.clear()
    uyg._kisayol_kontrol()
    basili.update({0x12, 0x58})
    uyg._kisayol_kontrol()
    kontrol(not uyg.acik, "Alt+X açık paneli kapatır")
    basili.clear()
    uyg._kisayol_kontrol()

    # 18) Elle giriş yok: kartta yalnız Yenile hitbox'ı ve uygulamada düzenleme/yapıştırma yok
    uyg.ac(); uyg.sabit = True
    bekle(0.22)
    uyg.kart_goster("claude")
    bekle(0.22)
    kontrol("yenile" in uyg._kart_hitboxes
            and "yapistir" not in uyg._kart_hitboxes
            and "duzenle" not in uyg._kart_hitboxes,
            "açılan kartta yalnız 'yenile' hitbox'ı var, 'yapistir' ve 'duzenle' yok")
    kontrol(not hasattr(uyg, "panodan_yapistir") and not hasattr(uyg, "duzenle_ac"),
            "uygulamada panodan_yapistir ve duzenle_ac öznitelikleri yok")
    kontrol(metinler_sigiyor(uyg.kart_tuval, uyg.kart_g, uyg.kart_y), "tek düğmeli kartta metinler taşmaz")

    # 19) Otomatik arka plan yenileme bağlantısı
    eski_otomatik_acik = uyg.otomatik_acik
    eski_otomatik_bas = uyg._otomatik_baslangic
    eski_otomatik = uyg.otomatik
    eski_yenile = uyg.yenile
    eski_yenileniyor = set(uyg.yenileniyor)
    cagrilan = []
    try:
        kontrol(eski_otomatik.son_deneme("antigravity") is not None
                and eski_otomatik.hata_sayisi("antigravity") == 0
                and eski_otomatik.hata_sayisi("codex") >= 1,
                "yenile ve sonuç alımı OtomatikPlan kayıtlarını günceller")

        uyg.yenile = lambda araclar=None: (cagrilan.append(list(araclar or [])), True)[1]
        uyg.otomatik = SimpleNamespace(vadesi_gelenler=lambda araclar: ["codex"])
        uyg.yenileniyor.clear()

        # (a) Ortam "0" iken _otomatik_kontrol hiçbir şey başlatmaz
        uyg._otomatik_baslangic = time.time() - 61
        uyg._otomatik_kontrol()
        kontrol((not eski_otomatik_acik) and not cagrilan,
                "LIMIT_CUBUGU_OTOMATIK=0 iken _otomatik_kontrol hiçbir şey başlatmaz")

        # (b) otomatik_acik=True, 61 sn geçmiş ve vadeli araç varken yalnız o araç için yenile çağrılır
        uyg.otomatik_acik = True
        uyg._otomatik_baslangic = time.time() - 61
        uyg._otomatik_kontrol()
        kontrol(cagrilan == [["codex"]],
                "otomatik açık ve 61 sn dolunca yalnız vadeli araç için yenile çağrılır")

        # Birden fazla vadeli araç varken yalnız ilk araç başlatılır
        cagrilan.clear()
        uyg.otomatik = SimpleNamespace(vadesi_gelenler=lambda araclar: ["claude", "codex"])
        uyg._otomatik_kontrol()
        kontrol(cagrilan == [["claude"]],
                "birden fazla vadeli araç varken yalnız ilk araç başlatılır")

        # (c) self.yenileniyor doluyken hiçbir şey başlatmaz
        cagrilan.clear()
        uyg.yenileniyor.add("claude")
        uyg._otomatik_kontrol()
        kontrol(not cagrilan, "self.yenileniyor doluyken _otomatik_kontrol hiçbir şey başlatmaz")
        uyg.yenileniyor.clear()

        # (d) 60 sn dolmadan hiçbir şey başlatmaz
        cagrilan.clear()
        uyg._otomatik_baslangic = time.time() - 30
        uyg._otomatik_kontrol()
        kontrol(not cagrilan, "başlangıçtan 60 sn dolmadan _otomatik_kontrol hiçbir şey başlatmaz")
    finally:
        uyg.otomatik_acik = eski_otomatik_acik
        uyg._otomatik_baslangic = eski_otomatik_bas
        uyg.otomatik = eski_otomatik
        uyg.yenile = eski_yenile
        uyg.yenileniyor.clear()
        uyg.yenileniyor.update(eski_yenileniyor)

    # 20) Dinamik araç seçimi ve canlı değişim
    kontrol(uyg.araclar == ["claude", "codex", "antigravity"],
            "eski-kullanıcı verisinde başlangıç araçları ['claude', 'codex', 'antigravity']")
    eski_panel_g = uyg.panel_g
    degisti_2 = uyg.araclari_degistir(["claude", "codex"])
    bekle(0.05)
    ozet_2 = uyg._centik_ozeti(time.time())
    kontrol(degisti_2 and uyg.panel_g == eski_panel_g - uyg.simge_adim
            and "antigravity" not in uyg._panel_hitboxes
            and "claude" in uyg._panel_hitboxes and "codex" in uyg._panel_hitboxes
            and isinstance(ozet_2, tuple) and len(ozet_2) == 2,
            "araclari_degistir 2 araca inince panel_g bir simge_adim küçülür, antigravity hitbox'ı kalkar")

    degisti_4 = uyg.araclari_degistir(["claude", "codex", "antigravity", "gemini"])
    bekle(0.05)
    ozet_4 = uyg._centik_ozeti(time.time())
    kontrol(degisti_4 and uyg.panel_g == eski_panel_g + uyg.simge_adim
            and "gemini" in uyg._panel_hitboxes
            and isinstance(ozet_4, tuple) and len(ozet_4) == 2,
            "kayıt dışı araç (gemini) eklenince panel_g büyür, gemini hitbox'ı ve çentik özeti hatasız çalışır")

    eski_sec = lc.ilk_kurulum.sec
    eski_kaydet = lc.secim.secimi_kaydet
    eski_bildirim = uyg.bildirim_goster
    eski_yenile_20 = uyg.yenile
    sag_yenile_cagrilari = []
    try:
        lc.ilk_kurulum.sec = lambda ana=None, baglayicilar_listesi=None, onceki=None: ["codex"]
        uyg.yenile = lambda araclar=None: (sag_yenile_cagrilari.append(list(araclar) if araclar is not None else None), True)[1]
        uyg._sag_tik(None)
        bekle(0.05)
        kontrol(uyg.araclar == ["codex"]
                and ortak.oku().get("araclar") == ["codex"]
                and not sag_yenile_cagrilari,
                "_sag_tik seçimi uygular, durum.json'a yazar ve mevcut araç için yenile çağırmaz")

        lc.ilk_kurulum.sec = lambda ana=None, baglayicilar_listesi=None, onceki=None: None
        uyg._sag_tik(None)
        bekle(0.05)
        kontrol(uyg.araclar == ["codex"], "_sag_tik vazgeçilince (None) araç listesi değişmez")

        sec_cagri = [0]
        sec_aninda_acik = []

        def sahte_sec_yeniden(ana=None, baglayicilar_listesi=None, onceki=None):
            sec_cagri[0] += 1
            sec_aninda_acik.append(uyg._secim_acik)
            uyg._sag_tik(None)
            return None

        lc.ilk_kurulum.sec = sahte_sec_yeniden
        uyg._sag_tik(None)
        bekle(0.05)
        kontrol(sec_cagri[0] == 1 and sec_aninda_acik == [True] and not uyg._secim_acik,
                "_sag_tik yeniden girişi engeller, sec çağrısında _secim_acik True ve dönüşte False")

        yakalanan_bildirimler = []
        lc.ilk_kurulum.sec = lambda ana=None, baglayicilar_listesi=None, onceki=None: ["claude", "codex"]
        lc.secim.secimi_kaydet = lambda kimlikler: False
        uyg.bildirim_goster = lambda metin, renk=lc.YESIL, sure_sn=4.0: yakalanan_bildirimler.append((metin, renk, sure_sn))
        uyg._sag_tik(None)
        bekle(0.05)
        kontrol(len(yakalanan_bildirimler) == 1
                and "kaydedilemedi" in yakalanan_bildirimler[0][0].lower()
                and yakalanan_bildirimler[0][1] == lc.AMBER
                and uyg.araclar == ["claude", "codex"],
                "_sag_tik kaydetme başarısız olunca amber bildirim gösterir ve canlı listeyi yine günceller")
    finally:
        lc.ilk_kurulum.sec = eski_sec
        lc.secim.secimi_kaydet = eski_kaydet
        uyg.bildirim_goster = eski_bildirim
        uyg.yenile = eski_yenile_20
        uyg.araclari_degistir(["claude", "codex", "antigravity"])
        bekle(0.05)

    # 21) Copilot kaynak etiketi ("Otomatik (gh)") ve özel pencere başlıkları
    onceki_araclar_21 = list(uyg.araclar)
    orijinal_kart_gorseli = lc.gm.kart_gorseli
    yakalanan_kart = []

    def sahte_kart_gorseli(*args, **kwargs):
        yakalanan_kart.append((args, kwargs))
        return orijinal_kart_gorseli(*args, **kwargs)

    try:
        ortak.guncelle(
            "copilot",
            {
                "kaynak": "Otomatik (gh)",
                "bes_saat": {"kalan": 99.7, "resets_at": time.time() + 5 * 86400},
                "etiketler": {"bes_saat": "Sohbet · aylık"},
            },
        )
        uyg.durum = ortak.oku()
        uyg.araclari_degistir(onceki_araclar_21 + ["copilot"])
        bekle(0.05)
        lc.gm.kart_gorseli = sahte_kart_gorseli
        uyg._kart_ciz("copilot")
        kontrol(len(yakalanan_kart) >= 1, "Copilot kartı çiziminde kart_gorseli çağrılır")
        if yakalanan_kart:
            k_args, k_kwargs = yakalanan_kart[-1]
            k_etiket = k_args[4]
            kontrol(
                isinstance(k_etiket, tuple)
                and k_etiket[0].startswith("Otomatik (gh)")
                and k_etiket[1] == lc.YESIL,
                "Copilot 'Otomatik (gh)' kaynağı yeşil otomatik etiketiyle gösterilir",
            )
            kontrol(
                k_kwargs.get("bes_baslik") == "Sohbet · aylık"
                and k_kwargs.get("hft_baslik") == "Başka limit yok",
                "Copilot kartında özel bes_baslik ve eksik haftalık için 'Başka limit yok' kullanılır",
            )
    finally:
        lc.gm.kart_gorseli = orijinal_kart_gorseli
        temiz_durum = ortak.oku()
        temiz_durum.pop("copilot", None)
        ortak.yaz(temiz_durum)
        uyg.durum = ortak.oku()
        uyg.araclari_degistir(onceki_araclar_21)
        bekle(0.05)

    # 22) Paralel yenileme: yavaş araç hızlı aracı bekletmez
    eski_yenile_fn = uyg.yenile_fn

    def sahte_paralel_yenile(kimlik):
        if kimlik == "yavas":
            time.sleep(1.5)
            return (True, "ok")
        if kimlik == "hizli":
            return (True, "ok")
        return (False, "beklenmeyen")

    try:
        uyg.yenile_fn = sahte_paralel_yenile
        uyg.yenile(["yavas", "hizli"])
        bas = time.time()
        while "hizli" in uyg.yenileniyor and time.time() < bas + 0.5:
            bekle(0.05)
        kontrol("hizli" not in uyg.yenileniyor and "yavas" in uyg.yenileniyor,
                "paralel yenilemede hızlı araç 0.5 sn içinde biter, yavaş hâlâ yenileniyor olur")
        while ("hizli" in uyg.yenileniyor or "yavas" in uyg.yenileniyor) and time.time() < bas + 2.5:
            bekle(0.05)
        kontrol("hizli" not in uyg.yenileniyor and "yavas" not in uyg.yenileniyor,
                "paralel yenilemede 2.5 sn içinde iki araç da biter")
    finally:
        uyg.yenile_fn = eski_yenile_fn

    # 23) Antigravity canlı süreç izleme (_antigravity_izle) ve kartta diger_gruplar satırı
    eski_ag_otomatik = uyg.otomatik_acik
    eski_ag_yenile = uyg.yenile
    eski_ag_yenileniyor = set(uyg.yenileniyor)
    eski_ag_araclar = list(uyg.araclar)
    eski_ag_pid = uyg._ag_son_pid
    eski_ag_kontrol = uyg._ag_son_kontrol
    eski_ag_okuma = uyg._ag_son_okuma
    eski_pid_fn_var = hasattr(yenileyici, "antigravity_canli_pid")
    eski_pid_fn = getattr(yenileyici, "antigravity_canli_pid", None)
    eski_ag_durum = dict(uyg.durum)
    eski_ag_notlar = dict(uyg.yenileme_notu)
    eski_ag_kart_gorseli = lc.gm.kart_gorseli
    try:
        ag_cagrilan = []
        pid_deger = [1234]
        pid_cagri = [0]

        def sahte_ag_pid():
            pid_cagri[0] += 1
            return pid_deger[0]

        yenileyici.antigravity_canli_pid = sahte_ag_pid
        uyg.yenile = lambda araclar=None: (ag_cagrilan.append(list(araclar or [])), True)[1]
        uyg.yenileniyor.clear()
        uyg.otomatik_acik = True
        uyg._ag_son_pid = None
        uyg._ag_son_kontrol = 0.0
        uyg._ag_son_okuma = 0.0

        t = 10000.0
        uyg._antigravity_izle(simdi=t)
        kontrol(ag_cagrilan == [["antigravity"]],
                "_antigravity_izle yeni pid (1234) görünce yenile(['antigravity']) çağırır")

        onceki_cagri_sayisi = pid_cagri[0]
        ag_cagrilan.clear()
        uyg._antigravity_izle(simdi=t + 2)
        kontrol(not ag_cagrilan and pid_cagri[0] == onceki_cagri_sayisi,
                "_antigravity_izle 5 sn dolmadan (t+2) kontrol etmez")

        ag_cagrilan.clear()
        uyg._antigravity_izle(simdi=t + 10)
        kontrol(not ag_cagrilan and pid_cagri[0] == onceki_cagri_sayisi + 1,
                "_antigravity_izle aynı pid ile t+10'da yeniden yenile çağırmaz")

        ag_cagrilan.clear()
        uyg._antigravity_izle(simdi=t + 70)
        kontrol(ag_cagrilan == [["antigravity"]],
                "_antigravity_izle aynı pid ile 60 sn dolunca (t+70) yenile çağırır")

        ag_cagrilan.clear()
        pid_deger[0] = 5678
        uyg._antigravity_izle(simdi=t + 76)
        kontrol(ag_cagrilan == [["antigravity"]],
                "_antigravity_izle pid 5678'e değişince hemen yenile çağırır")

        ag_cagrilan.clear()
        pid_deger[0] = None
        uyg._antigravity_izle(simdi=t + 82)
        kontrol(not ag_cagrilan and uyg._ag_son_pid is None,
                "_antigravity_izle pid None iken yenile çağırmaz")

        ag_cagrilan.clear()
        pid_deger[0] = 9999
        uyg.otomatik_acik = False
        uyg._antigravity_izle(simdi=t + 150)
        kontrol(not ag_cagrilan,
                "_antigravity_izle otomatik kapalıyken hiç yenile çağırmaz")

        ag_cagrilan.clear()
        uyg.otomatik_acik = True
        uyg.araclar = [a for a in eski_ag_araclar if a != "antigravity"]
        uyg._antigravity_izle(simdi=t + 220)
        kontrol(not ag_cagrilan,
                "_antigravity_izle 'antigravity' listede değilken yenile çağırmaz")
        uyg.araclar = list(eski_ag_araclar)

        yakalanan_ag_kart = []

        def sahte_ag_kart_gorseli(*args, **kwargs):
            yakalanan_ag_kart.append((args, kwargs))
            return eski_ag_kart_gorseli(*args, **kwargs)

        ag_bolum = dict(uyg.durum.get("antigravity") or {})
        ag_bolum["diger_gruplar"] = {"Claude/GPT": {"bes_saat": 13.6, "haftalik": 56.8}}
        uyg.durum = dict(uyg.durum)
        uyg.durum["antigravity"] = ag_bolum
        uyg.yenileme_notu.pop("antigravity", None)
        lc.gm.kart_gorseli = sahte_ag_kart_gorseli
        uyg._kart_ciz("antigravity")
        kontrol(
            bool(yakalanan_ag_kart)
            and "Claude/GPT: 5 saatlik %14 · haftalık %57" in yakalanan_ag_kart[-1][1].get("not_metni", "")
            and yakalanan_ag_kart[-1][1].get("not_renk") == lc.SOLUK,
            "Antigravity kartında yenileme notu boşken diger_gruplar SOLUK not satırında gösterilir",
        )

        uyg.yenileme_notu["antigravity"] = ("Yenileniyor...", lc.SOLUK)
        uyg._kart_ciz("antigravity")
        kontrol(
            yakalanan_ag_kart[-1][1].get("not_metni") == "Yenileniyor...",
            "Antigravity kartında yenileme notu varsa diger_gruplar yerine öncelikli kalır",
        )
    finally:
        lc.gm.kart_gorseli = eski_ag_kart_gorseli
        if eski_pid_fn_var:
            yenileyici.antigravity_canli_pid = eski_pid_fn
        elif hasattr(yenileyici, "antigravity_canli_pid"):
            delattr(yenileyici, "antigravity_canli_pid")
        uyg.otomatik_acik = eski_ag_otomatik
        uyg.yenile = eski_ag_yenile
        uyg.yenileniyor.clear()
        uyg.yenileniyor.update(eski_ag_yenileniyor)
        uyg.araclar = eski_ag_araclar
        uyg._ag_son_pid = eski_ag_pid
        uyg._ag_son_kontrol = eski_ag_kontrol
        uyg._ag_son_okuma = eski_ag_okuma
        uyg.durum = eski_ag_durum
        uyg.yenileme_notu = eski_ag_notlar

    # Gerçek ikinci süreç -> izole Windows event -> çalışan Tk paneli.
    with patch.dict(os.environ, {"LIMIT_CUBUGU_ORNEK_ADI": "LimitCubuguArayuzTest_" + uuid.uuid4().hex}):
        try:
            kontrol(lc.tek_ornek(), "arayüz testi izole tek örnek sahibi")
            imlec[0] = (-100000, -100000)
            uyg.sabit = False
            uyg.kapat()
            bekle(0.25)
            kok.withdraw()
            for tekrar in range(2):
                sonuc = subprocess.run([sys.executable, os.path.join(BURASI, "limit_cubugu.pyw")],
                                       timeout=15, capture_output=True)
                kontrol(sonuc.returncode == 0, "ikinci başlatma temizce çıkar")
                bekle(0.30)
                kontrol(uyg.acik and kok.winfo_viewable(), "ikinci başlatma mevcut paneli açar/görünür tutar")
                kontrol(bool(kok.attributes("-topmost")), "sinyalle açılan panel en üstte")
                kontrol(alan(kok)[2] - alan(kok)[0] == uyg.panel_g, "sinyal sonrası tam panel boyutu")
            bekle(0.65)
            kontrol(uyg.acik, "sinyal sonrası imleç dışarıdayken panel hemen kapanmaz")
        finally:
            lc.tek_ornek_temizle()
    uyg.sabit = False
    kok.destroy()


def guvenli_adimlar():
    try:
        adimlar()
    except Exception as h:
        import traceback
        traceback.print_exc()
        hatalar.append(f"istisna: {h}")
        kok.destroy()


kok.after(120, guvenli_adimlar)
kok.mainloop()
# discover aynı süreçte başka testleri de çalıştırır: gerçek sorgu fonksiyonlarını geri koy
yenileyici.codex_sorgula, yenileyici.claude_sorgula, yenileyici.antigravity_sorgula = _GERCEK_SORGULAR
print()
print("SONUÇ:", "BAŞARILI" if not hatalar else f"{len(hatalar)} HATA: {hatalar}")
if hatalar:  # başarıda çıkış yapma: unittest discover modülü içe aktarabilsin
    sys.exit(1)
