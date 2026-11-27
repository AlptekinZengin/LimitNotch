"""agy_gizli.py birim testleri (tüm Win32 ve alt süreç çağrıları sahtelenir)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agy_gizli  # noqa: E402
import dil  # noqa: E402
import durum_ortak as ortak  # noqa: E402
import yenileyici  # noqa: E402

ORNEK_KOTA = {
    "groups": [
        {
            "displayName": "Gemini",
            "buckets": [
                {"window": "5h", "remainingFraction": 0.75, "resetTime": 1800000000},
                {"window": "weekly", "remainingFraction": 0.50, "resetTime": 1800500000},
            ],
        }
    ]
}


class TestAgyGizli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exe = os.path.join(self.tmp.name, "Antigravity.exe")
        with open(self.exe, "wb") as f:
            f.write(b"sahte")
        self.profil = os.path.join(self.tmp.name, "profil")
        self.eski_son = agy_gizli._son_deneme
        agy_gizli._son_deneme = None
        self.addCleanup(self._son_geri_yukle)

    def _son_geri_yukle(self):
        agy_gizli._son_deneme = self.eski_son

    def _hub_yaz(self, ad, pid=4242):
        yol = os.path.join(self.tmp.name, ad)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({"pid": pid, "httpPort": 12345, "csrfToken": "sahte"}, f)
        return yol

    def test_a_ortam_sifir_iken_baslatilmaz(self):
        with mock.patch.dict(os.environ, {"LIMIT_CUBUGU_AGY_GIZLI": "0"}, clear=False), \
                mock.patch.object(agy_gizli, "_baslat") as baslat:
            self.assertFalse(agy_gizli.kullanilabilir_mi(simdi=1000.0, exe=self.exe))
            sonuc = agy_gizli.gizli_oku(exe=self.exe, profil=self.profil, simdi=1000.0)
        self.assertIsNone(sonuc)
        baslat.assert_not_called()

    def test_b_exe_yoksa_none(self):
        olmayan = os.path.join(self.tmp.name, "yok.exe")
        with mock.patch.dict(os.environ, {"LIMIT_CUBUGU_AGY_GIZLI": "1"}, clear=False), \
                mock.patch.object(agy_gizli, "_baslat") as baslat:
            self.assertFalse(agy_gizli.kullanilabilir_mi(simdi=1000.0, exe=olmayan))
            sonuc = agy_gizli.gizli_oku(exe=olmayan, profil=self.profil, simdi=1000.0)
        self.assertIsNone(sonuc)
        baslat.assert_not_called()

    def test_c_yeni_hub_cikinca_sorgu_doner_ve_kapat_bir_kez_cagrilir(self):
        eski_hub = self._hub_yaz("hub_1000.json", pid=1111)
        yeni_hub = self._hub_yaz("hub_2000.json", pid=2222)
        sahte_oturum = {"pid": 9001, "surec": 10, "is_nesnesi": 20, "masaustu": 30}
        hub_durumu = [[eski_hub], [eski_hub], [yeni_hub, eski_hub]]

        def sahte_hublar():
            return list(hub_durumu.pop(0) if len(hub_durumu) > 1 else hub_durumu[0])

        sorgu = mock.Mock(return_value=ORNEK_KOTA)
        with mock.patch.dict(os.environ, {"LIMIT_CUBUGU_AGY_GIZLI": "1"}, clear=False), \
                mock.patch.object(agy_gizli, "HUB_ARALIK", 0.01), \
                mock.patch.object(agy_gizli, "_baslat", return_value=sahte_oturum) as baslat, \
                mock.patch.object(agy_gizli, "_kapat") as kapat, \
                mock.patch.object(yenileyici, "antigravity_hub_dosyalari", side_effect=sahte_hublar), \
                mock.patch.object(yenileyici, "antigravity_sureci_mi", side_effect=lambda p: p == 2222):
            sonuc = agy_gizli.gizli_oku(
                sorgu=sorgu, zaman_asimi=1.0, exe=self.exe, profil=self.profil, simdi=1000.0,
            )

        self.assertEqual(sonuc, ORNEK_KOTA)
        baslat.assert_called_once_with(self.exe, self.profil)
        sorgu.assert_called_once_with(yeni_hub)
        kapat.assert_called_once_with(sahte_oturum)

    def test_d_hub_hic_cikmazsa_none_ve_kapat_cagrilir(self):
        sahte_oturum = {"pid": 9002, "surec": 11, "is_nesnesi": 21, "masaustu": 31}
        with mock.patch.dict(os.environ, {"LIMIT_CUBUGU_AGY_GIZLI": "1"}, clear=False), \
                mock.patch.object(agy_gizli, "HUB_ARALIK", 0.05), \
                mock.patch.object(agy_gizli, "_baslat", return_value=sahte_oturum) as baslat, \
                mock.patch.object(agy_gizli, "_kapat") as kapat, \
                mock.patch.object(yenileyici, "antigravity_hub_dosyalari", return_value=[]):
            sonuc = agy_gizli.gizli_oku(
                sorgu=mock.Mock(), zaman_asimi=0.25, exe=self.exe, profil=self.profil, simdi=1000.0,
            )

        self.assertIsNone(sonuc)
        baslat.assert_called_once()
        kapat.assert_called_once_with(sahte_oturum)

    def test_e_sorgu_istisna_firlatirsa_kapat_yine_cagrilir(self):
        yeni_hub = self._hub_yaz("hub_3000.json", pid=3333)
        sahte_oturum = {"pid": 9003, "surec": 12, "is_nesnesi": 22, "masaustu": 32}
        cagrilar = [[], [yeni_hub]]

        def sahte_hublar():
            return list(cagrilar.pop(0) if len(cagrilar) > 1 else cagrilar[0])

        def patlayan_sorgu(_hub):
            raise RuntimeError("beklenmeyen hata")

        with mock.patch.dict(os.environ, {"LIMIT_CUBUGU_AGY_GIZLI": "1"}, clear=False), \
                mock.patch.object(agy_gizli, "HUB_ARALIK", 0.01), \
                mock.patch.object(agy_gizli, "_baslat", return_value=sahte_oturum), \
                mock.patch.object(agy_gizli, "_kapat") as kapat, \
                mock.patch.object(yenileyici, "antigravity_hub_dosyalari", side_effect=sahte_hublar), \
                mock.patch.object(yenileyici, "antigravity_sureci_mi", return_value=True):
            sonuc = agy_gizli.gizli_oku(
                sorgu=patlayan_sorgu, zaman_asimi=1.0, exe=self.exe, profil=self.profil, simdi=1000.0,
            )

        self.assertIsNone(sonuc)
        kapat.assert_called_once_with(sahte_oturum)

    def test_f_on_dakika_siklik_siniri(self):
        sahte_oturum = {"pid": 9004, "surec": 13, "is_nesnesi": 23, "masaustu": 33}
        with mock.patch.dict(os.environ, {"LIMIT_CUBUGU_AGY_GIZLI": "1"}, clear=False), \
                mock.patch.object(agy_gizli, "HUB_ARALIK", 0.01), \
                mock.patch.object(agy_gizli, "_baslat", return_value=sahte_oturum) as baslat, \
                mock.patch.object(agy_gizli, "_kapat") as kapat, \
                mock.patch.object(yenileyici, "antigravity_hub_dosyalari", return_value=[]):
            ilk = agy_gizli.gizli_oku(
                sorgu=mock.Mock(), zaman_asimi=0.05, exe=self.exe, profil=self.profil, simdi=1000.0,
            )
            ikinci = agy_gizli.gizli_oku(
                sorgu=mock.Mock(), zaman_asimi=0.05, exe=self.exe, profil=self.profil, simdi=1100.0,
            )
            ucuncu = agy_gizli.gizli_oku(
                sorgu=mock.Mock(), zaman_asimi=0.05, exe=self.exe, profil=self.profil, simdi=1601.0,
            )

        self.assertIsNone(ilk)
        self.assertIsNone(ikinci)
        self.assertIsNone(ucuncu)
        self.assertEqual(baslat.call_count, 2)
        self.assertEqual(kapat.call_count, 2)

    def test_g_yenile_antigravity_sorgu_verilmisse_gizli_denemez(self):
        durum_yolu = os.path.join(self.tmp.name, "durum.json")

        def sahte_kapali():
            raise yenileyici.AntigravityHatasi(dil.t("agy_kapali_hata"))

        with mock.patch.object(agy_gizli, "gizli_oku") as gizli_mock:
            ok, mesaj = yenileyici.yenile_antigravity(yol=durum_yolu, sorgu=sahte_kapali)

        self.assertFalse(ok)
        self.assertEqual(mesaj, dil.t("agy_kapali_not"))
        gizli_mock.assert_not_called()

    def test_yenile_antigravity_gizli_basarili_kaydeder(self):
        durum_yolu = os.path.join(self.tmp.name, "durum.json")

        def kapali_sorgula():
            raise yenileyici.AntigravityHatasi(dil.t("agy_kapali_hata"))

        with mock.patch.dict(os.environ, {"LIMITNOTCH_DIL": "tr"}, clear=False), \
                mock.patch.object(yenileyici, "antigravity_sorgula", side_effect=kapali_sorgula), \
                mock.patch.object(agy_gizli, "gizli_oku", return_value=ORNEK_KOTA) as gizli_mock:
            ok, mesaj = yenileyici.yenile_antigravity(yol=durum_yolu)

        self.assertTrue(ok)
        self.assertEqual(mesaj, dil.t("agy_gizli_yenilendi"))
        gizli_mock.assert_called_once()
        kayit = ortak.oku(durum_yolu)["antigravity"]
        self.assertEqual(kayit["kaynak"], dil.t("kaynak_otomatik_gizli"))
        self.assertEqual(kayit["bes_saat"]["kalan"], 75.0)
        self.assertEqual(kayit["haftalik"]["kalan"], 50.0)

    def test_sorgu_antigravity_hatasinda_yeniden_dener(self):
        yeni_hub = self._hub_yaz("hub_4000.json", pid=4444)
        sahte_oturum = {"pid": 9005, "surec": 14, "is_nesnesi": 24, "masaustu": 34}
        cagrilar = [[], [yeni_hub]]

        def sahte_hublar():
            return list(cagrilar.pop(0) if len(cagrilar) > 1 else cagrilar[0])

        sorgu = mock.Mock(side_effect=[yenileyici.AntigravityHatasi("hazır değil"), ORNEK_KOTA])
        with mock.patch.dict(os.environ, {"LIMIT_CUBUGU_AGY_GIZLI": "1"}, clear=False), \
                mock.patch.object(agy_gizli, "HUB_ARALIK", 0.01), \
                mock.patch.object(agy_gizli, "SORGU_ARALIK", 0.01), \
                mock.patch.object(agy_gizli, "SORGU_ZAMAN_ASIMI", 1.0), \
                mock.patch.object(agy_gizli, "_baslat", return_value=sahte_oturum), \
                mock.patch.object(agy_gizli, "_kapat") as kapat, \
                mock.patch.object(yenileyici, "antigravity_hub_dosyalari", side_effect=sahte_hublar), \
                mock.patch.object(yenileyici, "antigravity_sureci_mi", return_value=True):
            sonuc = agy_gizli.gizli_oku(
                sorgu=sorgu, zaman_asimi=1.0, exe=self.exe, profil=self.profil, simdi=1000.0,
            )

        self.assertEqual(sonuc, ORNEK_KOTA)
        self.assertEqual(sorgu.call_count, 2)
        kapat.assert_called_once_with(sahte_oturum)

    def test_kilit_doluyken_ikinci_cagri_baslatmaz(self):
        agy_gizli._KILIT.acquire()
        try:
            with mock.patch.dict(os.environ, {"LIMIT_CUBUGU_AGY_GIZLI": "1"}, clear=False), \
                    mock.patch.object(agy_gizli, "_baslat") as baslat:
                sonuc = agy_gizli.gizli_oku(exe=self.exe, profil=self.profil, simdi=1000.0)
        finally:
            agy_gizli._KILIT.release()

        self.assertIsNone(sonuc)
        baslat.assert_not_called()

    def test_kapat_yalniz_kendi_agacina_dokunur_ve_tutamaclari_kapatir(self):
        oturum = {"pid": 500, "surec": 101, "is_nesnesi": 202, "masaustu": 303}
        canli_set = {500, 501}

        def sahte_kill(pid):
            canli_set.discard(pid)

        with mock.patch.object(agy_gizli, "_surec_agaci", side_effect=[{500, 501}, {501}]), \
                mock.patch.object(agy_gizli, "_pencereler", return_value=[777]) as pencereler, \
                mock.patch.object(agy_gizli, "_pencere_kapat") as pencere_kapat, \
                mock.patch.object(agy_gizli, "_surec_bekle", return_value=False) as bekle, \
                mock.patch.object(agy_gizli, "_is_bitir", return_value=False), \
                mock.patch.object(agy_gizli, "_surec_canli_mi", side_effect=lambda p: p in canli_set), \
                mock.patch.object(agy_gizli, "_taskkill", side_effect=sahte_kill) as taskkill, \
                mock.patch.object(agy_gizli, "_tutamac_kapat") as tutamac_kapat, \
                mock.patch.object(agy_gizli, "_masaustu_kapat") as masaustu_kapat:
            agy_gizli._kapat(oturum)

        pencereler.assert_called_once_with({500, 501}, 303)
        pencere_kapat.assert_called_once_with(777)
        bekle.assert_called_once_with(101, agy_gizli.KAPANMA_BEKLEME)
        self.assertEqual([c.args[0] for c in taskkill.call_args_list], [500, 501])
        self.assertEqual([c.args[0] for c in tutamac_kapat.call_args_list], [101, 202])
        masaustu_kapat.assert_called_once_with(303)

    def test_kapat_job_basariliysa_pid_ile_oldurmez(self):
        oturum = {"pid": 500, "surec": 101, "is_nesnesi": 202, "masaustu": 303}
        with mock.patch.object(agy_gizli, "_surec_agaci", return_value={500, 501}), \
                mock.patch.object(agy_gizli, "_pencereler", return_value=[]), \
                mock.patch.object(agy_gizli, "_surec_bekle", return_value=True), \
                mock.patch.object(agy_gizli, "_is_bitir", return_value=True) as is_bitir, \
                mock.patch.object(agy_gizli, "_surec_canli_mi", return_value=True), \
                mock.patch.object(agy_gizli, "_taskkill") as taskkill, \
                mock.patch.object(agy_gizli, "_tutamac_kapat") as tutamac_kapat, \
                mock.patch.object(agy_gizli, "_masaustu_kapat") as masaustu_kapat:
            agy_gizli._kapat(oturum)

        is_bitir.assert_called_once_with(202)
        taskkill.assert_not_called()
        self.assertEqual([c.args[0] for c in tutamac_kapat.call_args_list], [101, 202])
        masaustu_kapat.assert_called_once_with(303)


if __name__ == "__main__":
    unittest.main()
