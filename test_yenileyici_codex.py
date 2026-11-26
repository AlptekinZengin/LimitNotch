"""yenileyici.py codex komut bulma birim testleri (sahte klasörler, tmp; gerçek ev dizinine dokunulmaz)."""
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ["LIMITNOTCH_DIL"] = "tr"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yenileyici as y  # noqa: E402


def _exe_yap(kok, ad):
    yol = os.path.join(kok, ad, "bin", "codex.exe")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "wb"):
        pass
    return yol


class TestCodexKomutu(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.desktop = os.path.join(self.tmp.name, "releases")
        os.makedirs(self.desktop)

    def test_en_yuksek_surum_secilir(self):
        _exe_yap(self.desktop, "0.9.0-x86_64-pc-windows-msvc")
        e167 = _exe_yap(self.desktop, "0.167.0-x86_64-pc-windows-msvc")
        _exe_yap(self.desktop, "0.166.0-x86_64-pc-windows-msvc")
        # metin sıralaması 0.9.0'ı öne alırdı; sayı tuple doğru sonucu verir
        self.assertEqual(y.codex_komutu(path_codex="", desktop_koku=self.desktop), [e167])
        adaylar = y.codex_adaylari(path_codex="", desktop_koku=self.desktop)
        self.assertEqual(len(adaylar), 3)
        self.assertTrue(adaylar[1][0].count("0.166.0"))

    def test_mtime_degil_surum(self):
        eski = _exe_yap(self.desktop, "0.167.0-x")
        yeni = _exe_yap(self.desktop, "0.166.0-x")
        os.utime(eski, (1, 1))
        os.utime(yeni, None)
        self.assertEqual(y.codex_komutu(path_codex="", desktop_koku=self.desktop), [eski])

    def test_path_varsa_once_o(self):
        _exe_yap(self.desktop, "0.167.0-x")
        yol = os.path.join(self.tmp.name, "codex.cmd")
        with open(yol, "w"):
            pass
        self.assertEqual(y.codex_komutu(path_codex=yol, desktop_koku=self.desktop), [yol])

    def test_path_yolu_yoksa_desktop(self):
        e = _exe_yap(self.desktop, "0.167.0-x")
        sahte = os.path.join(self.tmp.name, "yok", "codex.cmd")
        self.assertEqual(y.codex_komutu(path_codex=sahte, desktop_koku=self.desktop), [e])

    def test_path_yokken_desktop(self):
        e = _exe_yap(self.desktop, "0.167.0-x")
        with mock.patch.object(y.shutil, "which", return_value=None):
            self.assertEqual(y.codex_komutu(desktop_koku=self.desktop), [e])

    def test_vendor_exe_tercih_edilir(self):
        kok = os.path.join(self.tmp.name, "npm")
        yol = os.path.join(kok, "codex.cmd")
        vendor = os.path.join(kok, "node_modules", "@openai", "codex", "node_modules", "@openai",
                              "codex-win32-x64", "vendor", "x86", "bin", "codex.exe")
        os.makedirs(os.path.dirname(vendor))
        for p in (yol, vendor):
            with open(p, "w"):
                pass
        self.assertEqual(y.codex_komutu(path_codex=yol, desktop_koku=self.desktop), [vendor])

    def test_hicbiri_yoksa_none_ve_mesaj(self):
        bos = os.path.join(self.tmp.name, "bos")
        self.assertIsNone(y.codex_komutu(path_codex="", desktop_koku=bos))
        with mock.patch.object(y.shutil, "which", return_value=None), \
                mock.patch.object(y, "CODEX_DESKTOP_KOKU", bos):
            with self.assertRaises(y.CodexHatasi) as c:
                y.codex_sorgula()
            self.assertEqual(str(c.exception), "codex bulunamadı (PATH'te ve Codex Desktop'ta yok)")
            ok, mesaj = y.yenile_codex(yol=os.path.join(self.tmp.name, "d.json"))
            self.assertFalse(ok)
            self.assertIn("codex bulunamadı", mesaj)

    def test_ilk_aday_hata_verirse_sonrakini_dener(self):
        adaylar = [["a.exe"], ["b.exe"]]

        def tek(komut, zaman_asimi):
            if komut == ["a.exe"]:
                raise y.CodexHatasi("bozuk")
            return {"ok": komut[0]}

        with mock.patch.object(y, "codex_adaylari", return_value=adaylar), \
                mock.patch.object(y, "_codex_sorgula_tek", side_effect=tek):
            self.assertEqual(y.codex_sorgula(), {"ok": "b.exe"})

    def test_hepsi_hata_verirse_son_hata(self):
        with mock.patch.object(y, "codex_adaylari", return_value=[["a"], ["b"]]), \
                mock.patch.object(y, "_codex_sorgula_tek", side_effect=y.CodexHatasi("x")):
            with self.assertRaises(y.CodexHatasi):
                y.codex_sorgula()


if __name__ == "__main__":
    unittest.main()
