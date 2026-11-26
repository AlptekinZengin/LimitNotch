"""otomatik.py birim testleri (zaman ve pil durumu enjekte edilir; gercek bekleme yok)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import otomatik as o  # noqa: E402

A = ["claude", "codex", "antigravity"]


class Test(unittest.TestCase):
    def kur(self, pilde=False):
        self.t = [1000.0]
        self.pil = [pilde]
        return o.OtomatikPlan(zaman=lambda: self.t[0], pilde_mi=lambda: self.pil[0])

    def test_ilk_cagri_hepsi_vadeli(self):
        self.assertEqual(self.kur().vadesi_gelenler(A), A)

    def test_basari_sonrasi_300(self):
        p = self.kur()
        p.sonuc_bildir("claude", True, 1000)
        self.assertNotIn("claude", p.vadesi_gelenler(A, 1299))
        self.assertIn("claude", p.vadesi_gelenler(A, 1300))

    def test_pilde_900(self):
        p = self.kur(pilde=True)
        p.sonuc_bildir("claude", True, 1000)
        self.assertNotIn("claude", p.vadesi_gelenler(A, 1899))
        self.assertIn("claude", p.vadesi_gelenler(A, 1900))

    def test_geri_cekilme(self):
        for hata, aralik in [(1, 300), (2, 600), (3, 1200), (5, 1800)]:
            p = self.kur()
            for _ in range(hata):
                p.sonuc_bildir("codex", False, 1000)
            self.assertEqual(p.hata_sayisi("codex"), hata)
            self.assertNotIn("codex", p.vadesi_gelenler(A, 1000 + aralik - 1))
            self.assertIn("codex", p.vadesi_gelenler(A, 1000 + aralik))

    def test_pilde_geri_cekilme_pil_altina_inmez(self):
        p = self.kur(pilde=True)
        p.sonuc_bildir("codex", False, 1000)
        self.assertNotIn("codex", p.vadesi_gelenler(A, 1899))
        self.assertIn("codex", p.vadesi_gelenler(A, 1900))

    def test_basari_sayaci_sifirlar(self):
        p = self.kur()
        p.sonuc_bildir("claude", False, 1000)
        p.sonuc_bildir("claude", False, 1100)
        p.sonuc_bildir("claude", True, 1200)
        self.assertEqual(p.hata_sayisi("claude"), 0)
        self.assertEqual(p.son_deneme("claude"), 1200)
        self.assertIn("claude", p.vadesi_gelenler(A, 1500))

    def test_surerken_dondurulmez(self):
        p = self.kur()
        p.basladi("claude")
        self.assertEqual(p.vadesi_gelenler(A), ["codex", "antigravity"])
        p.sonuc_bildir("claude", True, 1000)
        self.assertNotIn("claude", p.vadesi_gelenler(A, 1100))

    def test_sira_korunur(self):
        p = self.kur()
        self.assertEqual(p.vadesi_gelenler(["antigravity", "claude"]), ["antigravity", "claude"])

    def test_son_deneme_yok(self):
        self.assertIsNone(self.kur().son_deneme("claude"))
        self.assertEqual(self.kur().hata_sayisi("claude"), 0)

    def test_pilde_mi_gercek(self):
        self.assertIsInstance(o.pilde_mi(), bool)


if __name__ == "__main__":
    unittest.main()
