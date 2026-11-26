"""yenileyici.py antigravity birim testleri (sahte JSON/hub dosyaları; ağ ve gerçek ev dizini yok)."""
import json
import os
import sys
import tempfile
import time
import unittest

os.environ["LIMITNOTCH_DIL"] = "tr"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yenileyici as y  # noqa: E402
import durum_ortak as ortak  # noqa: E402

OZET = {"response": {"groups": [
    {"displayName": "Gemini Models", "buckets": [
        {"bucketId": "gemini-weekly", "window": "weekly", "remainingFraction": 0.67,
         "resetTime": "2026-12-02T12:08:36Z"},
        {"bucketId": "gemini-5h", "window": "5h", "remainingFraction": 0.40,
         "resetTime": "2026-11-25T23:15:10Z"}]},
    {"displayName": "Claude and GPT models", "buckets": [
        {"bucketId": "3p-weekly", "window": "weekly", "remainingFraction": 1},
        {"bucketId": "3p-5h", "window": "5h", "remainingFraction": 1}]}]}}

DURUM = {"userStatus": {"cascadeModelConfigData": {"clientModelConfigs": [
    {"label": "Gemini 4 Neon (High)",
     "quotaInfo": {"remainingFraction": 0.40, "resetTime": "2026-11-25T23:15:10Z"}},
    {"label": "Claude Sonnet 5.5 (High)",
     "quotaInfo": {"remainingFraction": 1, "resetTime": "2026-11-26T01:29:02Z"}}]}}}


class TestAyristir(unittest.TestCase):
    def test_ozet_ana_grup_gemini_diger_gruplar_ayri(self):
        a = y.antigravity_ayristir(OZET)
        self.assertEqual(a["bes_saat"]["kalan"], 40.0)
        self.assertEqual(a["bes_saat"]["grup"], "Gemini")
        self.assertEqual(a["haftalik"]["kalan"], 67.0)
        self.assertEqual(a["haftalik"]["grup"], "Gemini")
        self.assertAlmostEqual(a["haftalik"]["resets_at"],
                               ortak.zaman_cevir("2026-12-02T12:08:36Z"))
        self.assertEqual(a["etiketler"], {"bes_saat": "5 Saatlik · Gemini (Neon)",
                                          "haftalik": "Haftalık · Gemini (Neon)"})
        self.assertEqual(a["diger_gruplar"],
                         {"Claude/GPT": {"bes_saat": 100.0, "haftalik": 100.0}})

    def test_claude_grubu_daha_azsa_bile_gemini_ana_kalir(self):
        v = json.loads(json.dumps(OZET))
        v["response"]["groups"][1]["buckets"][0]["remainingFraction"] = 0.2
        a = y.antigravity_ayristir(v)
        self.assertEqual(a["haftalik"]["grup"], "Gemini")
        self.assertEqual(a["haftalik"]["kalan"], 67.0)
        self.assertEqual(a["diger_gruplar"]["Claude/GPT"]["haftalik"], 20.0)

    def test_yalniz_claude_gpt_eski_davranis_etiket_yok(self):
        v = {"response": {"groups": [OZET["response"]["groups"][1]]}}
        a = y.antigravity_ayristir(v)
        self.assertEqual(a["bes_saat"]["grup"], "Claude/GPT")
        self.assertEqual(a["bes_saat"]["kalan"], 100.0)
        self.assertEqual(a["etiketler"], {})
        self.assertEqual(a["diger_gruplar"], {})

    def test_ana_grup_pencerede_yoksa_en_az_grup(self):
        v = json.loads(json.dumps(OZET))
        v["response"]["groups"][0]["buckets"] = [v["response"]["groups"][0]["buckets"][1]]  # yalnız 5h
        v["response"]["groups"][1]["buckets"][0]["remainingFraction"] = 0.2
        a = y.antigravity_ayristir(v)
        self.assertEqual(a["bes_saat"]["grup"], "Gemini")
        self.assertEqual(a["haftalik"]["grup"], "Claude/GPT")
        self.assertEqual(a["haftalik"]["kalan"], 20.0)
        self.assertEqual(set(a["etiketler"]), {"bes_saat"})
        self.assertIsNone(a["diger_gruplar"]["Claude/GPT"].get("yok"))

    def test_user_status_yedegi_yalniz_bes_saat(self):
        a = y.antigravity_ayristir(DURUM)
        self.assertEqual(set(a), {"bes_saat", "etiketler", "diger_gruplar"})
        self.assertEqual(a["bes_saat"]["kalan"], 40.0)
        self.assertEqual(a["bes_saat"]["grup"], "Gemini")
        self.assertEqual(set(a["etiketler"]), {"bes_saat"})
        self.assertEqual(a["diger_gruplar"], {"Claude/GPT": {"bes_saat": 100.0, "haftalik": None}})

    def test_bos_ve_gecersiz(self):
        for v in ({}, [], None, {"response": {"groups": []}}):
            with self.assertRaises(y.AntigravityHatasi):
                y.antigravity_ayristir(v)


class TestYenile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.yol = os.path.join(self.tmp.name, "durum.json")

    def test_basari_yazar(self):
        ortak.guncelle("antigravity", {"haftalik": {"kalan": 81.0, "resets_at": 5}}, self.yol)
        ok, _ = y.yenile_antigravity(self.yol, sorgu=lambda: OZET)
        self.assertTrue(ok)
        b = ortak.oku(self.yol)["antigravity"]
        self.assertEqual(b["kaynak"], y.ANTIGRAVITY_KAYNAK)
        self.assertEqual(b["bes_saat"]["kalan"], 40.0)
        self.assertEqual(b["haftalik"]["kalan"], 67.0)

    def test_haftalik_yoksa_eskisi_kalir(self):
        ortak.guncelle("antigravity", {"haftalik": {"kalan": 81.0, "resets_at": 5}}, self.yol)
        ok, mesaj = y.yenile_antigravity(self.yol, sorgu=lambda: DURUM)
        self.assertTrue(ok)
        self.assertIn("haftalık alınamadı", mesaj)
        b = ortak.oku(self.yol)["antigravity"]
        self.assertEqual(b["haftalik"]["kalan"], 81.0)
        self.assertEqual(b["bes_saat"]["kalan"], 40.0)

    def test_baglanti_hatasi_false_ve_veri_korunur(self):
        ortak.guncelle("antigravity", {"bes_saat": {"kalan": 55.0, "resets_at": 5}}, self.yol)

        def bozuk():
            raise y.AntigravityHatasi("ConnectionRefusedError")
        ok, mesaj = y.yenile_antigravity(self.yol, sorgu=bozuk)
        self.assertFalse(ok)
        self.assertIn("mevcut veri korundu", mesaj)
        self.assertEqual(ortak.oku(self.yol)["antigravity"]["bes_saat"]["kalan"], 55.0)

    def test_kapali_hatasi_mesaji_birebir(self):
        ortak.guncelle("antigravity", {"bes_saat": {"kalan": 55.0, "resets_at": 5}}, self.yol)

        def kapali():
            raise y.AntigravityHatasi("Antigravity kapalı (çalışan dil sunucusu yok)")
        ok, mesaj = y.yenile_antigravity(self.yol, sorgu=kapali)
        self.assertFalse(ok)
        self.assertEqual(mesaj, "Antigravity kapalı · açılınca kendiliğinden okunur")
        self.assertEqual(ortak.oku(self.yol)["antigravity"]["bes_saat"]["kalan"], 55.0)

    def test_eski_diger_gruplar_ve_etiketler_tamamen_degisir(self):
        ortak.guncelle("antigravity", {"diger_gruplar": {"Eski": {"bes_saat": 1.0}},
                                       "etiketler": {"haftalik": "eski"}}, self.yol)
        ok, _ = y.yenile_antigravity(self.yol, sorgu=lambda: OZET)
        self.assertTrue(ok)
        b = ortak.oku(self.yol)["antigravity"]
        self.assertEqual(set(b["diger_gruplar"]), {"Claude/GPT"})
        self.assertEqual(b["etiketler"]["haftalik"], "Haftalık · Gemini (Neon)")

    def test_beklenmeyen_hata_false(self):
        ok, _ = y.yenile_antigravity(self.yol, sorgu=lambda: 1 / 0)
        self.assertFalse(ok)


class TestSorgula(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _hub(self, ad, port, mtime):
        yol = os.path.join(self.tmp.name, ad)
        with open(yol, "w") as f:
            json.dump({"httpPort": port, "csrfToken": "sahte"}, f)
        os.utime(yol, (mtime, mtime))
        return yol

    def test_hub_sirasi_en_yeni_once(self):
        self._hub("hub_1.json", 1, 100)
        self._hub("hub_2.json", 2, 300)
        self._hub("hub_3.json", 3, 200)
        sira = [os.path.basename(f) for f in y.antigravity_hub_dosyalari(
            os.path.join(self.tmp.name, "hub_*.json"))]
        self.assertEqual(sira, ["hub_2.json", "hub_3.json", "hub_1.json"])

    def test_olu_hub_atlanir_canli_kullanilir(self):
        d = [self._hub("hub_a.json", 11, 300), self._hub("hub_b.json", 22, 200),
             self._hub("hub_c.json", 33, 100)]
        denenen = []

        def rpc(port, csrf, yontem, zaman):
            denenen.append(port)
            if port != 22:
                raise ConnectionRefusedError()
            return OZET
        self.assertEqual(y.antigravity_sorgula(hub_dosyalari=d, rpc=rpc), OZET)
        self.assertEqual(denenen, [11, 22])

    def test_ozet_olmazsa_user_status(self):
        d = [self._hub("hub_a.json", 11, 300)]

        def rpc(port, csrf, yontem, zaman):
            if yontem == "RetrieveUserQuotaSummary":
                raise ValueError("bozuk")
            return DURUM
        self.assertEqual(y.antigravity_sorgula(hub_dosyalari=d, rpc=rpc), DURUM)

    def test_hepsi_olu_hata(self):
        d = [self._hub("hub_a.json", 11, 300), self._hub("hub_b.json", 22, 200)]

        def rpc(*a):
            raise ConnectionRefusedError()
        with self.assertRaises(y.AntigravityHatasi):
            y.antigravity_sorgula(hub_dosyalari=d, rpc=rpc)

    def test_hub_yoksa_hata(self):
        with self.assertRaises(y.AntigravityHatasi):
            y.antigravity_sorgula(hub_dosyalari=[], rpc=lambda *a: OZET)


class TestSurecKontrol(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _hub(self, ad, port, mtime, pid=None):
        yol = os.path.join(self.tmp.name, ad)
        veri = {"httpPort": port, "csrfToken": "sahte"}
        if pid is not None:
            veri["pid"] = pid
        with open(yol, "w") as f:
            json.dump(veri, f)
        os.utime(yol, (mtime, mtime))
        return yol

    def test_olu_pidler_atlanir_yalniz_canli_denenir(self):
        d = [self._hub(f"hub_{i}.json", 100 + i, 500 - i, pid=1000 + i) for i in range(5)]
        d.append(self._hub("hub_canli.json", 777, 10, pid=9))
        denenen = []

        def rpc(port, csrf, yontem, zaman):
            denenen.append(port)
            return OZET
        self.assertEqual(y.antigravity_sorgula(hub_dosyalari=d, rpc=rpc,
                                               surec_kontrol=lambda pid: pid == 9), OZET)
        self.assertEqual(denenen, [777])

    def test_hepsi_olu_hemen_hata_rpc_cagrilmaz(self):
        d = [self._hub(f"hub_{i}.json", 100 + i, 500 - i, pid=1000 + i) for i in range(6)]
        cagri = []
        b = time.time()
        with self.assertRaises(y.AntigravityHatasi) as c:
            y.antigravity_sorgula(hub_dosyalari=d, rpc=lambda *a: cagri.append(a),
                                  surec_kontrol=lambda pid: False)
        self.assertLess(time.time() - b, 0.5)
        self.assertEqual(cagri, [])
        self.assertIn("kapalı", str(c.exception))

    def test_pid_olmayan_hub_eskisi_gibi_denenir(self):
        d = [self._hub("hub_a.json", 11, 300)]
        denenen = []

        def rpc(port, csrf, yontem, zaman):
            denenen.append(port)
            return OZET
        self.assertEqual(y.antigravity_sorgula(hub_dosyalari=d, rpc=rpc,
                                               surec_kontrol=lambda pid: None), OZET)
        self.assertEqual(denenen, [11])

    def test_uc_canli_en_cok_ikisi_denenir(self):
        d = [self._hub(f"hub_{i}.json", 10 + i, 500 - i, pid=50 + i) for i in range(3)]
        denenen = []

        def rpc(port, csrf, yontem, zaman):
            denenen.append(port)
            raise ConnectionRefusedError()
        with self.assertRaises(y.AntigravityHatasi):
            y.antigravity_sorgula(hub_dosyalari=d, rpc=rpc, surec_kontrol=lambda pid: True)
        self.assertEqual(denenen, [10, 11])

    def _ad_ile(self, ad):
        eski = y.surec_adi
        y.surec_adi = lambda pid: ad
        self.addCleanup(setattr, y, "surec_adi", eski)
        y.surec_calisiyor_mu_eski = y.surec_calisiyor_mu
        y.surec_calisiyor_mu = lambda pid: True
        self.addCleanup(setattr, y, "surec_calisiyor_mu", y.surec_calisiyor_mu_eski)

    def test_canli_ama_cmd_exe_olu_sayilir_rpc_yok(self):
        self._ad_ile("cmd.exe")
        self.assertIs(y.antigravity_sureci_mi(3320), False)
        d = [self._hub("hub_x.json", 11, 300, pid=3320)]
        cagri = []
        with self.assertRaises(y.AntigravityHatasi):
            y.antigravity_sorgula(hub_dosyalari=d, rpc=lambda *a: cagri.append(a))
        self.assertEqual(cagri, [])
        self.assertIsNone(y.antigravity_canli_pid(d))

    def test_language_server_canli(self):
        self._ad_ile("language_server.exe")
        self.assertIs(y.antigravity_sureci_mi(3320), True)

    def test_ad_alinamazsa_canli(self):
        self._ad_ile(None)
        self.assertIs(y.antigravity_sureci_mi(3320), True)

    def test_antigravity_sureci_mi_gercek_python_false(self):
        self.assertIs(y.antigravity_sureci_mi(os.getpid()), False if os.name == "nt" else True)

    def test_surec_calisiyor_mu_gercek(self):
        self.assertIs(y.surec_calisiyor_mu(os.getpid()), True)
        self.assertIsNone(y.surec_calisiyor_mu(-1))
        self.assertIsNone(y.surec_calisiyor_mu(0))
        self.assertIsNone(y.surec_calisiyor_mu("12"))
        self.assertIn(y.surec_calisiyor_mu(4_000_000), (False, None))


class TestCanliPid(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _hub(self, ad, mtime, icerik):
        yol = os.path.join(self.tmp.name, ad)
        with open(yol, "w") as f:
            f.write(icerik if isinstance(icerik, str) else json.dumps(icerik))
        os.utime(yol, (mtime, mtime))
        return yol

    def test_olu_ve_canli_karisik_canlinin_pidi(self):
        d = [self._hub("hub_a.json", 300, {"pid": 11}), self._hub("hub_b.json", 200, {"pid": 22}),
             self._hub("hub_c.json", 100, {"pid": 33})]
        self.assertEqual(y.antigravity_canli_pid(d, lambda pid: pid == 22), 22)

    def test_hepsi_olu_none(self):
        d = [self._hub("hub_a.json", 300, {"pid": 11}), self._hub("hub_b.json", 200, {"pid": 22})]
        self.assertIsNone(y.antigravity_canli_pid(d, lambda pid: False))
        self.assertIsNone(y.antigravity_canli_pid([], lambda pid: True))

    def test_bozuk_json_atlanir(self):
        d = [self._hub("hub_a.json", 300, "{bozuk"), self._hub("hub_b.json", 200, {"pid": 5}),
             os.path.join(self.tmp.name, "yok.json")]
        self.assertEqual(y.antigravity_canli_pid(d, lambda pid: True), 5)

    def test_sorgu_istisnasi_yutulur(self):
        d = [self._hub("hub_a.json", 300, {"pid": 1}), self._hub("hub_b.json", 200, {"pid": 2})]

        def kontrol(pid):
            if pid == 1:
                raise RuntimeError("x")
            return True
        self.assertEqual(y.antigravity_canli_pid(d, kontrol), 2)


if __name__ == "__main__":
    unittest.main()
