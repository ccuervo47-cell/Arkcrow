"""Generador de APU complementarios en geometría F-14-3-5 (libro sintético del formato UNAD)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "nucleo"))
sys.path.insert(0, str(RAIZ / "tests"))

from arkcrow import apu_unad  # noqa: E402
from arkcrow.recalculo import recalcular  # noqa: E402
from test_auditor_unad import libro  # noqa: E402

SPEC = {
    "titulo": "Prueba", "fuente_supuesto": "SUPUESTO prueba", "prestaciones": 0.94, "herramienta_menor": 0.05,
    "transporte": {"descripcion": "Transporte de materiales", "capacidad_t": 3.5},
    "precios_nuevos": {"EQ": [], "MO": [["Jardinero", 82000]],
                       "MAT": [["Tierra negra puesta en obra", "m3", 85000, "incluido"], ["Abono", "kg", 1500, 0.001]]},
    "pesos_existentes": {"Adoquín de concreto 20x10x6": 0.0028},
    "apus": [{"item": "2.3", "eq": [], "mat": [["Tierra negra puesta en obra", 0.11], ["Abono", 0.5]],
              "mo": [["Jardinero", 50]], "nota": "espesor 0,10 m"},
             {"item": "2.1", "eq": [], "mat": [["Adoquín de concreto 20x10x6", 50]], "mo": [["Oficial de obra", 20]]}],
}


class TestApuUnad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        oficial = libro(cls.tmp / "oficial.xlsx")
        salida = apu_unad.construir(oficial, SPEC, cls.tmp / "comp.xlsx")
        from openpyxl import load_workbook
        cls.wv = load_workbook(recalcular(salida), data_only=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_apu_calcula_con_herramienta_menor_y_transporte(self):
        ws = self.wv["2.3"]
        jornal = 82000 * 1.94
        mo = round(jornal / 50, 2)
        self.assertAlmostEqual(ws["M81"].value, mo, places=1)
        self.assertAlmostEqual(ws["M37"].value, round(0.05 * mo, 2), places=1)
        self.assertAlmostEqual(ws["M61"].value, 0.11 * 85000 + 0.5 * 1500, places=1)
        self.assertAlmostEqual(ws["H66"].value, 0.5 * 0.001 / 3.5, places=6)    # la tierra puesta en obra no suma peso
        self.assertEqual(ws["M85"].value, round(ws["M83"].value))

    def test_resumen_compara_con_balance(self):
        r = self.wv["RESUMEN"]
        fila = next(i for i in range(5, 10) if r[f"B{i}"].value == "2.3")
        self.assertEqual(r[f"F{fila}"].value, 17500)
        self.assertAlmostEqual(r[f"H{fila}"].value, r[f"G{fila}"].value / 17500 - 1, places=6)

    def test_insumo_inexistente_falla(self):
        malo = {**SPEC, "apus": [{"item": "2.3", "eq": [], "mat": [["No existe", 1]], "mo": []}]}
        with self.assertRaises(KeyError):
            apu_unad.construir(self.tmp / "oficial.xlsx", malo, self.tmp / "x.xlsx")


if __name__ == "__main__":
    unittest.main(verbosity=2)
