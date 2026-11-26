import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

os.environ["LIMITNOTCH_DIL"] = "tr"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import durum_ortak as ortak  # noqa: E402
from baglayicilar import copilot as c  # noqa: E402

GERCEK = {
    "copilot_plan": "individual", "access_type_sku": "free_limited_copilot",
    "quota_reset_date": "2026-12-01", "quota_reset_date_utc": "2026-12-01T00:00:00.000Z",
    "endpoints": {"api": "https://gizli.example/api", "token": "GIZLI-TOKEN-123"},
    "quota_snapshots": {
        "chat": {"percent_remaining": 99.7, "remaining": 199, "entitlement": 200, "unlimited": False},
        "completions": {"percent_remaining": 100.0, "remaining": 2000, "entitlement": 2000,
                        "unlimited": False},
        "premium_interactions": {"percent_remaining": 0.0, "remaining": 0, "entitlement": 0,
                                 "unlimited": False},
    },
}
UCRETLI = {
    "quota_reset_date": "2026-12-01",
    "quota_snapshots": {
        "chat": {"percent_remaining": 100.0, "entitlement": 0, "unlimited": True},
        "completions": {"percent_remaining": 100.0, "entitlement": 0, "unlimited": True},
        "premium_interactions": {"percent_remaining": 40.0, "remaining": 120, "entitlement": 300,
                                 "unlimited": False},
    },
}
HEPSI_SINIRSIZ = {"quota_snapshots": {
    k: {"percent_remaining": 100.0, "entitlement": 0, "unlimited": True}
    for k in ("chat", "completions", "premium_interactions")}}


def sahte(cikti="", kod=0, hata=""):
    return subprocess.CompletedProcess(["gh"], kod, stdout=cikti, stderr=hata)


class OznitelikTesti(unittest.TestCase):
    def test_ozellikler(self):
        b = c.BAGLAYICI
        self.assertEqual((b.kimlik, b.ad, b.kisa_ad, b.renk, b.durum, b.sira),
                         ("copilot", "GitHub Copilot", "Copilot", "#A78BFA", "deneysel", 40))
        self.assertIn("gh api copilot_internal/user", b.okuma_yolu)


class BulTesti(unittest.TestCase):
    def test_gh_yok(self):
        with mock.patch.object(c, "gh_komutu", return_value=None):
            self.assertFalse(c.BAGLAYICI.bul())

    def test_gh_var_copilot_klasoru_var(self):
        with mock.patch.object(c, "gh_komutu", return_value="gh"), \
             mock.patch.object(c.os.path, "expanduser", return_value="EV"), \
             mock.patch.object(c.os.path, "isdir", side_effect=lambda p: p.endswith(".copilot")):
            self.assertTrue(c.BAGLAYICI.bul())

    def test_gh_var_iz_yok(self):
        with mock.patch.object(c, "gh_komutu", return_value="gh"), \
             mock.patch.object(c.os.path, "isdir", return_value=False), \
             mock.patch.object(c.glob, "glob", return_value=[]):
            self.assertFalse(c.BAGLAYICI.bul())

    def test_eklenti_klasoru(self):
        with mock.patch.object(c, "gh_komutu", return_value="gh"), \
             mock.patch.object(c.os.path, "isdir", return_value=False), \
             mock.patch.object(c.glob, "glob", return_value=["x/github.copilot-1"]):
            self.assertTrue(c.BAGLAYICI.bul())


class AyristirTesti(unittest.TestCase):
    def test_gercek_bicim(self):
        a = c.ayristir(GERCEK)
        self.assertEqual(a["bes_saat"]["kalan"], 99.7)
        self.assertEqual(a["haftalik"]["kalan"], 100.0)
        self.assertEqual(a["etiketler"], {"bes_saat": "Sohbet · aylık",
                                          "haftalik": "Kod tamamlama · aylık"})
        self.assertEqual(a["bes_saat"]["resets_at"], a["haftalik"]["resets_at"])
        self.assertAlmostEqual(a["bes_saat"]["resets_at"],
                               ortak.zaman_cevir("2026-12-01T00:00:00Z"), delta=1)

    def test_yalniz_tarih_utc_gece_yarisi(self):
        veri = json.loads(json.dumps(GERCEK))
        del veri["quota_reset_date_utc"]
        a = c.ayristir(veri)
        self.assertEqual(a["bes_saat"]["resets_at"],
                         datetime(2026, 12, 1, tzinfo=timezone.utc).timestamp())

    def test_eksi_entitlement_secilmez(self):
        veri = {"quota_snapshots": {
            "premium_interactions": {"percent_remaining": 10.0, "entitlement": -1, "unlimited": False},
            "chat": {"percent_remaining": 55.0, "entitlement": 100, "unlimited": False}}}
        a = c.ayristir(veri)
        self.assertEqual(a["bes_saat"]["kalan"], 55.0)
        self.assertNotIn("haftalik", a)

    def test_ucretli(self):
        a = c.ayristir(UCRETLI)
        self.assertEqual(a["bes_saat"]["kalan"], 40.0)
        self.assertNotIn("haftalik", a)
        self.assertEqual(a["etiketler"], {"bes_saat": "Premium istek · aylık"})

    def test_hepsi_sinirsiz(self):
        with self.assertRaises(c.CopilotHatasi):
            c.ayristir(HEPSI_SINIRSIZ)

    def test_kota_yok(self):
        with self.assertRaises(c.CopilotHatasi):
            c.ayristir({"copilot_plan": "x"})


class YenileTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.TemporaryDirectory()
        self.yol = os.path.join(self.klasor.name, "durum.json")
        self.gh = mock.patch.object(c, "gh_komutu", return_value="gh")
        self.gh.start()

    def tearDown(self):
        self.gh.stop()
        self.klasor.cleanup()

    def test_yazar_ve_gizli_alan_yok(self):
        with mock.patch.object(c.subprocess, "run", return_value=sahte(json.dumps(GERCEK))):
            ok, mesaj = c.BAGLAYICI.yenile(self.yol)
        self.assertTrue(ok)
        self.assertEqual(mesaj, "Copilot limitleri yenilendi")
        with open(self.yol, encoding="utf-8") as f:
            ham = f.read()
        self.assertNotIn("GIZLI", ham)
        self.assertNotIn("endpoints", ham)
        b = json.loads(ham)["copilot"]
        self.assertEqual(b["kaynak"], "Otomatik (gh)")
        self.assertEqual(b["bes_saat"]["kalan"], 99.7)

    def test_eski_haftalik_silinir(self):
        ortak.yaz({"surum": 1, "copilot": {"haftalik": {"kalan": 50, "resets_at": 1},
                                           "etiketler": {"haftalik": "Eski"}}}, self.yol)
        with mock.patch.object(c.subprocess, "run", return_value=sahte(json.dumps(UCRETLI))):
            ok, _ = c.BAGLAYICI.yenile(self.yol)
        self.assertTrue(ok)
        b = ortak.oku(self.yol)["copilot"]
        self.assertNotIn("haftalik", b)
        self.assertEqual(b["bes_saat"]["kalan"], 40.0)
        self.assertNotIn("haftalik", b["etiketler"])

    def test_cikis_kodu_1(self):
        ortak.yaz({"surum": 1, "copilot": {"bes_saat": {"kalan": 7}}}, self.yol)
        with open(self.yol, encoding="utf-8") as f:
            once = f.read()
        with mock.patch.object(c.subprocess, "run",
                               return_value=sahte("", 1, "not logged in\nikinci")):
            ok, mesaj = c.BAGLAYICI.yenile(self.yol)
        self.assertFalse(ok)
        self.assertIn("GitHub girişi yok", mesaj)
        self.assertNotIn("ikinci", mesaj)
        with open(self.yol, encoding="utf-8") as f:
            self.assertEqual(f.read(), once)

    def test_stderr_sizmaz(self):
        ham = "https://proxy.ornek.local kullanici:sifre"
        with mock.patch.object(c.subprocess, "run", return_value=sahte("", 1, ham)):
            ok, mesaj = c.BAGLAYICI.yenile(self.yol)
        self.assertFalse(ok)
        self.assertNotIn("proxy", mesaj)
        self.assertNotIn("sifre", mesaj)
        self.assertIn("gh hatası (çıkış kodu 1)", mesaj)

    def test_http_hata_eslemeleri(self):
        for stderr, beklenen in (("gh: HTTP 401: Bad credentials", "GitHub izin vermedi (401/403)"),
                                 ("HTTP 403 forbidden", "GitHub izin vermedi (401/403)"),
                                 ("gh: Not Found (HTTP 404)", "Copilot bilgisi bulunamadı (404)"),
                                 ("dial: could not resolve host", "ağ hatası")):
            with mock.patch.object(c.subprocess, "run", return_value=sahte("", 1, stderr)):
                _, mesaj = c.BAGLAYICI.yenile(self.yol)
            self.assertIn(beklenen, mesaj)

    def test_komut_ve_parametreler(self):
        with mock.patch.object(c.subprocess, "run",
                               return_value=sahte(json.dumps(GERCEK))) as mock_run:
            c.sorgula(7)
        args, kw = mock_run.call_args
        self.assertEqual(args[0], ["gh", "api", "copilot_internal/user"])
        self.assertEqual(kw["timeout"], 7)
        self.assertEqual(kw["encoding"], "utf-8")
        self.assertEqual(kw["errors"], "replace")
        self.assertIs(kw["stdin"], subprocess.DEVNULL)
        if os.name == "nt":
            self.assertEqual(kw["creationflags"], c.CREATE_NO_WINDOW)

    def test_tek_yazim(self):
        with mock.patch.object(c.subprocess, "run", return_value=sahte(json.dumps(UCRETLI))), \
             mock.patch.object(c.ortak, "yaz", wraps=ortak.yaz) as yaz:
            ok, _ = c.BAGLAYICI.yenile(self.yol)
        self.assertTrue(ok)
        self.assertEqual(yaz.call_count, 1)

    def test_yazma_basarisiz(self):
        with mock.patch.object(c.subprocess, "run", return_value=sahte(json.dumps(UCRETLI))), \
             mock.patch.object(c.ortak, "yaz", return_value=False):
            ok, mesaj = c.BAGLAYICI.yenile(self.yol)
        self.assertFalse(ok)
        self.assertIn("yazılamadı", mesaj)

    def test_baska_arac_bolumu_korunur(self):
        claude = {"kaynak": "otomatik", "bes_saat": {"kalan": 12.0, "resets_at": 5}}
        ortak.yaz({"surum": 1, "claude": claude}, self.yol)
        with mock.patch.object(c.subprocess, "run", return_value=sahte(json.dumps(GERCEK))):
            ok, _ = c.BAGLAYICI.yenile(self.yol)
        self.assertTrue(ok)
        self.assertEqual(ortak.oku(self.yol)["claude"], claude)

    def test_zaman_asimi(self):
        with mock.patch.object(c.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("gh", 10)):
            ok, mesaj = c.BAGLAYICI.yenile(self.yol)
        self.assertFalse(ok)
        self.assertIn("Copilot okunamadı", mesaj)
        self.assertFalse(os.path.exists(self.yol))

    def test_json_degil(self):
        with mock.patch.object(c.subprocess, "run", return_value=sahte("<html>")):
            ok, _ = c.BAGLAYICI.yenile(self.yol)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
