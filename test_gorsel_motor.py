"""gorsel_motor.py birim testleri, performans kontrolü ve 4 önizleme PNG üretimi."""
import inspect
import math
import os
import sys
import time
import unittest

from PIL import Image, ImageChops, ImageDraw

os.environ["LIMITNOTCH_DIL"] = "tr"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gorsel_motor as gm  # noqa: E402

CIKTI_DIZIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_cikti")


def _kutu_gecerli_mi(kutu, w, h):
    x1, y1, x2, y2 = kutu
    return 0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h


def _kutular_cakismiyor_mu(kutular):
    liste = list(kutular.items())
    for i in range(len(liste)):
        ad1, (ax1, ay1, ax2, ay2) = liste[i]
        for j in range(i + 1, len(liste)):
            ad2, (bx1, by1, bx2, by2) = liste[j]
            if not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1):
                return False, f"{ad1} ve {ad2} çakışıyor: {(ax1, ay1, ax2, ay2)} vs {(bx1, by1, bx2, by2)}"
    return True, ""


class TestGorselMotor(unittest.TestCase):
    def test_truetype_font_yuklendi(self):
        yol = gm._font_yolu_bul("semibold")
        self.assertIsNotNone(yol, "Windows Segoe UI TrueType fontu bulunamadı")
        self.assertTrue(os.path.isfile(yol))

    def test_centik_boyut_ve_turkce(self):
        img = gm.centik_gorseli(
            168,
            24,
            [gm.YESIL, gm.AMBER, gm.KIRMIZI],
            "Çalışma %85 · ĞŞİÖÜ",
            gm.VURGU,
            nefes=0.75,
        )
        self.assertEqual(img.size, (168, 24))
        self.assertEqual(img.mode, "RGBA")
        # Üst kenar dolu, alt köşeler şeffaf (yuvarlatılmış)
        self.assertGreater(img.getpixel((84, 0))[3], 200)
        self.assertEqual(img.getpixel((0, 23))[3], 0)
        self.assertEqual(img.getpixel((167, 23))[3], 0)

    def test_centik_uzun_metin_tasma_yok(self):
        img = gm.centik_gorseli(
            168,
            24,
            [gm.YESIL, gm.YESIL, gm.YESIL],
            "Çok uzun bir Türkçe özet metni kesinlikle taşmamalı ğüşiöç",
            gm.YESIL,
            nefes=1.0,
            tarama_faz=0.35,
        )
        self.assertEqual(img.size, (168, 24))

    def test_centik_imza_ve_geriye_uyumluluk(self):
        sig = inspect.signature(gm.centik_gorseli)
        self.assertEqual(
            list(sig.parameters.keys()),
            [
                "w",
                "h",
                "noktalar",
                "metin",
                "vurgu_renk",
                "nefes",
                "tarama_faz",
                "aktif_nokta",
                "onceki_metin",
                "gecis_t",
            ],
        )
        self.assertIsNone(sig.parameters["aktif_nokta"].default)
        self.assertIsNone(sig.parameters["onceki_metin"].default)
        self.assertEqual(sig.parameters["gecis_t"].default, 1.0)

        img_eski = gm.centik_gorseli(
            168, 24, [gm.YESIL, gm.AMBER, gm.YESIL], "Claude %82", gm.YESIL, nefes=0.6
        )
        img_varsayilan = gm.centik_gorseli(
            168,
            24,
            [gm.YESIL, gm.AMBER, gm.YESIL],
            "Claude %82",
            gm.YESIL,
            nefes=0.6,
            tarama_faz=None,
            aktif_nokta=None,
            onceki_metin=None,
            gecis_t=1.0,
        )
        self.assertEqual(img_eski.tobytes(), img_varsayilan.tobytes())

    def test_centik_aktif_nokta_gorsel_fark(self):
        noktalar = [gm.YESIL, gm.AMBER, gm.YESIL]
        img_none = gm.centik_gorseli(168, 24, noktalar, "Claude %82", gm.YESIL, nefes=0.6, aktif_nokta=None)
        img_0 = gm.centik_gorseli(168, 24, noktalar, "Claude %82", gm.YESIL, nefes=0.6, aktif_nokta=0)
        img_1 = gm.centik_gorseli(168, 24, noktalar, "Claude %82", gm.YESIL, nefes=0.6, aktif_nokta=1)
        img_2 = gm.centik_gorseli(168, 24, noktalar, "Claude %82", gm.YESIL, nefes=0.6, aktif_nokta=2)

        for idx_a, a in (("none", img_none), ("0", img_0), ("1", img_1), ("2", img_2)):
            for idx_b, b in (("none", img_none), ("0", img_0), ("1", img_1), ("2", img_2)):
                if idx_a < idx_b:
                    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
                    self.assertIsNotNone(diff.getbbox(), f"aktif_nokta={idx_a} ve {idx_b} aynı çıktı")

        # Aktif nokta kendi merkezinde pasif hâlinden daha parlak olmalı
        def _parlaklik(img, x, y):
            r, g, b, _ = img.getpixel((x, y))
            return r + g + b

        # 3 nokta merkezleri (~16, ~26.5 -> 27, ~37), y ~ 11
        self.assertGreater(_parlaklik(img_0, 16, 11), _parlaklik(img_1, 16, 11))
        self.assertGreater(_parlaklik(img_1, 27, 11), _parlaklik(img_0, 27, 11))
        self.assertGreater(_parlaklik(img_2, 37, 11), _parlaklik(img_0, 37, 11))

    def test_centik_metin_gecis_crossfade(self):
        noktalar = [gm.YESIL, gm.AMBER, gm.YESIL]
        img_eski_statik = gm.centik_gorseli(168, 24, noktalar, "Claude %82", gm.YESIL, nefes=0.6, aktif_nokta=0)
        img_yeni_statik = gm.centik_gorseli(168, 24, noktalar, "Codex %31", gm.AMBER, nefes=0.6, aktif_nokta=1)

        img_t0 = gm.centik_gorseli(
            168, 24, noktalar, "Codex %31", gm.YESIL, nefes=0.6, aktif_nokta=0,
            onceki_metin="Claude %82", gecis_t=0.0,
        )
        img_t05 = gm.centik_gorseli(
            168, 24, noktalar, "Codex %31", "#98C95F", nefes=0.6, aktif_nokta=1,
            onceki_metin="Claude %82", gecis_t=0.5,
        )
        img_t1 = gm.centik_gorseli(
            168, 24, noktalar, "Codex %31", gm.AMBER, nefes=0.6, aktif_nokta=1,
            onceki_metin="Claude %82", gecis_t=1.0,
        )

        # t=0.0 önceki metinle, t=1.0 yeni metinle bire bir eşleşmeli
        self.assertEqual(img_t0.tobytes(), img_eski_statik.tobytes())
        self.assertEqual(img_t1.tobytes(), img_yeni_statik.tobytes())

        # t=0.5 hem t=0.0 hem t=1.0'dan farklı ara kare olmalı ve metin alanı tam opak kalmalı
        metin_bolgesi = (52, 2, 160, 20)
        diff_05_0 = ImageChops.difference(
            img_t05.crop(metin_bolgesi).convert("RGB"),
            img_t0.crop(metin_bolgesi).convert("RGB"),
        )
        diff_05_1 = ImageChops.difference(
            img_t05.crop(metin_bolgesi).convert("RGB"),
            img_t1.crop(metin_bolgesi).convert("RGB"),
        )
        self.assertIsNotNone(diff_05_0.getbbox())
        self.assertIsNotNone(diff_05_1.getbbox())
        for x in range(56, 152, 8):
            self.assertEqual(img_t05.getpixel((x, 11))[3], 255, f"Metin alanında şeffaf delik: x={x}")

    def test_centik_harmanlanmis_vurgu_renk(self):
        noktalar = [gm.YESIL, gm.AMBER, gm.YESIL]
        img_yesil = gm.centik_gorseli(168, 24, noktalar, "Claude %82", gm.YESIL, nefes=0.8)
        img_ara = gm.centik_gorseli(168, 24, noktalar, "Codex %31", "#98c95f", nefes=0.8)
        img_amber = gm.centik_gorseli(168, 24, noktalar, "Codex %31", gm.AMBER, nefes=0.8)

        # Alt vurgu çizgisi pikseli (x=84, y=22) her üç renkte farklı ve ara renk ortada olmalı
        py = img_yesil.getpixel((84, 22))
        pm = img_ara.getpixel((84, 22))
        pa = img_amber.getpixel((84, 22))
        self.assertNotEqual(py, pm)
        self.assertNotEqual(pm, pa)
        self.assertGreater(pm[0], py[0])
        self.assertLess(pm[0], pa[0])

    def test_centik_gecersiz_parametre_guvenligi(self):
        noktalar = [gm.YESIL, gm.AMBER, gm.KIRMIZI]
        img_baz = gm.centik_gorseli(168, 24, noktalar, "AGY %94", gm.YESIL, nefes=0.5)

        # Sınır dışı veya geçersiz aktif_nokta hata vermeden varsayılan görünüme düşmeli
        for gecersiz_idx in (-1, -99, 3, 100, True, False, "abc"):
            with self.subTest(aktif_nokta=gecersiz_idx):
                img = gm.centik_gorseli(
                    168, 24, noktalar, "AGY %94", gm.YESIL, nefes=0.5, aktif_nokta=gecersiz_idx
                )
                self.assertEqual(img.size, (168, 24))
                self.assertEqual(img.tobytes(), img_baz.tobytes())

        # Sınır dışı veya NaN/Inf gecis_t güvenli kırpılmalı
        img_onceki = gm.centik_gorseli(168, 24, noktalar, "Claude %82", gm.YESIL, nefes=0.5)
        for t_alt in (-0.5, -10.0):
            with self.subTest(gecis_t=t_alt):
                img = gm.centik_gorseli(
                    168, 24, noktalar, "AGY %94", gm.YESIL, nefes=0.5,
                    onceki_metin="Claude %82", gecis_t=t_alt,
                )
                self.assertEqual(img.tobytes(), img_onceki.tobytes())

        for t_ust in (1.5, 99.0, float("nan"), float("inf"), float("-inf")):
            with self.subTest(gecis_t=t_ust):
                img = gm.centik_gorseli(
                    168, 24, noktalar, "AGY %94", gm.YESIL, nefes=0.5,
                    onceki_metin="Claude %82", gecis_t=t_ust,
                )
                self.assertEqual(img.tobytes(), img_baz.tobytes())

        # Boş nokta listesi + bozuk hex renk + boş metin de hatasız çizilmeli
        img_bos = gm.centik_gorseli(
            168, 24, [], "", vurgu_renk="#ZZZZZZ", nefes=float("nan"),
            aktif_nokta=0, onceki_metin="", gecis_t=0.5,
        )
        self.assertEqual(img_bos.size, (168, 24))
        self.assertEqual(img_bos.mode, "RGBA")

    def test_panel_hitboxes_ve_durumlar(self):
        araclar = {
            "claude": {"bes_kalan": 82.0, "hft_kalan": 64.0},
            "codex": {"bes_kalan": 34.0, "hft_kalan": 71.0},
            "antigravity": {"bes_kalan": 12.0, "hft_kalan": 100.0},
        }
        w, h = 430, 86
        img, hitboxes = gm.panel_gorseli(
            w,
            h,
            araclar,
            secili_arac="claude",
            hover_arac="codex",
            hover_dugme="sabit",
            sabit=True,
            yenileniyor=False,
            tarama_faz=0.0,
            donus_aci=0.0,
            durum_metni="",
        )
        self.assertEqual(img.size, (w, h))
        self.assertEqual(img.mode, "RGBA")
        beklenen = {"claude", "codex", "antigravity", "yenile", "sabit", "ekran", "cikis"}
        self.assertEqual(set(hitboxes.keys()), beklenen)
        for ad, kutu in hitboxes.items():
            self.assertTrue(_kutu_gecerli_mi(kutu, w, h), f"Geçersiz kutu {ad}: {kutu}")
        ok, hata = _kutular_cakismiyor_mu(hitboxes)
        self.assertTrue(ok, hata)

    def test_panel_yenileniyor_ve_bos_veri(self):
        araclar = {
            "claude": {"bes_kalan": None, "hft_kalan": None},
            "codex": {"bes_kalan": float("nan"), "hft_kalan": float("inf")},
            "antigravity": {"bes_kalan": 0.0, "hft_kalan": 50.0},
        }
        img, hitboxes = gm.panel_gorseli(
            430,
            86,
            araclar,
            secili_arac=None,
            hover_arac=None,
            hover_dugme="cikis",
            sabit=False,
            yenileniyor={"claude"},
            tarama_faz=0.42,
            donus_aci=135.0,
            durum_metni="Yenileniyor...",
        )
        self.assertEqual(img.size, (430, 86))
        self.assertEqual(len(hitboxes), 7)

    def test_panel_varsayilan_araclar_parametresiz(self):
        araclar_durum = {
            "claude": {"bes_kalan": 75.0, "hft_kalan": 50.0},
            "codex": {"bes_kalan": 60.0, "hft_kalan": 80.0},
            "antigravity": {"bes_kalan": 25.0, "hft_kalan": 90.0},
        }
        w, h = 430, 86
        img, hitboxes = gm.panel_gorseli(w, h, araclar_durum)
        self.assertEqual(img.size, (w, h))
        beklenen = {"claude", "codex", "antigravity", "yenile", "sabit", "ekran", "cikis"}
        self.assertEqual(set(hitboxes.keys()), beklenen)

    def test_panel_bes_arac_standart_ve_genis(self):
        arac_listesi = ["claude", "codex", "antigravity", "gemini", "copilot"]
        araclar_durum = {
            "claude": {"bes_kalan": 82.0, "hft_kalan": 64.0},
            "codex": {"bes_kalan": 34.0, "hft_kalan": 71.0},
            "antigravity": {"bes_kalan": 12.0, "hft_kalan": 100.0},
            "gemini": {"bes_kalan": 40, "hft_kalan": 80, "renk": "#4285F4", "ad": "Gemini CLI"},
            "copilot": {"bes_kalan": None, "hft_kalan": None},
        }
        w3, h = 430, 86
        w5 = int(w3 * (12 + 76 * 5 + 12 + 42 * 4 + 10) / (12 + 76 * 3 + 12 + 42 * 4 + 10))
        for w in (w3, w5):
            with self.subTest(w=w):
                img, hitboxes = gm.panel_gorseli(w, h, araclar_durum, araclar=arac_listesi)
                self.assertEqual(img.size, (w, h))
                self.assertEqual(img.mode, "RGBA")
                for arac in arac_listesi:
                    self.assertIn(arac, hitboxes)
                for ad, kutu in hitboxes.items():
                    self.assertTrue(_kutu_gecerli_mi(kutu, w, h), f"Geçersiz kutu {ad}: {kutu}")
                arac_kutulari = {arac: hitboxes[arac] for arac in arac_listesi}
                ok, hata = _kutular_cakismiyor_mu(arac_kutulari)
                self.assertTrue(ok, hata)
                ok_tum, hata_tum = _kutular_cakismiyor_mu(hitboxes)
                self.assertTrue(ok_tum, hata_tum)
                for i in range(len(arac_listesi) - 1):
                    self.assertLess(
                        hitboxes[arac_listesi[i]][0],
                        hitboxes[arac_listesi[i + 1]][0],
                        f"Soldan sağa sıra bozuk: {arac_listesi[i]} vs {arac_listesi[i + 1]}",
                    )

    def test_panel_bos_araclar_varsayilana_duser(self):
        araclar_durum = {
            "claude": {"bes_kalan": 50.0, "hft_kalan": 50.0},
            "codex": {"bes_kalan": 50.0, "hft_kalan": 50.0},
            "antigravity": {"bes_kalan": 50.0, "hft_kalan": 50.0},
        }
        w, h = 430, 86
        img, hitboxes = gm.panel_gorseli(w, h, araclar_durum, araclar=[])
        self.assertEqual(img.size, (w, h))
        for arac in ("claude", "codex", "antigravity"):
            self.assertIn(arac, hitboxes)
        self.assertEqual(
            set(hitboxes.keys()),
            {"claude", "codex", "antigravity", "yenile", "sabit", "ekran", "cikis"},
        )

    def test_panel_tek_arac_genislik_278(self):
        araclar_durum = {
            "gemini": {"bes_kalan": 65.0, "hft_kalan": 80.0, "renk": "#4285F4"},
        }
        w, h = 278, 86
        img, hitboxes = gm.panel_gorseli(w, h, araclar_durum, araclar=["gemini"])
        self.assertEqual(img.size, (w, h))
        self.assertEqual(img.mode, "RGBA")
        self.assertEqual(set(hitboxes.keys()), {"gemini", "yenile", "sabit", "ekran", "cikis"})
        for ad, kutu in hitboxes.items():
            self.assertTrue(_kutu_gecerli_mi(kutu, w, h), f"Geçersiz kutu {ad}: {kutu}")
        ok, hata = _kutular_cakismiyor_mu(hitboxes)
        self.assertTrue(ok, hata)

    def test_marka_simgesi_genel_ve_ozel_harf(self):
        tuval1 = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d1 = ImageDraw.Draw(tuval1)
        gm._marka_simgesi_ciz(d1, "gemini", 32.0, 32.0, 20.0, marka_renk="#4285F4")
        self.assertIsNotNone(tuval1.getbbox())

        tuval2 = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(tuval2)
        gm._marka_simgesi_ciz(d2, "gemini", 32.0, 32.0, 20.0, marka_renk="#4285F4", harf="X")
        self.assertIsNotNone(tuval2.getbbox())

    def test_marka_simgesi_copilot(self):
        tuval = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(tuval)
        gm._marka_simgesi_ciz(d, "copilot", 32.0, 32.0, 20.0, marka_renk="#A78BFA")
        self.assertIsNotNone(tuval.getbbox())

    def test_arac_durumu_coz_renk_onceligi(self):
        durum = {
            "gemini": {"bes_kalan": 40, "hft_kalan": 80, "renk": "#4285F4"},
            "copilot": {"bes_kalan": None, "hft_kalan": None, "renk": "gecersiz"},
            "claude": {"bes_kalan": 70, "hft_kalan": 60, "renk": "#123"},
        }
        self.assertEqual(gm._arac_durumu_coz(durum, "gemini")[2], "#4285F4")
        self.assertEqual(gm._arac_durumu_coz(durum, "copilot")[2], gm.VURGU)
        self.assertEqual(gm._arac_durumu_coz(durum, "claude")[2], gm.ARAC_BILGI["claude"]["renk"])

    def test_kart_hitboxes_ve_formatlar(self):
        w, h = 368, 356
        simdi = time.time()
        img, hitboxes = gm.kart_gorseli(
            w,
            h,
            arac_ad="Claude",
            marka_renk="#D97757",
            kaynak_etiketi=("Otomatik (statusLine)", gm.YESIL),
            bes_durum=(78.0, simdi + 2 * 3600 + 15 * 60, False),
            hft_durum={"kalan": 42.0, "alt_metin": "Yenilenme: Paz 11:00 (3 g 4 sa sonra)"},
            bes_anim_oran=0.78,
            hft_anim_oran=0.42,
            son_guncelleme="2 dk önce",
            not_metni="Limitler yenilendi: 5 saatlik %78, haftalık %42 — Türkçe karakter testi: İıŞşĞğÜüÖöÇç",
            not_renk=gm.YESIL,
            hover_dugme="yenile",
            yenileniyor=False,
        )
        self.assertEqual(img.size, (w, h))
        self.assertEqual(img.mode, "RGBA")
        self.assertEqual(set(hitboxes.keys()), {"yenile"})
        for ad, kutu in hitboxes.items():
            self.assertTrue(_kutu_gecerli_mi(kutu, w, h), f"Geçersiz kart kutusu {ad}: {kutu}")

    def test_kart_yenileniyor_ve_veri_yok(self):
        img, hitboxes = gm.kart_gorseli(
            368,
            356,
            arac_ad="Antigravity",
            marka_renk="#38BDF8",
            kaynak_etiketi="Veri yok",
            bes_durum=(None, None, False),
            hft_durum=(100.0, None, True),
            bes_anim_oran=None,
            hft_anim_oran=1.0,
            son_guncelleme="hiç",
            not_metni="Yenileniyor...",
            not_renk=gm.IKINCIL,
            hover_dugme=None,
            yenileniyor=True,
            donus_aci=90.0,
            tarama_faz=0.6,
        )
        self.assertEqual(img.size, (368, 356))
        self.assertEqual(set(hitboxes.keys()), {"yenile"})
        self.assertTrue(_kutu_gecerli_mi(hitboxes["yenile"], 368, 356))

    def test_kart_ozel_ve_varsayilan_basliklar(self):
        w, h = 368, 356
        simdi = time.time()
        img_ozel, hitboxes_ozel = gm.kart_gorseli(
            w,
            h,
            arac_ad="Copilot",
            marka_renk="#6E40C9",
            kaynak_etiketi=("Otomatik (gh)", gm.YESIL),
            bes_durum=(99.7, simdi + 5 * 86400, False),
            hft_durum=(85.0, simdi + 5 * 86400, False),
            bes_anim_oran=0.997,
            hft_anim_oran=0.85,
            son_guncelleme="az önce",
            bes_baslik="Sohbet · aylık",
            hft_baslik="Kod tamamlama · aylık",
        )
        self.assertEqual(img_ozel.size, (w, h))
        self.assertEqual(img_ozel.mode, "RGBA")
        self.assertEqual(set(hitboxes_ozel.keys()), {"yenile"})

        img_varsayilan, hitboxes_varsayilan = gm.kart_gorseli(
            w,
            h,
            arac_ad="Copilot",
            marka_renk="#6E40C9",
            kaynak_etiketi=("Otomatik (gh)", gm.YESIL),
            bes_durum=(99.7, simdi + 5 * 86400, False),
            hft_durum=(85.0, simdi + 5 * 86400, False),
            bes_anim_oran=0.997,
            hft_anim_oran=0.85,
            son_guncelleme="az önce",
        )
        self.assertEqual(img_varsayilan.size, (w, h))
        self.assertEqual(img_varsayilan.mode, "RGBA")
        self.assertEqual(set(hitboxes_varsayilan.keys()), {"yenile"})

    def test_toast_ve_gecis(self):
        metin = "✓ Claude yenilendi! (%100)"
        tw, th = gm.toast_boyut_hesapla(metin, olcek=1.0)
        img = gm.toast_gorseli(tw, th, metin, gm.YESIL)
        self.assertEqual(img.size, (tw, th))
        self.assertEqual(img.mode, "RGBA")
        # İç zemin tam opak olmalı (saydam delik olmamalı)
        self.assertEqual(img.getpixel((tw // 2, th // 2))[3], 255)

        uyari = gm.toast_gorseli(260, 34, "⚠ Codex limiti azaldı (%12)", gm.AMBER)
        self.assertEqual(uyari.size, (260, 34))
        self.assertEqual(uyari.getpixel((130, 17))[3], 255)

        gecis = gm.gecis_gorseli(260, 50, gm.VURGU)
        self.assertEqual(gecis.size, (260, 50))

    def test_performans_hizi(self):
        araclar = {
            "claude": {"bes_kalan": 78.0, "hft_kalan": 62.0},
            "codex": {"bes_kalan": 35.0, "hft_kalan": 80.0},
            "antigravity": {"bes_kalan": 14.0, "hft_kalan": 95.0},
        }
        # Önbellek ısındırma
        gm.centik_gorseli(168, 24, [gm.YESIL, gm.AMBER, gm.KIRMIZI], "AGY %14", gm.KIRMIZI, nefes=0.5)
        gm.panel_gorseli(430, 86, araclar, "claude", None, None, False, False, 0.0, 0.0, "")
        gm.kart_gorseli(
            368, 356, "Claude", "#D97757", "Otomatik (statusLine)",
            {"kalan": 78.0, "alt_metin": "2 sa 15 dk sonra yenilenir"},
            {"kalan": 62.0, "alt_metin": "Yenilenme: Paz 11:00"},
            0.78, 0.62, "2 dk önce", "", None, None, False,
        )
        gm.toast_gorseli(240, 34, "✓ Claude yenilendi! (%100)", gm.YESIL)

        n = 10
        t0 = time.perf_counter()
        for i in range(n):
            gm.centik_gorseli(168, 24, [gm.YESIL, gm.AMBER, gm.KIRMIZI], "AGY %14", gm.KIRMIZI, nefes=i / n)
        centik_ms = (time.perf_counter() - t0) * 1000 / n

        t0 = time.perf_counter()
        for i in range(n):
            gm.panel_gorseli(430, 86, araclar, "claude", "codex", None, True, True, i / n, i * 36.0, "Yenileniyor...")
        panel_ms = (time.perf_counter() - t0) * 1000 / n

        t0 = time.perf_counter()
        for i in range(n):
            gm.kart_gorseli(
                368, 356, "Claude", "#D97757", "Otomatik (statusLine)",
                {"kalan": 78.0, "alt_metin": "2 sa 15 dk sonra yenilenir"},
                {"kalan": 62.0, "alt_metin": "Yenilenme: Paz 11:00"},
                0.78 * (i + 1) / n, 0.62 * (i + 1) / n, "2 dk önce",
                "Limitler yenilendi: 5 saatlik %78", gm.YESIL, "yenile", False,
            )
        kart_ms = (time.perf_counter() - t0) * 1000 / n

        t0 = time.perf_counter()
        for _ in range(n):
            gm.toast_gorseli(240, 34, "✓ Claude yenilendi! (%100)", gm.YESIL)
        toast_ms = (time.perf_counter() - t0) * 1000 / n

        print(f"\n[Hız] çentik: {centik_ms:.1f} ms | panel: {panel_ms:.1f} ms | kart: {kart_ms:.1f} ms | toast: {toast_ms:.1f} ms")
        self.assertLess(centik_ms, 20.0)
        self.assertLess(panel_ms, 40.0)
        self.assertLess(kart_ms, 60.0)
        self.assertLess(toast_ms, 20.0)


def onizlemeleri_uret():
    os.makedirs(CIKTI_DIZIN, exist_ok=True)
    simdi = time.time()

    # 1. Çentik önizleme
    centik = gm.centik_gorseli(
        168,
        24,
        [gm.YESIL, gm.AMBER, gm.KIRMIZI],
        "AGY %14",
        gm.KIRMIZI,
        nefes=0.85,
    )
    centik.save(os.path.join(CIKTI_DIZIN, "onizleme_centik.png"))

    # 2. Panel önizleme
    araclar = {
        "claude": {"bes_kalan": 82.0, "hft_kalan": 64.0},
        "codex": {"bes_kalan": 34.0, "hft_kalan": 71.0},
        "antigravity": {"bes_kalan": 14.0, "hft_kalan": 92.0},
    }
    panel, _ = gm.panel_gorseli(
        430,
        86,
        araclar,
        secili_arac="claude",
        hover_arac="codex",
        hover_dugme="sabit",
        sabit=True,
        yenileniyor=False,
        tarama_faz=0.0,
        donus_aci=0.0,
        durum_metni="",
        coklu_monitor=True,
    )
    panel.save(os.path.join(CIKTI_DIZIN, "onizleme_panel.png"))

    # 3. Kart önizleme
    kart, _ = gm.kart_gorseli(
        368,
        356,
        arac_ad="Claude",
        marka_renk="#D97757",
        kaynak_etiketi=("Otomatik (statusLine)", gm.YESIL),
        bes_durum=(78.0, simdi + 2 * 3600 + 15 * 60, False),
        hft_durum=(42.0, simdi + 3 * 86400 + 4 * 3600, False),
        bes_anim_oran=0.78,
        hft_anim_oran=0.42,
        son_guncelleme="2 dk önce",
        not_metni="Limitler yenilendi: 5 saatlik %78 kaldı, haftalık %42 (ŞşĞğÜüÖöÇçİı)",
        not_renk=gm.YESIL,
        hover_dugme="yenile",
        yenileniyor=False,
    )
    kart.save(os.path.join(CIKTI_DIZIN, "onizleme_kart.png"))

    # 4. Toast önizleme
    metin = "✓ Claude yenilendi! (%100)"
    tw, th = gm.toast_boyut_hesapla(metin, olcek=1.0)
    toast = gm.toast_gorseli(tw, th, metin, gm.YESIL)
    toast.save(os.path.join(CIKTI_DIZIN, "onizleme_toast.png"))


if __name__ == "__main__":
    onizlemeleri_uret()
    unittest.main(verbosity=2)
