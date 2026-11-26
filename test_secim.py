"""secim.py testleri (sahte bağlayıcılar, geçici durum.json)."""
import os
import tempfile
import unittest
from unittest import mock

import baglayicilar
import durum_ortak as ortak
import secim
from baglayicilar import taban


def _sahte(kimlik, sira, durum=taban.KARARLI, bulunur=True, ad=None, kisa=""):
    class Sahte(taban.Baglayici):
        pass

    s = Sahte()
    s.kimlik = kimlik
    s.ad = ad or kimlik.title()
    s.kisa_ad = kisa
    s.sira = sira
    s.durum = durum
    s.renk = "#112233"
    s.okuma_yolu = f"{kimlik} okuma yolu"
    s.bul = lambda: bulunur
    return s


class SecimTesti(unittest.TestCase):
    def setUp(self):
        self.a = _sahte("a", 1)
        self.b = _sahte("b", 2, durum=taban.DENEYSEL)
        self.c = _sahte("c", 3, bulunur=False, kisa="CC")
        self.hepsi = [self.a, self.b, self.c]
        yamalar = [
            mock.patch.object(baglayicilar, "hepsi", lambda: list(self.hepsi)),
            mock.patch.object(baglayicilar, "kimlikler",
                              lambda: tuple(x.kimlik for x in self.hepsi)),
            mock.patch.object(baglayicilar, "bulunanlar",
                              lambda: [x for x in self.hepsi if x.bul()]),
            mock.patch.object(baglayicilar, "getir",
                              lambda k: next((x for x in self.hepsi if x.kimlik == k), None)),
        ]
        for y in yamalar:
            y.start()
            self.addCleanup(y.stop)
        self.klasor = tempfile.TemporaryDirectory()
        self.addCleanup(self.klasor.cleanup)
        self.yol = os.path.join(self.klasor.name, "durum.json")

    def test_kayitli_secim_filtrelenir_ve_kayit_sirasina_gore_doner(self):
        durum = {"araclar": ["c", "zzz", "a"]}
        self.assertEqual(secim.kayitli_secim(durum), ["c", "zzz", "a"])
        self.assertEqual(secim.etkin_kimlikler(durum), ["a", "c"])
        self.assertFalse(secim.kurulum_gerekli(durum))

    def test_eski_kullanici_gecisi(self):
        durum = {"surum": 1, "b": {"kaynak": "otomatik"}, "a": {"guncellendi": 1}}
        self.assertEqual(secim.etkin_kimlikler(durum), ["a", "b"])
        self.assertFalse(secim.kurulum_gerekli(durum))

    def test_bos_durum_bulunan_kararlilar_ve_kurulum_gerekli(self):
        durum = {"surum": 1}
        self.assertEqual(secim.etkin_kimlikler(durum), ["a"])
        self.assertTrue(secim.kurulum_gerekli(durum))

    def test_hic_kararli_bulunmazsa_hepsi(self):
        self.a.bul = lambda: False
        self.assertEqual(secim.etkin_kimlikler({}), ["a", "b", "c"])

    def test_secimi_kaydet_ve_oku(self):
        self.assertTrue(secim.secimi_kaydet(["b", "a"], self.yol))
        durum = ortak.oku(self.yol)
        self.assertEqual(secim.kayitli_secim(durum), ["b", "a"])
        self.assertEqual(secim.etkin_kimlikler(durum), ["a", "b"])

    def test_bilgi_bilinen_ve_bilinmeyen(self):
        b = secim.bilgi("c")
        self.assertEqual(b, {"ad": "C", "kisa_ad": "CC", "renk": "#112233",
                             "durum": taban.KARARLI, "okuma_yolu": "c okuma yolu"})
        self.assertEqual(secim.bilgi("b")["durum"], taban.DENEYSEL)
        self.assertEqual(secim.bilgi("yok"), {"ad": "yok", "kisa_ad": "yok", "renk": "#94A3B8",
                                              "durum": "kararli", "okuma_yolu": ""})

    def test_bozuk_degerler_istisna_firlatmaz(self):
        self.assertIsNone(secim.kayitli_secim({"araclar": "x"}))
        self.assertEqual(secim.kayitli_secim({"araclar": [1, "claude"]}), ["claude"])
        self.assertEqual(secim.etkin_kimlikler({"araclar": "x"}), ["a"])
        self.assertEqual(secim.etkin_kimlikler({"araclar": [1, "b"]}), ["b"])
        self.assertTrue(secim.kurulum_gerekli({"araclar": None}))
        # dict olmayan bölüm eski kullanıcı sayılmaz: yedek yol (bulunan kararlı = a), "c" gelmez
        self.assertEqual(secim.etkin_kimlikler({"c": "dict degil"}), ["a"])
        self.assertTrue(secim.kurulum_gerekli({"c": "dict degil"}))
        # durum dict bile değilse
        self.assertIsNone(secim.kayitli_secim(None))
        self.assertIsInstance(secim.etkin_kimlikler(None), list)
        self.assertFalse(secim.kurulum_gerekli(None) is None)

    def test_bos_ya_da_taninmayan_secim_bos_liste_vermez(self):
        # Sonuç asla boş olmasın: yedek yol (bulunan kararlı = a) devreye girer.
        self.assertEqual(secim.etkin_kimlikler({"araclar": []}), ["a"])
        self.assertEqual(secim.etkin_kimlikler({"araclar": ["yok"]}), ["a"])

    def test_hepsi_istisna_atarsa_bos_doner(self):
        with mock.patch.object(baglayicilar, "kimlikler", side_effect=RuntimeError("x")):
            self.assertEqual(secim.etkin_kimlikler({}), [])


if __name__ == "__main__":
    unittest.main()
