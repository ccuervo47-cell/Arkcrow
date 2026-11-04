"""Pruebas de lectura de planos AutoCAD (DXF) con un plano sintético de cantidades conocidas."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "nucleo"))
sys.path.insert(0, str(RAIZ / "tests"))

from arkcrow import cad, conocimiento  # noqa: E402
from dxf_prueba import crear  # noqa: E402


class TestCad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.mm = crear(cls.tmp / "paisajismo_mm.dxf", unidades_mm=True)
        cls.m = crear(cls.tmp / "paisajismo_m.dxf", unidades_mm=False)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def _capa(self, r, nombre):
        return next(c for c in r["capas"] if c["capa"] == nombre)

    def test_cantidades_por_capa(self):
        r = cad.leer(self.mm)
        self.assertEqual(r["unidades"], "mm")
        self.assertAlmostEqual(self._capa(r, "ZONA VERDE")["m2"], 50 + 3.14159, places=2)
        self.assertAlmostEqual(self._capa(r, "ADOQUIN")["m2_sombreado"], 11.0, places=3)
        self.assertAlmostEqual(self._capa(r, "BORDILLO")["ml"], 12 + 3.14159, places=2)
        self.assertEqual(r["bloques_total"], {"ARBOL": 7, "LUMINARIA": 3})
        self.assertIn("ADOQUIN PEATONAL", self._capa(r, "TEXTOS")["textos"])

    def test_mismo_resultado_en_metros_y_milimetros(self):
        a, b = cad.leer(self.mm), cad.leer(self.m)
        for capa in ("ZONA VERDE", "ADOQUIN", "BORDILLO"):
            for k in ("m2", "m2_sombreado", "ml"):
                self.assertAlmostEqual(self._capa(a, capa)[k], self._capa(b, capa)[k], places=3)

    def test_sin_unidades_avisa(self):
        import ezdxf
        doc = ezdxf.readfile(self.mm)
        doc.header["$INSUNITS"] = 0
        sin = self.tmp / "sin_unidades.dxf"
        doc.saveas(sin)
        r = cad.leer(sin)
        self.assertEqual(r["unidades"], "mm")
        self.assertTrue(any("no declara unidades" in a for a in r["avisos"]))
        self.assertAlmostEqual(self._capa(cad.leer(sin, unidades="mm"), "ZONA VERDE")["m2"], 53.14, places=1)

    def test_filtro_de_capas_y_memoria(self):
        r = cad.leer(self.mm, capas="VERDE|ARBOL")
        self.assertEqual({c["capa"] for c in r["capas"]}, {"ZONA VERDE", "ARBOLES"})
        filas = cad.a_filas_memoria(cad.leer(self.mm))
        self.assertIn(["Bloque ARBOL en capa ARBOLES (DXF)", None, None, None, 7], filas["und"])
        self.assertTrue(any(f[1] == 11.0 for f in filas["m2"]))

    def test_excel_de_cantidades(self):
        from openpyxl import load_workbook
        x = cad.a_excel(cad.leer(self.mm), self.tmp / "cant.xlsx")
        ws = load_workbook(x)["CANTIDADES DXF"]
        self.assertTrue(any(str(c.value).startswith("=SUM(") for fila in ws.iter_rows() for c in fila))

    def test_dwg_sin_oda_explica_que_hacer(self):
        dwg = self.tmp / "plano.dwg"
        dwg.write_bytes(b"AC1032")
        from ezdxf.addons import odafc
        if odafc.is_installed():
            self.skipTest("ODA File Converter instalado en este equipo")
        with self.assertRaises(cad.CadNoLegible) as c:
            cad.leer(dwg)
        self.assertIn("DXF", str(c.exception))

    def test_indexa_y_se_puede_consultar(self):
        destino = RAIZ / "conocimiento" / "obras" / "zz-prueba-cad"
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.mm, destino / "plano_paisajismo.dxf")
        try:
            con = conocimiento.conectar(self.tmp / "idx.sqlite")
            conocimiento.indexar(con, embeddings=False, verbose=False)
            r = conocimiento.buscar("cuántas luminarias tiene el plano de paisajismo", con=con)
            self.assertTrue(any("plano_paisajismo.dxf" in x["ruta"] and "LUMINARIA (3 und)" in x["texto"] for x in r[:3]))
            con.close()
        finally:
            shutil.rmtree(destino)


if __name__ == "__main__":
    unittest.main(verbosity=2)
