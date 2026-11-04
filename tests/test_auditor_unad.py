"""Auditor del formato UNAD F-14-3-5 con un libro sintético que reproduce los errores típicos."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "nucleo"))

from arkcrow import auditor_unad  # noqa: E402
from arkcrow.recalculo import recalcular  # noqa: E402


def libro(ruta: Path) -> Path:
    from openpyxl import Workbook
    wb = Workbook()
    p = wb.active
    p.title = "PRECIOS "
    p["B4"], p["H4"], p["I4"] = "Herramienta menor (%)", "%", 11000
    p["K4"], p["R4"], p["S4"] = "Adoquín de concreto 20x10x6", "m2", 52000
    p["U4"], p["Z4"], p["AA4"] = "Transporte de materiales", "VIAJE", 100000
    p["AC4"], p["AJ4"] = "Oficial de obra", 98400
    b = wb.create_sheet("BALANCE")
    b["B2"], b["B3"] = "PRESUPUESTO", "UNAD PAISAJISMO COROZAL 2026"
    filas = [("2", "OBRA CIVIL", None, None, None), ("2.1", "Suministro e instalación de adoquín para senderos", "m2", 400, 70000),
             ("2.2", "Suministro e instalación de árboles nativos", "und", 20, 189200),
             ("2.3", "Suministro de tierra negra fertilizada", "m2", 4000, 17500)]
    for i, (c, d, u, q, vu) in enumerate(filas, start=5):
        b[f"B{i}"], b[f"C{i}"] = c, d
        if u:
            b[f"D{i}"], b[f"E{i}"], b[f"F{i}"], b[f"G{i}"] = u, q, vu, f"=ROUND(E{i}*F{i},0)"
    b["G5"] = "=SUM(G6:G8)"
    b["E9"], b["G9"] = "COSTOS DIRECTOS", "=SUM(G5:G8)/2"
    for r, (k, v) in enumerate((("A", 0.16), ("I ", 0.06), ("U", 0.04), ("I / U", 0.19)), start=10):
        b[f"E{r}"], b[f"F{r}"], b[f"G{r}"] = k, v, f"=ROUND(G9*F{r},0)"
    b["E14"], b["G14"] = "VALOR TOTAL ", "=SUM(G9:G13)"
    f = wb.create_sheet("FORMATO")
    f["B19"] = "ADECUACIÓN Y DOTACIÓN DE ESPACIOS DESTINADOS A PRIMEROS AUXILIOS"
    f["J15"], f["C27"], f["K27"] = ",", ".", "."

    def apu(nombre, item, material, mano=True):
        a = wb.create_sheet(nombre)
        a["B32"] = item
        a["C32"] = f"=VLOOKUP(B32,BALANCE!$B$5:$G$14,2,0)"
        a["K32"] = f"=VLOOKUP(B32,BALANCE!$B$5:$G$14,3,0)"
        a["B37"], a["J37"], a["K37"], a["M37"] = "Herramienta menor (%)", 11000, 0.0041, "=J37*K37"
        a["B49"], a["J49"] = material, 1.05
        a["K49"] = f"=VLOOKUP(B49,'PRECIOS '!$K$4:$S$10,9,0)"
        a["M49"] = "=K49*J49"
        a["B66"], a["H66"], a["I66"], a["J66"], a["K66"], a["M66"] = "Transporte de materiales", 0.015, 1, "=H66*I66", 100000, "=K66*J66"
        a["B76"], a["H76"], a["I76"], a["J76"], a["K76"] = "Oficial de obra", 98400, "=+H76*0.94", "=H76+I76", 0.04120531628277363
        a["M76"] = "=K76*J76"
        a["M83"] = "=ROUND(M37+M49+M66+M76,2)"
        a["M85"] = "=ROUND(M83,0)"
    apu("2.1", "2.1", "Adoquín de concreto 20x10x6")
    apu("2.2", "2.2", "Division en madera con marco y parales")    # copiado de otro proyecto: #N/A
    apu("6.9", "6.9", "Silla giratoria")                           # hoja sobrante
    wb.save(ruta)
    return Path(recalcular(ruta, ruta))


class TestAuditorUnad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.au = auditor_unad.auditar(libro(cls.tmp / "apus.xlsx"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def _temas(self, sev):
        return " ".join(f"{h.tema} {h.detalle}" for h in self.au.hallazgos if h.severidad == sev)

    def test_detecta_errores_tipicos(self):
        err = self._temas("ERROR")
        self.assertIn("OBJETO no corresponde", err)
        self.assertIn("Ítem 2.2", err)
        self.assertIn("Division en madera", err)
        self.assertIn("ítems sin hoja de APU: 2.3", err)
        adv = self._temas("ADVERTENCIA")
        for t in ("CONTRATO No. vacío", "/2", "Hojas sobrantes", "Herramienta menor", "tierra negra"):
            self.assertIn(t, adv, t)
        obs = self._temas("OBSERVACIÓN")
        self.assertIn("94%", obs)
        self.assertIn("decimales", obs)
        self.assertIn("viaje global", obs)

    def test_estados_y_resumen(self):
        est = {i["item"]: i["estado"] for i in self.au.items}
        self.assertEqual(est["2.2"], "APU de otro proyecto")
        self.assertEqual(est["2.3"], "sin APU")
        self.assertEqual(self.au.resumen["hojas_sobrantes"], 1)

    def test_salidas(self):
        md = auditor_unad.reporte_md(self.au)
        self.assertIn("## Estado por ítem", md)
        x = auditor_unad.a_excel(self.au, self.tmp / "aud.xlsx")
        from openpyxl import load_workbook
        self.assertEqual(load_workbook(x).sheetnames[:2], ["HALLAZGOS", "ITEMS"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
