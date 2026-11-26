"""dil.py iki dilli altyapı birim testleri."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dil  # noqa: E402
import durum_ortak as ortak  # noqa: E402
import gorsel_motor as gm  # noqa: E402


class TestDilSozlukleri(unittest.TestCase):
    def test_tr_en_anahtar_kumeleri_ayni(self):
        self.assertEqual(set(dil.METINLER.keys()), {"tr", "en"})
        self.assertEqual(set(dil.METINLER["tr"].keys()), set(dil.METINLER["en"].keys()))

    def test_degerler_bos_degil(self):
        for kod in ("tr", "en"):
            for k, v in dil.METINLER[kod].items():
                self.assertIsInstance(v, str, f"{kod}.{k}")
                self.assertTrue(len(v) > 0, f"{kod}.{k} boş")


class TestDilSecimi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.yol = os.path.join(self.tmp.name, "durum.json")

    def test_ortam_degiskeni_onceligi(self):
        ortam = {"LIMITNOTCH_DIL": "en"}
        with mock.patch.dict(os.environ, ortam, clear=False):
            self.assertEqual(dil.etkin_dil({"dil": "tr"}), "en")
        with mock.patch.dict(os.environ, {"LIMITNOTCH_DIL": "TR"}, clear=False):
            self.assertEqual(dil.etkin_dil({"dil": "en"}), "tr")

    def test_durum_json_tercihi_ve_kayit(self):
        with mock.patch.dict(os.environ, {"LIMITNOTCH_DIL": ""}, clear=False):
            self.assertTrue(dil.dil_ayarla("en", self.yol))
            self.assertEqual(dil.etkin_dil(yol=self.yol), "en")
            self.assertTrue(dil.dil_ayarla("tr", self.yol))
            self.assertEqual(dil.etkin_dil(yol=self.yol), "tr")
            self.assertFalse(dil.dil_ayarla("fr", self.yol))

    def test_windows_dili_fallback(self):
        with mock.patch.dict(os.environ, {"LIMITNOTCH_DIL": ""}, clear=False):
            with mock.patch.object(dil.ctypes, "windll", create=True) as w:
                w.kernel32.GetUserDefaultUILanguage.return_value = 0x041F  # tr-TR
                self.assertEqual(dil.etkin_dil(durum={}), "tr")
                w.kernel32.GetUserDefaultUILanguage.return_value = 0x0409  # en-US
                self.assertEqual(dil.etkin_dil(durum={}), "en")

    def test_eksik_anahtar_dususu_ve_bicimlendirme(self):
        with mock.patch.dict(os.environ, {"LIMITNOTCH_DIL": "en"}, clear=False):
            self.assertEqual(dil.t("yuzde_kaldi", yuzde="42"), "42% left")
            self.assertEqual(dil.t("olmayan_anahtar_xyz"), "olmayan_anahtar_xyz")
            with mock.patch.dict(dil.METINLER["en"], clear=False):
                dil.METINLER["en"].pop("centik_bos", None)
                self.assertEqual(dil.t("centik_bos"), dil.METINLER["tr"]["centik_bos"])
            # Eksik format argümanında da çökmez
            self.assertIsInstance(dil.t("yuzde_kaldi"), str)

    def test_ingilizce_gorsel_motor_ve_araclar(self):
        with mock.patch.dict(os.environ, {"LIMITNOTCH_DIL": "en"}, clear=False):
            img, _ = gm.panel_gorseli(
                430, 86,
                {"claude": {"bes_kalan": 75, "hft_kalan": 50}},
                yenileniyor=True,
            )
            self.assertEqual(img.size, (430, 86))
            kart, _ = gm.kart_gorseli(
                368, 356, "Claude Code", "#D97757", "Auto (refreshed)",
                (75, None, False), (50, None, False),
            )
            self.assertEqual(kart.size, (368, 356))


class TestTara(unittest.TestCase):
    def test_tarama_temiz_doner(self):
        import tara
        self.assertEqual(tara.main(), 0)


if __name__ == "__main__":
    unittest.main()
