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

    def test_cotizaciones_reemplazan_supuestos(self):
        from openpyxl import load_workbook
        plantilla = apu_unad.plantilla_cotizaciones(self.tmp / "oficial.xlsx", SPEC, self.tmp / "cot.xlsx")
        wb = load_workbook(plantilla)
        ws = wb["COTIZACIONES"]
        fila = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 2).value == "Abono")
        ws.cell(fila, 6, 2100)
        ws.cell(fila, 7, "Vivero El Prado")
        ws.cell(fila, 8, "05/11/2026")
        wb.save(plantilla)
        spec, avisos = apu_unad.aplicar_cotizaciones(SPEC, plantilla)
        self.assertEqual(spec["cotizaciones"]["Abono"]["precio"], 2100)
        self.assertEqual(avisos, [])
        salida = apu_unad.construir(self.tmp / "oficial.xlsx", spec, self.tmp / "cotizado.xlsx")
        wv = load_workbook(recalcular(salida), data_only=True)
        self.assertAlmostEqual(wv["2.3"]["M61"].value, 0.11 * 85000 + 0.5 * 2100, places=1)

    def test_proceso_de_cotizacion(self):
        from openpyxl import load_workbook
        from arkcrow import cotizaciones
        filas = cotizaciones.necesidades(self.tmp / "oficial.xlsx", SPEC)
        abono = next(f for f in filas if f["insumo"] == "Abono")
        self.assertAlmostEqual(abono["cantidad"], 0.5 * 4000)          # 0,5 kg/m² × 4.000 m² del ítem 2.3
        self.assertEqual(abono["categoria"], "Vivero y jardinería")
        x = cotizaciones.libro(filas, self.tmp / "comp.xlsx", "Prueba")
        wb = load_workbook(x)
        ws = wb["COMPARATIVO"]
        r = next(i for i in range(5, ws.max_row + 1) if ws.cell(i, 2).value == "Abono")
        ws.cell(r, 7, "Vivero A"); ws.cell(r, 8, 1800); ws.cell(r, 9, "Vivero B"); ws.cell(r, 10, 1650)
        wb.save(x)
        v = load_workbook(recalcular(x), data_only=True)["COMPARATIVO"]
        self.assertEqual(v.cell(r, 13).value, 1650)
        self.assertEqual(v.cell(r, 14).value, "Vivero B")
        self.assertEqual(v.cell(r, 15).value, round(2000 * 1650))
        elegidas = cotizaciones.desde_comparativo(x)
        self.assertEqual(elegidas["Abono"]["proveedor"], "Vivero B")
        docs = cotizaciones.solicitudes(filas, self.tmp / "sol", "Prueba", "Corozal, Sucre", {"nombre": "Arq. X"})
        self.assertTrue(all(d.exists() and d.with_suffix(".txt").exists() for d in docs))

    def test_insumo_inexistente_falla(self):
        malo = {**SPEC, "apus": [{"item": "2.3", "eq": [], "mat": [["No existe", 1]], "mo": []}]}
        with self.assertRaises(KeyError):
            apu_unad.construir(self.tmp / "oficial.xlsx", malo, self.tmp / "x.xlsx")


if __name__ == "__main__":
    unittest.main(verbosity=2)
