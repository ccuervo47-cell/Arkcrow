"""Prueba obligatoria de la Fase 4: ejercicio de la sala de juntas + el auditor detecta errores sembrados.

Ejecutar desde la carpeta ArkcrowObra:  python -m unittest tests.test_costos -v
Requiere LibreOffice (o Excel en Windows) para recalcular.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "nucleo"))

from arkcrow import auditor, db, libro_costos, revisor_calidad  # noqa: E402

PROYECTO = RAIZ / "proyectos" / "sala-juntas-prueba" / "proyecto.json"


def fila_de(ws, texto, col="A"):
    return next(r for r in range(1, ws.max_row + 1) if str(ws[f"{col}{r}"].value).startswith(str(texto)))


def reglas(res, severidad=None):
    return [h.regla for h in res.hallazgos if severidad is None or h.severidad == severidad]


class TestSalaDeJuntas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.inicializar()
        cls.tmp = Path(tempfile.mkdtemp(prefix="arkcrow-test-"))
        cls.xlsx = libro_costos.generar(PROYECTO, cls.tmp / "sala.xlsx")
        cls.res = auditor.auditar(cls.xlsx)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_libro_aprobado_sin_errores(self):
        self.assertTrue(self.res.aprobado, [h for h in self.res.hallazgos if h.severidad == "ERROR"])

    def test_costo_directo_del_orden_de_la_prueba(self):
        cd = self.res.resumen["costo_directo"]
        self.assertGreater(cd, 9_000_000)
        self.assertLess(cd, 12_000_000)

    def test_aiu_aplicado(self):
        s = self.res.resumen
        self.assertAlmostEqual(s["administracion"], round(s["costo_directo"] * 0.13), delta=1)
        self.assertAlmostEqual(s["iva_utilidad"], round(s["utilidad"] * 0.19), delta=1)
        # misma relación total / costo directo que la prueba (13,66 / 10,88 ≈ 1,255)
        self.assertAlmostEqual(s["valor_total"] / s["costo_directo"], 1.2552, places=3)

    def test_formulas_vivas_en_balance(self):
        ws = load_workbook(self.xlsx)["BALANCE"]
        fila = fila_de(ws, "='APU 2.01'")
        for col in "ABCDEFGHI":
            self.assertTrue(str(ws[f"{col}{fila}"].value).startswith("="), f"{col}{fila} no es fórmula")

    def test_observaciones_tecnicas_de_la_prueba(self):
        obs = reglas(self.res, "OBSERVACIÓN TÉCNICA")
        self.assertIn("T3 Confinamiento NSR-10", obs)
        self.assertIn("T4 Pintura de cielo raso", obs)
        self.assertEqual(obs.count("T5 Puertas y ventanas"), 2)
        sup = " ".join(self.res.superadas)
        self.assertIn("T1 Mortero", sup)
        self.assertIn("T2 Cuantía", sup)

    def test_revisor_calidad_entrega_con_valores(self):
        copia = self.tmp / "entrega.xlsx"
        shutil.copy(self.xlsx, copia)
        ok, _, _ = revisor_calidad.revisar(copia, entregar=True)
        self.assertTrue(ok)
        wv = load_workbook(copia, data_only=True)
        self.assertTrue(any(isinstance(c.value, (int, float)) and c.value > 9_000_000
                            for f in wv["BALANCE"].iter_rows() for c in f))
        ws = load_workbook(copia)["BALANCE"]
        self.assertTrue(str(ws[f"F{fila_de(ws, "='APU 2.01'")}"].value).startswith("="))


class TestAuditorDetectaErrores(unittest.TestCase):
    """Se siembran a propósito los errores de la revisión de la prueba y el auditor debe encontrarlos."""

    @classmethod
    def setUpClass(cls):
        db.inicializar()
        cls.tmp = Path(tempfile.mkdtemp(prefix="arkcrow-test-"))
        base = libro_costos.generar(PROYECTO, cls.tmp / "base.xlsx")
        wb = load_workbook(base)
        bal = wb["BALANCE"]
        r201, r204 = fila_de(bal, "='APU 2.01'"), fila_de(bal, "='APU 2.04'")
        bal[f"D{r201}"] = 1.29                    # cantidad pegada (no enlazada)
        bal[f"E{r204}"] = 0                       # valor unitario en cero
        bal[f"C{fila_de(bal, "='APU 2.03'")}"] = "ml"   # unidad pegada y distinta en el balance
        datos = wb["DATOS"]
        for r in range(1, datos.max_row + 1):
            lab = datos[f"A{r}"].value or ""
            if lab == "Contratista":
                datos[f"B{r}"] = None             # encabezado vacío
            if lab.startswith("Prestaciones"):
                datos[f"B{r}"] = 0.45             # prestaciones mal
            if lab.startswith("Herramienta menor"):
                datos[f"B{r}"] = 0.15             # herramienta menor fuera de rango
        a202 = wb["APU 2.02"]
        a202[f"B{fila_de(a202, 'Descripción')}"] = "Mortero de nivelación de piso 1:4, e = 0,08 m."
        a201 = wb["APU 2.01"]
        a201[f"C{fila_de(a201, 80, 'C')}"] = 150   # acero: 150 kg/m³
        cls.malo = cls.tmp / "malo.xlsx"
        wb.save(cls.malo)
        cls.res = auditor.auditar(cls.malo)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_no_aprueba(self):
        self.assertFalse(self.res.aprobado)

    def test_detecta_cada_error(self):
        errores = reglas(self.res, "ERROR")
        for regla in ("R1 Balance enlazado", "R1 Totales en cero", "R2 Unidades", "R3 Encabezados", "R5 Prestaciones"):
            self.assertIn(regla, errores, regla)
        self.assertIn("R7 Herramienta menor", reglas(self.res, "ADVERTENCIA"))
        obs = reglas(self.res, "OBSERVACIÓN TÉCNICA")
        self.assertIn("T1 Mortero de nivelación", obs)
        self.assertIn("T2 Cuantía de acero", obs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
