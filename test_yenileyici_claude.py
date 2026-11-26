"""yenileyici.py Claude canlı okuma birim testleri (gerçek claude çağrılmaz, sahte çıktı kullanılır)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from unittest import mock

os.environ["LIMITNOTCH_DIL"] = "tr"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import durum_ortak as ortak  # noqa: E402
import yenileyici as y  # noqa: E402

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Europe/Istanbul")
except Exception:  # tzdata yoksa saat dilimli testler atlanır
    IST = None

# `claude -p /usage --output-format json` ile alınan gerçek metin (Claude Code 2.1.332)
GERCEK_METIN = (
    "You are currently using your subscription to power your Claude Code usage\n\n"
    "Current session: 53% used · resets Nov 26, 12:09am (Europe/Istanbul)\n"
    "Current week (all models): 75% used · resets Nov 30, 10:59am (Europe/Istanbul)\n\n"
    "What's contributing to your usage?\nLast 24h · 617 requests · 27 sessions\n"
    "  63%  Start fresh when you switch tasks · run /clear\n"
)


def ist(*a):
    return datetime(*a, tzinfo=IST).timestamp()


@unittest.skipIf(IST is None, "zoneinfo/tzdata yok")
class TestClaudeAyristir(unittest.TestCase):
    def setUp(self):
        self.simdi = ist(2026, 11, 25, 20, 0)

    def test_gercek_cikti(self):
        a = y.claude_ayristir(GERCEK_METIN, self.simdi)
        self.assertEqual(a["bes_saat"], {"kalan": 47.0, "resets_at": ist(2026, 11, 26, 0, 9)})
        self.assertEqual(a["haftalik"], {"kalan": 25.0, "resets_at": ist(2026, 11, 30, 10, 59)})

    def test_yuzde_sinirlanir_ve_ondalik(self):
        a = y.claude_ayristir("Current session: 120% used\nCurrent week: 12.5% used", self.simdi)
        self.assertEqual(a["bes_saat"]["kalan"], 0.0)
        self.assertIsNone(a["bes_saat"]["resets_at"])
        self.assertEqual(a["haftalik"]["kalan"], 87.5)

    def test_yalniz_haftalik_sonnet_satiri_karismaz(self):
        metin = ("Current week (Sonnet only): 10% used · resets Nov 30, 10:59am (Europe/Istanbul)\n"
                 "Current week (all models): 40% used · resets Nov 30, 10:59am (Europe/Istanbul)\n")
        a = y.claude_ayristir(metin, self.simdi)
        self.assertEqual(a["haftalik"]["kalan"], 60.0)
        self.assertNotIn("bes_saat", a)

    def test_limit_satiri_yoksa_hata(self):
        with self.assertRaises(y.ClaudeHatasi):
            y.claude_ayristir("Please run /login", self.simdi)
        with self.assertRaises(y.ClaudeHatasi):
            y.claude_ayristir("", self.simdi)

    def test_reset_saat_bicimleri(self):
        s = self.simdi
        self.assertEqual(y.claude_reset_coz(" · resets 3pm (Europe/Istanbul)", s), ist(2026, 11, 26, 15, 0))
        self.assertEqual(y.claude_reset_coz(" · resets 9:30pm (Europe/Istanbul)", s), ist(2026, 11, 25, 21, 30))
        self.assertEqual(y.claude_reset_coz(" · resets 12am (Europe/Istanbul)", s), ist(2026, 11, 26, 0, 0))
        self.assertEqual(y.claude_reset_coz(" · resets Dec 1 at 12pm (Europe/Istanbul)", s), ist(2026, 12, 1, 12, 0))
        self.assertIsNone(y.claude_reset_coz(" · bilinmeyen", s))

    def test_yil_donumu(self):
        s = ist(2026, 12, 30, 12, 0)
        self.assertEqual(y.claude_reset_coz(" · resets Jan 2, 9am (Europe/Istanbul)", s), ist(2027, 1, 2, 9, 0))


class TestClaudeSorgula(unittest.TestCase):
    def _sonuc(self, stdout=b"", stderr=b"", kod=0):
        return subprocess.CompletedProcess([], kod, stdout, stderr)

    def test_json_result_doner_ve_pencere_acmaz(self):
        cikti = json.dumps({"type": "result", "is_error": False, "result": GERCEK_METIN}).encode("utf-8")
        with mock.patch.object(y.subprocess, "run", return_value=self._sonuc(cikti)) as r:
            self.assertEqual(y.claude_sorgula(komut="claude.exe"), GERCEK_METIN)
        arg, kw = r.call_args
        self.assertEqual(arg[0][:3], ["claude.exe", "-p", "/usage"])
        self.assertIn("--no-session-persistence", arg[0])
        self.assertEqual(kw["stdin"], subprocess.DEVNULL)
        if os.name == "nt":
            self.assertEqual(kw["creationflags"], y.CREATE_NO_WINDOW)

    def test_is_error(self):
        cikti = json.dumps({"is_error": True, "result": "Not logged in"}).encode()
        with mock.patch.object(y.subprocess, "run", return_value=self._sonuc(cikti)):
            with self.assertRaisesRegex(y.ClaudeHatasi, "Not logged in"):
                y.claude_sorgula(komut="claude.exe")

    def test_bayrak_tanimazsa_duz_komutla_tekrar(self):
        iyi = self._sonuc(json.dumps({"result": GERCEK_METIN}).encode())
        kotu = self._sonuc(stderr=b"error: unknown option '--safe-mode'", kod=1)
        with mock.patch.object(y.subprocess, "run", side_effect=[kotu, iyi]) as r:
            self.assertEqual(y.claude_sorgula(komut="claude.exe"), GERCEK_METIN)
        self.assertNotIn("--safe-mode", r.call_args_list[1][0][0])

    def test_zaman_asimi(self):
        with mock.patch.object(y.subprocess, "run", side_effect=subprocess.TimeoutExpired("c", 1)):
            with self.assertRaisesRegex(y.ClaudeHatasi, "zaman aşımı"):
                y.claude_sorgula(komut="claude.exe")

    def test_komut_yok(self):
        with mock.patch.object(y, "claude_komutu", return_value=None):
            with self.assertRaises(y.ClaudeHatasi):
                y.claude_sorgula()


class TestYenileClaude(unittest.TestCase):
    def setUp(self):
        fd, self.yol = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        veri = ortak.bos_durum()
        veri["claude"] = {"kaynak": "otomatik", "bes_saat": {"kalan": 78, "resets_at": 111.0},
                          "haftalik": {"kalan": 91, "resets_at": 222.0}}
        veri["codex"] = {"kaynak": "elle", "bes_saat": {"kalan": 5}}
        ortak.yaz(veri, self.yol)

    def tearDown(self):
        os.remove(self.yol)

    def test_basarili_yazar(self):
        ok, mesaj = y.yenile_claude(self.yol, sorgu=lambda: GERCEK_METIN)
        self.assertTrue(ok, mesaj)
        veri = ortak.oku(self.yol)
        c = veri["claude"]
        self.assertEqual(c["kaynak"], y.CLAUDE_KAYNAK)
        self.assertEqual(c["bes_saat"]["kalan"], 47.0)
        self.assertEqual(c["haftalik"]["kalan"], 25.0)
        self.assertIsNotNone(c["bes_saat"]["resets_at"])
        self.assertEqual(veri["codex"]["bes_saat"]["kalan"], 5)  # başka araca dokunmaz

    def test_hata_veriyi_korur(self):
        onceki = ortak.oku(self.yol)

        def hatali():
            raise y.ClaudeHatasi("zaman aşımı (25 sn)")

        ok, mesaj = y.yenile_claude(self.yol, sorgu=hatali)
        self.assertFalse(ok)
        self.assertIn("zaman aşımı", mesaj)
        self.assertEqual(ortak.oku(self.yol), onceki)

    def test_beklenmeyen_cikti_veriyi_korur(self):
        onceki = ortak.oku(self.yol)
        ok, _ = y.yenile_claude(self.yol, sorgu=lambda: None)
        self.assertFalse(ok)
        self.assertEqual(ortak.oku(self.yol), onceki)

    def test_yenile_kayit_tablosu_modul_fonksiyonunu_kullanir(self):
        with mock.patch.object(y, "claude_sorgula", return_value=GERCEK_METIN):
            self.assertEqual(y.yenile("claude", self.yol), (True, "Claude limitleri yenilendi"))


if __name__ == "__main__":
    unittest.main()
