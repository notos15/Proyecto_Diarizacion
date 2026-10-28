import unittest

import numpy as np

from evaluar import medir


class EvaluacionTest(unittest.TestCase):
    def test_permutar_etiquetas_no_crea_error(self):
        referencia = np.array([0, 0, -1, 1, 1], dtype=np.int32)
        sistema = np.array([1, 1, -1, 0, 0], dtype=np.int32)
        resultado, estados, _ = medir(referencia, sistema)
        self.assertEqual(resultado["der_pct"], 0)
        self.assertEqual(resultado["confusion_seg"], 0)
        self.assertEqual(list(estados), [1, 1, 0, 1, 1])

    def test_omision_y_falsa_alarma(self):
        referencia = np.array([0, 0, -1, -1], dtype=np.int32)
        sistema = np.array([0, -1, 0, -1], dtype=np.int32)
        resultado, _, _ = medir(referencia, sistema)
        self.assertEqual(resultado["omision_seg"], 0.01)
        self.assertEqual(resultado["falsa_alarma_seg"], 0.01)
        self.assertEqual(resultado["der_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
