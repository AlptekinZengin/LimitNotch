"""ilk_kurulum.py testleri."""
import os
import tkinter as tk
import unittest

os.environ["LIMITNOTCH_DIL"] = "tr"
import ilk_kurulum
from baglayicilar import taban


def _sahte(kimlik, durum=taban.KARARLI, bulunur=True):
    class Sahte(taban.Baglayici):
        pass

    s = Sahte()
    s.kimlik = kimlik
    s.ad = kimlik.title()
    s.durum = durum
    s.okuma_yolu = f"{kimlik} okuma yolu"
    s.bul = lambda: bulunur
    return s


class VarsayilanSecimTesti(unittest.TestCase):
    def setUp(self):
        self.liste = [_sahte("a"), _sahte("b", taban.DENEYSEL), _sahte("c")]

    def test_onceki_yok_kararlilar(self):
        self.assertEqual(ilk_kurulum.varsayilan_secim(self.liste), ["a", "c"])

    def test_onceki_var_yalniz_bulunanlardaki_onceki(self):
        self.assertEqual(ilk_kurulum.varsayilan_secim(self.liste, ["b", "yok", "a"]), ["a", "b"])
        self.assertEqual(ilk_kurulum.varsayilan_secim(self.liste, []), [])

    def test_deneysel_varsayilan_secili_degil(self):
        self.assertNotIn("b", ilk_kurulum.varsayilan_secim(self.liste))


class PencereTesti(unittest.TestCase):
    def setUp(self):
        try:
            self.kok = tk.Tk()
        except tk.TclError as h:
            self.skipTest(f"Tk açılamadı: {h}")
        self.kok.withdraw()
        self.addCleanup(self._temizle)
        self.liste = [_sahte("a"), _sahte("b", taban.DENEYSEL), _sahte("c", bulunur=False)]
        self.pencereler = []

    def _temizle(self):
        for p in self.pencereler:
            try:
                p.pencere.destroy()
            except tk.TclError:
                pass
        try:
            self.kok.destroy()
        except tk.TclError:
            pass

    def _yeni(self, liste=None, onceki=None):
        p = ilk_kurulum._Pencere(self.kok, self.liste if liste is None else liste, onceki)
        self.pencereler.append(p)
        return p

    def test_hepsini_bagla(self):
        p = self._yeni()
        self.assertEqual([b.kimlik for b in p.bulunan], ["a", "b"])
        self.assertEqual([b.kimlik for b in p.bulunmayan], ["c"])
        p.hepsini_bagla()
        self.assertEqual(p.sonuc, ["a", "b"])

    def test_secilenleri_bagla(self):
        p = self._yeni()
        self.assertTrue(p.degiskenler["a"].get())
        self.assertFalse(p.degiskenler["b"].get())  # deneysel varsayılan seçili değil
        p.degiskenler["a"].set(False)
        p.degiskenler["b"].set(True)
        p.secilenleri_bagla()
        self.assertEqual(p.sonuc, ["b"])

    def test_hic_isaretli_yokken_dugme_pasif(self):
        p = self._yeni(onceki=[])
        self.assertEqual(str(p.secilenler_dugmesi.cget("state")), "disabled")
        p.degiskenler["a"].set(True)
        self.assertEqual(str(p.secilenler_dugmesi.cget("state")), "normal")

    def test_vazgec(self):
        p = self._yeni()
        p.vazgec()
        self.assertIsNone(p.sonuc)

    def test_hic_arac_bulunamazsa_kapat(self):
        p = self._yeni([_sahte("a", bulunur=False), _sahte("b", bulunur=False)])
        self.assertEqual(p.bulunan, [])
        self.assertIsNone(p.secilenler_dugmesi)
        p.vazgec()
        self.assertIsNone(p.sonuc)

    def test_bul_istisna_atarsa_bulunamadi_sayilir(self):
        k = _sahte("a")

        def patla():
            raise RuntimeError("x")

        k.bul = patla
        p = self._yeni([k, _sahte("b")])
        self.assertEqual([b.kimlik for b in p.bulunan], ["b"])

    def test_onceki_secimde_olup_bulunamayan_isaretli_gelir(self):
        p = self._yeni(onceki=["c"])
        self.assertEqual([b.kimlik for b in p.bulunan], ["a", "b", "c"])
        self.assertEqual(p.bulunmayan, [])
        self.assertTrue(p.degiskenler["c"].get())
        self.assertFalse(p.degiskenler["a"].get())
        p.hepsini_bagla()
        self.assertEqual(p.sonuc, ["a", "b", "c"])

    def test_aday_yokken_yalniz_kapat(self):
        p = self._yeni([_sahte("a", bulunur=False)])
        duğmeler = []

        def tara(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Button):
                    duğmeler.append(c.cget("text"))
                tara(c)

        tara(p.pencere)
        self.assertEqual(duğmeler, ["Kapat"])

    def test_hic_kutu_isaretli_degilken_secilenleri_bagla_kapatmaz(self):
        p = self._yeni()
        for v in p.degiskenler.values():
            v.set(False)
        p.secilenleri_bagla()
        self.assertIsNone(p.sonuc)
        self.assertTrue(p.pencere.winfo_exists())

    def test_sec_ana_ile(self):
        yakalanan = []
        asil = ilk_kurulum._Pencere

        class Yakalayici(asil):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                yakalanan.append(self)

        self.kok.after(300, lambda: yakalanan[0].hepsini_bagla())
        ilk_kurulum._Pencere = Yakalayici
        try:
            sonuc = ilk_kurulum.sec(ana=self.kok, baglayicilar_listesi=self.liste)
        finally:
            ilk_kurulum._Pencere = asil
        self.assertEqual(sonuc, ["a", "b"])
        self.assertEqual(int(yakalanan[0].pencere.winfo_exists()), 0)

    def test_sec_ana_none_gizli_koku_yok_eder(self):
        onceki_kok = tk._default_root
        yakalanan = []
        asil = ilk_kurulum._Pencere

        class Yakalayici(asil):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                yakalanan.append(self)
                self.ana.after(300, self.hepsini_bagla)

        ilk_kurulum._Pencere = Yakalayici
        try:
            sonuc = ilk_kurulum.sec(baglayicilar_listesi=[_sahte("a")])
        finally:
            ilk_kurulum._Pencere = asil
        self.assertEqual(sonuc, ["a"])
        self.assertIsNot(tk._default_root, yakalanan[0].ana)
        self.assertIs(tk._default_root, onceki_kok if onceki_kok is not self.kok else self.kok)


if __name__ == "__main__":
    unittest.main()
