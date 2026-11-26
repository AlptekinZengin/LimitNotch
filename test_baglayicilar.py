"""baglayicilar kayıt defteri ve yenileyici.yenile yönlendirmesi testleri (gerçek bağlayıcıya bağımlı değil)."""
import os
import sys
import types
import unittest
from unittest import mock

os.environ["LIMITNOTCH_DIL"] = "tr"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baglayicilar  # noqa: E402
import yenileyici  # noqa: E402
from baglayicilar.taban import Baglayici  # noqa: E402


def sahte_baglayici(kimlik, sira=100, bul=False, yenile=None):
    sinif = type("Sahte_" + kimlik, (Baglayici,), {})
    b = sinif()
    b.kimlik = kimlik
    b.sira = sira
    b.bul = (lambda: bul) if not isinstance(bul, Exception) else (lambda: (_ for _ in ()).throw(bul))
    if yenile is not None:
        b.yenile = yenile
    return b


def modul(b):
    return types.SimpleNamespace(BAGLAYICI=b)


class DefterTesti(unittest.TestCase):
    def setUp(self):
        baglayicilar.yeniden_yukle()

    def tearDown(self):
        baglayicilar.yeniden_yukle()

    def yukle(self, *baglayicilar_):
        return mock.patch.object(
            baglayicilar, "_modulleri_yukle", return_value=[modul(b) for b in baglayicilar_])

    def test_siralama(self):
        a, b, c = sahte_baglayici("zzz", 1), sahte_baglayici("bbb", 5), sahte_baglayici("aaa", 5)
        with self.yukle(b, a, c):
            self.assertEqual([x.kimlik for x in baglayicilar.hepsi()], ["zzz", "aaa", "bbb"])

    def test_getir(self):
        a = sahte_baglayici("a")
        with self.yukle(a):
            self.assertIs(baglayicilar.getir("a"), a)
            self.assertIsNone(baglayicilar.getir("yok"))

    def test_kimlikler(self):
        with self.yukle(sahte_baglayici("b", 2), sahte_baglayici("a", 1)):
            self.assertEqual(baglayicilar.kimlikler(), ("a", "b"))

    def test_ayni_kimlik_biri_kalir(self):
        i1, i2 = sahte_baglayici("x"), sahte_baglayici("x")
        with self.yukle(i1, i2):
            self.assertEqual(baglayicilar.hepsi(), [i1])
            self.assertTrue(baglayicilar.yukleme_hatalari())

    def test_baglayici_olmayan_atlanir(self):
        with mock.patch.object(baglayicilar, "_modulleri_yukle", return_value=[
                types.SimpleNamespace(BAGLAYICI="metin"), types.SimpleNamespace(),
                modul(sahte_baglayici("a"))]):
            self.assertEqual(baglayicilar.kimlikler(), ("a",))
            self.assertEqual(len(baglayicilar.yukleme_hatalari()), 2)

    def test_bos_kimlik_atlanir(self):
        with self.yukle(sahte_baglayici("")):
            self.assertEqual(baglayicilar.hepsi(), [])

    def test_bulunanlar(self):
        var, yok = sahte_baglayici("var", 1, bul=True), sahte_baglayici("yok", 2, bul=False)
        patlar = sahte_baglayici("patlar", 3, bul=RuntimeError("x"))
        with self.yukle(var, yok, patlar):
            self.assertEqual(baglayicilar.bulunanlar(), [var])

    def test_yukleme_hatalari_kopya(self):
        with self.yukle(sahte_baglayici("a")):
            baglayicilar.hepsi()
        baglayicilar.yukleme_hatalari()["x"] = "y"
        self.assertNotIn("x", baglayicilar.yukleme_hatalari())

    def test_gercek_modulleri_yukle_liste_doner(self):
        self.assertIsInstance(baglayicilar._modulleri_yukle(), list)
        self.assertIsInstance(baglayicilar.hepsi(), list)

    def test_onbellek_ve_yeniden_yukle(self):
        with self.yukle(sahte_baglayici("a")) as m:
            baglayicilar.hepsi()
            baglayicilar.hepsi()
            self.assertEqual(m.call_count, 1)
            baglayicilar._HATALAR["x"] = "y"
            baglayicilar.yeniden_yukle()
            self.assertEqual(baglayicilar.yukleme_hatalari(), {})
            baglayicilar.hepsi()
            self.assertEqual(m.call_count, 2)

    def test_gecersiz_kimlik_ve_sira(self):
        iyi = sahte_baglayici("iyi")
        bos = sahte_baglayici("  ")
        sirasiz = sahte_baglayici("s1")
        sirasiz.sira = None
        metin = sahte_baglayici("s2")
        metin.sira = "10"
        mantik = sahte_baglayici("s3")
        mantik.sira = True
        with self.yukle(iyi, bos, sirasiz, metin, mantik):
            self.assertEqual(baglayicilar.hepsi(), [iyi])
            self.assertEqual(len(baglayicilar.yukleme_hatalari()), 4)

    def test_taban_ve_gizli_import_edilmez(self):
        sahte = [(None, "taban", False), (None, "_gizli", False)]
        with mock.patch("pkgutil.iter_modules", return_value=sahte),                 mock.patch("importlib.import_module", side_effect=ImportError("x")) as im:
            sonuc = baglayicilar._modulleri_yukle()
        self.assertEqual(sonuc, [])
        adlar = [c.args[0] for c in im.call_args_list]
        self.assertNotIn("baglayicilar.taban", adlar)
        self.assertNotIn("baglayicilar._gizli", adlar)


class YenileYonlendirmeTesti(unittest.TestCase):
    def setUp(self):
        baglayicilar.yeniden_yukle()

    def tearDown(self):
        baglayicilar.yeniden_yukle()

    def test_baglayiciya_yonlendirir(self):
        cagrilar = []
        b = sahte_baglayici("t", yenile=lambda yol=None: (cagrilar.append(yol), (True, "tamam"))[1])
        with mock.patch.object(baglayicilar, "getir", return_value=b):
            self.assertEqual(yenileyici.yenile("t", "yol.json"), (True, "tamam"))
        self.assertEqual(cagrilar, ["yol.json"])

    def test_bilinmeyen_arac(self):
        with mock.patch.object(baglayicilar, "getir", return_value=None):
            self.assertEqual(yenileyici.yenile("yokarac"), (False, "Bilinmeyen araç: yokarac"))

    def test_eski_yola_duser(self):
        with mock.patch.object(baglayicilar, "getir", return_value=None), \
                mock.patch.dict(yenileyici.YENILEYICILER, {"eski": lambda yol=None: (True, "eski")}):
            self.assertEqual(yenileyici.yenile("eski"), (True, "eski"))

    def test_baglayici_eski_yoldan_once(self):
        eski = mock.Mock(return_value=(True, "eski"))
        b = sahte_baglayici("t", yenile=lambda yol=None: (True, "yeni"))
        with mock.patch.object(baglayicilar, "getir", return_value=b),                 mock.patch.dict(yenileyici.YENILEYICILER, {"t": eski}):
            self.assertEqual(yenileyici.yenile("t"), (True, "yeni"))
        eski.assert_not_called()

    def test_getir_hatasi_eski_yola_duser(self):
        with mock.patch.object(baglayicilar, "getir", side_effect=RuntimeError("x")),                 mock.patch.dict(yenileyici.YENILEYICILER, {"eski": lambda yol=None: (True, "eski")}):
            self.assertEqual(yenileyici.yenile("eski"), (True, "eski"))

    def test_istisna_yakalanir(self):
        def patla(yol=None):
            raise ValueError("x")
        b = sahte_baglayici("t", yenile=patla)
        with mock.patch.object(baglayicilar, "getir", return_value=b):
            self.assertEqual(yenileyici.yenile("t"), (False, "Yenilenemedi (ValueError)"))


if __name__ == "__main__":
    unittest.main()
