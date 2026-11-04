"""Pruebas de la Fase 5 (skills de obra). Usan una obra temporal 'zz-prueba-obra' que se borra al final.

Ejecutar desde ArkcrowObra:  python -m unittest tests.test_obra -v
"""
import json
import shutil
import sys
import unittest
import zipfile
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "nucleo"))
sys.path.insert(0, str(RAIZ / "tests"))

from arkcrow import (bim, bitacora, checklists, comunicaciones, cortes, cronograma, db, fotos,  # noqa: E402
                     libro_costos, no_previstos)
from arkcrow.recalculo import recalcular  # noqa: E402
from arkcrow.revisor_calidad import revisar  # noqa: E402

OBRA = "zz-prueba-obra"
DIR = RAIZ / "proyectos" / OBRA
EJEMPLO = RAIZ / "proyectos" / "sala-juntas-prueba"


def valores(xlsx, hoja):
    return load_workbook(recalcular(xlsx), data_only=True)[hoja]


class TestObra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        shutil.rmtree(DIR, ignore_errors=True)
        DIR.mkdir(parents=True)
        shutil.copy(EJEMPLO / "proyecto.json", DIR / "proyecto.json")
        db.inicializar()
        libro = libro_costos.generar(DIR / "proyecto.json")
        ok, _, _ = revisar(libro, entregar=True)
        assert ok

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(DIR, ignore_errors=True)

    # ------------------------------------------------------------- bitácora
    def test_bitacora_y_informe_semanal(self):
        texto = (EJEMPLO / "ejemplos" / "bitacora_2026-11-03.txt").read_text(encoding="utf-8")
        e = bitacora.parsear_texto(texto)
        self.assertEqual(e["clima"]["lluvia_h"], 2.0)
        self.assertEqual(sum(p["cantidad"] for p in e["personal"]), 6)
        self.assertEqual(e["actividades"][0]["item"], "2.03")
        self.assertEqual(e["actividades"][0]["cantidad"], 18.0)
        self.assertEqual(e["actividades"][0]["avance"], 0.5)
        self.assertEqual(e["equipos"][0], {"equipo": "andamio multidireccional", "cantidad": 4, "horas": 8.0})
        bitacora.registrar(OBRA, e, date(2026, 11, 3))
        bitacora.registrar(OBRA, bitacora.parsear_texto("Novedades: segunda nota del día"), date(2026, 11, 3))
        dia = json.loads((DIR / "bitacora" / "2026-11-03.json").read_text(encoding="utf-8"))
        self.assertEqual(len(dia["novedades"]), 2, "debe agregar, no sobrescribir")
        docx, _ = bitacora.informe_semanal(OBRA, date(2026, 11, 4))
        xml = zipfile.ZipFile(docx).read("word/document.xml").decode()
        self.assertIn("INFORME SEMANAL DE OBRA", xml)
        self.assertIn("mampostería bloque No. 4", xml)

    # ---------------------------------------------------------------- fotos
    def test_fotos_exif_gps_y_anexo(self):
        from fotos_prueba import crear
        origen = DIR / "_celular"
        crear(origen, "2.03_muro eje A.jpg", datetime(2026, 11, 3, 9, 15), 4.60971, -74.08175)
        crear(origen, "IMG_0001.jpg", datetime(2026, 11, 4, 16, 5))
        nuevos = fotos.organizar(OBRA, origen)
        self.assertEqual(len(nuevos), 2)
        r = next(x for x in nuevos if x["item"] == "2.03")
        self.assertAlmostEqual(r["lat"], 4.60971, places=4)
        self.assertAlmostEqual(r["lon"], -74.08175, places=4)
        self.assertTrue(r["archivo"].endswith("20261103_091500_2.03_muro_eje_A.jpg"))
        self.assertTrue((origen / "2.03_muro eje A.jpg").exists(), "no debe mover el original")
        self.assertEqual(fotos.organizar(OBRA, origen), [], "no debe duplicar")
        docx, _ = fotos.anexo(OBRA, item="2.03")
        self.assertIn("word/media/", " ".join(zipfile.ZipFile(docx).namelist()))
        self.assertEqual(fotos.contar(OBRA)["2.03"], 1)

    # --------------------------------------------------------------- cortes
    def test_acta_de_corte(self):
        (DIR / "cortes").mkdir(exist_ok=True)
        for n in (1, 2):
            shutil.copy(EJEMPLO / "cortes" / f"corte_{n:02d}.json", DIR / "cortes" / f"corte_{n:02d}.json")
        r = cortes.acta(OBRA, 2)
        self.assertEqual(r["errores"], [])
        self.assertTrue(any("2.08" in a and "supera" in a for a in r["avisos"]))
        ws = valores(r["xlsx"], "ACTA CORTE 02")
        filas = {row[0]: row for row in ws.iter_rows(values_only=True) if isinstance(row[0], str)}
        f204 = filas["2.04"]          # 40 (corte 1) + 35,87 (corte 2) = 75,87 = 100 %
        self.assertAlmostEqual(f204[6], 40.0)
        self.assertAlmostEqual(f204[8], 75.87, places=2)
        self.assertAlmostEqual(f204[9], 1.0, places=3)
        self.assertEqual(filas["2.04"][15], "AZUL")
        cd_row = next(row for row in ws.iter_rows(values_only=True) if row[0] == "COSTO DIRECTO")
        self.assertGreater(cd_row[5], 9_000_000)        # valor contrato
        self.assertGreater(cd_row[12], cd_row[11])      # acumulado > este corte

    # ------------------------------------------------------------------ NP
    def test_items_no_previstos(self):
        (DIR / "np").mkdir(exist_ok=True)
        r = no_previstos.generar(OBRA, EJEMPLO / "np" / "solicitud_01.json")
        self.assertTrue(r["aprobado"])
        self.assertEqual(r["items"], 2)
        self.assertGreater(r["valor_total"], r["costo_directo"])
        xml = zipfile.ZipFile(r["oficio"]).read("word/document.xml").decode()
        self.assertIn("NP-02", xml)
        self.assertIn("BORRADOR", zipfile.ZipFile(r["oficio"]).read("word/header1.xml").decode())

    # ----------------------------------------------------------- cronograma
    def test_cronograma_formulas_igual_cpm(self):
        shutil.copy(EJEMPLO / "cronograma.json", DIR / "cronograma.json")
        r = cronograma.generar(OBRA)
        self.assertEqual(r["ruta_critica"], ["A", "B", "C", "D", "E", "H", "I", "J", "K"])
        ws = valores(r["xlsx"], "CRONOGRAMA")
        for i, fila in r["fila_de"].items():
            c = r["control"][i]
            self.assertEqual([ws[f"H{fila}"].value, ws[f"I{fila}"].value, ws[f"J{fila}"].value,
                              ws[f"K{fila}"].value, ws[f"L{fila}"].value],
                             [c["es"], c["ef"], c["ls"], c["lf"], c["holgura"]], f"actividad {i}")
        with self.assertRaises(ValueError):
            cronograma.cpm([{"id": "A", "duracion": 1, "predecesoras": ["B"]},
                            {"id": "B", "duracion": 1, "predecesoras": ["A"]}])

    # ----------------------------------------------------------- checklists
    def test_checklist_critico_no_aprueba(self):
        f = checklists.generar(OBRA, "mamposteria", "Eje A")
        wb = load_workbook(f)
        ws = wb["MAMPOSTERIA"]
        for i, v in enumerate(["SI", "SI", "SI", "SI", "SI", "NO", "SI", "N.A.", "SI"]):
            ws[f"E{9 + i}"] = v
        wb.save(f)
        ws = valores(f, "MAMPOSTERIA")
        self.assertEqual(ws["E23"].value, "NO APROBADO: ítem crítico")
        self.assertAlmostEqual(ws["E20"].value, 7 / 8)

    # -------------------------------------------------------- comunicaciones
    def test_comunicaciones_solo_borradores(self):
        import inspect
        fuente = inspect.getsource(comunicaciones)
        for prohibido in ("smtplib", "send_message", "sendmail", "requests.post"):
            self.assertNotIn(prohibido, fuente)
        eml = comunicaciones.correo(OBRA, "Supervisión", "Prueba", ["punto 1"])
        txt = eml.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("X-Unsent: 1", txt)
        self.assertIn("[BORRADOR]", txt)
        of = comunicaciones.oficio(OBRA, "Arq. X", "Supervisor", "Asunto prueba", ["a", "b"])
        self.assertIn("BORRADOR", zipfile.ZipFile(of).read("word/header1.xml").decode())
        acta = comunicaciones.acta_comite(OBRA, json.loads((EJEMPLO / "ejemplos" / "comite_01.json").read_text(encoding="utf-8")))
        self.assertIn("Confirmar la medida de la ventana", zipfile.ZipFile(acta).read("word/document.xml").decode())

    # ------------------------------------------------------------------ BIM
    def test_ifc_cantidades_igual_memoria(self):
        from ifc_prueba import crear
        ifc = crear(DIR / "modelo.ifc")
        r = bim.leer_ifc(ifc)["resumen"]
        self.assertAlmostEqual(r["muros_area_neta_m2_una_cara"], 37.935, places=3)
        self.assertAlmostEqual(r["muros_longitud_ml"], 13.84, places=3)
        self.assertAlmostEqual(r["espacios_area_m2"], 10.974, places=3)
        self.assertEqual((r["puertas"], r["ventanas"]), (1, 1))

    def test_pdf_plano(self):
        from reportlab.pdfgen import canvas
        pdf = DIR / "plano.pdf"
        c = canvas.Canvas(str(pdf))
        c.drawString(72, 700, "PLANTA SALA DE JUNTAS  ESC 1:50   AREA 10,97 m2")
        c.drawString(72, 680, "P-101  0,85 x 2,10    V-39  1,50 x 1,20    3,54  3,10")
        c.save()
        p = bim.leer_pdf_plano(pdf)[0]
        self.assertEqual(p["marcas_puertas"], ["P-101"])
        self.assertEqual(p["marcas_ventanas"], ["V-39"])
        self.assertIn(10.97, p["areas_m2"])
        self.assertIn("1:50", p["escalas"])
        self.assertIn(3.54, p["cotas"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
