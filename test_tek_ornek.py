"""Tek örnek sinyali: gerçek Windows event'i, izole adlar ve panel davranışı."""
import ctypes
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
import uuid


DOSYA = Path(__file__).with_name("limit_cubugu.pyw")
spec = importlib.util.spec_from_file_location("limit_cubugu_tek_ornek_test", DOSYA)
lc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lc)


class TestTekOrnek(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"LIMIT_CUBUGU_ORNEK_ADI": "LimitCubuguTest_" + uuid.uuid4().hex})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(lc.tek_ornek_temizle)

    @unittest.skipUnless(sys.platform == "win32", "Windows event testi")
    def test_ikinci_surec_sinyal_gonderir_ve_cikar(self):
        self.assertTrue(lc.tek_ornek())
        self.assertFalse(lc.one_ac_istendi())
        for _ in range(2):
            sonuc = subprocess.run([sys.executable, str(DOSYA)], timeout=15, capture_output=True)
            self.assertEqual(sonuc.returncode, 0, sonuc.stderr)
            self.assertTrue(lc.one_ac_istendi())
            self.assertFalse(lc.one_ac_istendi(), "Event tüketilince sıfırlanmalı")
        lc.tek_ornek_temizle()
        self.assertIsNone(lc._MUTEX_HANDLE)
        self.assertIsNone(lc._ONE_AC_EVENT)
        self.assertTrue(lc.tek_ornek(), "Temizlikten sonra yeni sahip oluşturulmalı")
        self.assertFalse(lc.one_ac_istendi())

    def test_veri_dosyasi_adlari_gercek_ornekten_ayri(self):
        with patch.dict(os.environ):
            os.environ.pop("LIMIT_CUBUGU_ORNEK_ADI", None)
            os.environ.pop("LIMIT_CUBUGU_DOSYA", None)
            gercek = lc._ornek_adi()
            os.environ["LIMIT_CUBUGU_DOSYA"] = "test_cikti/durum.json"
            test = lc._ornek_adi()
            self.assertNotEqual(gercek, test)
            os.environ["LIMIT_CUBUGU_DOSYA"] = os.path.abspath("test_cikti/durum.json")
            self.assertEqual(test, lc._ornek_adi())
            os.environ["LIMIT_CUBUGU_DOSYA"] = "test_cikti/baska.json"
            self.assertNotEqual(test, lc._ornek_adi())

    def test_sinyal_yokken_panel_degismez(self):
        uyg = Mock()
        with patch.object(lc, "one_ac_istendi", return_value=False):
            lc.LimitCubugu._one_ac_kontrol(uyg)
        uyg.ac.assert_not_called()
        uyg.kok.lift.assert_not_called()

    def test_sinyal_paneli_acar_ve_uste_getirir(self):
        uyg = Mock()
        with patch.object(lc, "one_ac_istendi", return_value=True), patch.object(lc, "en_uste_al") as ust, patch.object(lc.time, "time", return_value=100):
            lc.LimitCubugu._one_ac_kontrol(uyg)
        self.assertEqual(uyg._baslangic_bitis, 103)
        self.assertIsNone(uyg.ayrilma_bas)
        uyg.ac.assert_called_once_with()
        uyg.kok.deiconify.assert_called_once_with()
        uyg.kok.attributes.assert_called_once_with("-topmost", True)
        uyg.kok.lift.assert_called_once_with()
        ust.assert_called_once_with(uyg.kok)

    @unittest.skipUnless(sys.platform == "win32", "Windows ctypes testi")
    def test_ikinci_kopya_kendi_handlelarini_kapatir(self):
        k32 = Mock()
        k32.CreateEventW.return_value = 123
        k32.CreateMutexW.return_value = 456
        with patch.object(ctypes, "WinDLL", return_value=k32), patch.object(ctypes, "get_last_error", return_value=183):
            self.assertFalse(lc.tek_ornek())
        k32.SetEvent.assert_called_once_with(123)
        self.assertEqual([c.args[0] for c in k32.CloseHandle.call_args_list], [123, 456])
        self.assertIsNone(lc._ONE_AC_EVENT)
        self.assertIsNone(lc._MUTEX_HANDLE)

    @unittest.skipUnless(sys.platform == "win32", "Windows ctypes testi")
    def test_mutex_hatasinda_event_temizlenir(self):
        k32 = Mock()
        k32.CreateEventW.return_value = 123
        k32.CreateMutexW.return_value = None
        with patch.object(ctypes, "WinDLL", return_value=k32):
            self.assertTrue(lc.tek_ornek())
        k32.CloseHandle.assert_called_once_with(123)
        self.assertIsNone(lc._ONE_AC_EVENT)

    def test_main_hatasinda_kaynaklar_temizlenir(self):
        with patch.object(lc, "tek_ornek", return_value=True), patch.object(lc, "dpi_farkindaligi"), patch.object(lc.tk, "Tk", side_effect=RuntimeError("test")), patch.object(lc, "tek_ornek_temizle") as temizle:
            with self.assertRaises(RuntimeError):
                lc.main()
        temizle.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
