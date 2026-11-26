"""durum_ortak.KILIT: eşzamanlı guncelle çağrıları birbirinin bölümünü ezmemeli."""
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import durum_ortak as ortak  # noqa: E402


class TestKilit(unittest.TestCase):
    def test_sekiz_is_parcacigi_bolum_kaybetmez(self):
        with tempfile.TemporaryDirectory() as tmp:
            yol = os.path.join(tmp, "durum.json")
            gercek_oku = ortak.oku

            def yavas_oku(*a, **k):
                v = gercek_oku(*a, **k)
                time.sleep(0.001)
                return v

            def is_(i):
                for n in range(20):
                    ortak.guncelle(f"arac{i}", {"sayac": n}, yol)

            with mock.patch.object(ortak, "oku", side_effect=yavas_oku):
                ts = [threading.Thread(target=is_, args=(i,)) for i in range(8)]
                for t in ts:
                    t.start()
                for t in ts:
                    t.join()
            veri = gercek_oku(yol)
            for i in range(8):
                self.assertIn(f"arac{i}", veri)
                self.assertEqual(veri[f"arac{i}"]["sayac"], 19)


if __name__ == "__main__":
    unittest.main()
