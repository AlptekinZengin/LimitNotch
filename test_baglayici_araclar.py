"""Claude, Codex ve Antigravity bağlayıcılarının sözleşme ve sarma testleri."""
import os
import sys
import unittest
from unittest import mock

_KOK = os.path.dirname(os.path.abspath(__file__))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

import yenileyici  # noqa: E402
from baglayicilar import claude, codex, antigravity, taban  # noqa: E402


class BaglayiciAraclarTesti(unittest.TestCase):
    def test_sozlesme_ve_oznitelikler(self):
        beklenenler = [
            (claude, "claude", taban.KARARLI, 10, "#D97757"),
            (codex, "codex", taban.KARARLI, 20, "#10B981"),
            (antigravity, "antigravity", taban.DENEYSEL, 30, "#38BDF8"),
        ]
        for modul, kimlik, durum, sira, renk in beklenenler:
            with self.subTest(kimlik=kimlik):
                self.assertTrue(hasattr(modul, "BAGLAYICI"))
                b = modul.BAGLAYICI
                self.assertIsInstance(b, taban.Baglayici)
                self.assertEqual(b.kimlik, kimlik)
                self.assertIn(b.durum, taban.DURUMLAR)
                self.assertEqual(b.durum, durum)
                self.assertTrue(b.renk.startswith("#"))
                self.assertEqual(len(b.renk), 7)
                self.assertEqual(b.renk, renk)
                self.assertTrue(bool(b.ad and b.ad.strip()))
                self.assertTrue(bool(b.okuma_yolu and b.okuma_yolu.strip()))
                self.assertEqual(b.sira, sira)

    def test_claude_bul(self):
        with mock.patch.object(yenileyici, "claude_komutu", return_value="C:\\x\\claude.exe"):
            self.assertTrue(claude.BAGLAYICI.bul())
        with mock.patch.object(yenileyici, "claude_komutu", return_value=None):
            self.assertFalse(claude.BAGLAYICI.bul())
        with mock.patch.object(yenileyici, "claude_komutu", side_effect=OSError("erişim yok")):
            self.assertFalse(claude.BAGLAYICI.bul())

    def test_codex_bul(self):
        with mock.patch.object(yenileyici, "codex_komutu", return_value=["C:\\x\\codex.exe"]):
            self.assertTrue(codex.BAGLAYICI.bul())
        with mock.patch.object(yenileyici, "codex_komutu", return_value=None):
            self.assertFalse(codex.BAGLAYICI.bul())
        with mock.patch.object(yenileyici, "codex_komutu", side_effect=OSError("erişim yok")):
            self.assertFalse(codex.BAGLAYICI.bul())

    def test_antigravity_bul(self):
        with mock.patch.object(yenileyici, "antigravity_hub_dosyalari", return_value=["a.json"]), \
             mock.patch.object(os.path, "isdir", return_value=False):
            self.assertTrue(antigravity.BAGLAYICI.bul())

        with mock.patch.object(yenileyici, "antigravity_hub_dosyalari", return_value=[]), \
             mock.patch.object(os.path, "isdir", return_value=False):
            self.assertFalse(antigravity.BAGLAYICI.bul())

        with mock.patch.object(yenileyici, "antigravity_hub_dosyalari", side_effect=OSError("hata")), \
             mock.patch.object(os.path, "isdir", return_value=False):
            self.assertFalse(antigravity.BAGLAYICI.bul())

        with mock.patch.object(yenileyici, "antigravity_hub_dosyalari", return_value=[]), \
             mock.patch.object(os.path, "isdir", return_value=True) as isdir:
            self.assertTrue(antigravity.BAGLAYICI.bul())
            isdir.assert_called_once_with(
                os.path.join(os.path.expanduser("~"), ".gemini", "antigravity"))

        with mock.patch.object(yenileyici, "antigravity_hub_dosyalari", side_effect=OSError("hata")), \
             mock.patch.object(os.path, "isdir", return_value=True):
            self.assertTrue(antigravity.BAGLAYICI.bul())

    def test_yenile_aktarimi(self):
        hedefler = [
            (claude.BAGLAYICI, "yenile_claude"),
            (codex.BAGLAYICI, "yenile_codex"),
            (antigravity.BAGLAYICI, "yenile_antigravity"),
        ]
        yol = "sahte/durum.json"
        for baglayici, fonk_adi in hedefler:
            with self.subTest(arac=baglayici.kimlik):
                donus = (True, "ok")
                with mock.patch.object(yenileyici, fonk_adi, return_value=donus) as m:
                    sonuc = baglayici.yenile(yol)
                    m.assert_called_once_with(yol)
                    self.assertIs(sonuc, donus)
                with mock.patch.object(yenileyici, fonk_adi, return_value=donus) as m:
                    baglayici.yenile()
                    m.assert_called_once_with(None)

    def test_yenile_istisna_yakalama(self):
        hedefler = [
            (claude.BAGLAYICI, "yenile_claude"),
            (codex.BAGLAYICI, "yenile_codex"),
            (antigravity.BAGLAYICI, "yenile_antigravity"),
        ]
        for baglayici, fonk_adi in hedefler:
            with self.subTest(arac=baglayici.kimlik):
                with mock.patch.object(yenileyici, fonk_adi, side_effect=RuntimeError("patladı")):
                    sonuc = baglayici.yenile("sahte/durum.json")
                    self.assertIsInstance(sonuc, tuple)
                    self.assertEqual(len(sonuc), 2)
                    self.assertIs(sonuc[0], False)
                    self.assertIsInstance(sonuc[1], str)
                    self.assertIn("RuntimeError", sonuc[1])


if __name__ == "__main__":
    unittest.main()
