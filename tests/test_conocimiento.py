"""Pruebas de la Fase 3: memoria persistente y base de conocimiento con citas.

Ejecutar desde ArkcrowObra:  python -m unittest tests.test_conocimiento -v
"""
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "nucleo"))

from arkcrow import asistente, conocimiento, memoria  # noqa: E402


class TestMemoria(unittest.TestCase):
    def test_carga_memoria_base_y_obra_activa(self):
        m = memoria.cargar()
        for f in ("perfil.md", "empresa.md", "lecciones.md", "preferencias.md"):
            self.assertIn(f"memoria/{f}", m)
        self.assertIn("13 %", m["memoria/empresa.md"])
        if memoria.obra_activa():
            self.assertTrue(any("/proyectos/" in k for k in m))

    def test_rechaza_datos_sensibles(self):
        for texto in ("C.C. 1.023.456.789 del contratista", "la contraseña del correo es abc123",
                      "cuenta de ahorros 0123 4567 8901", "tarjeta 4111 1111 1111 1111"):
            with self.assertRaises(ValueError, msg=texto):
                memoria.proponer("empresa.md", texto)

    def test_no_escribe_sin_confirmacion(self):
        destino = RAIZ / "memoria" / "_prueba_tmp.md"
        try:
            p = memoria.proponer("_prueba_tmp.md", "El interventor prefiere las actas los viernes.", "prueba")
            self.assertFalse(destino.exists(), "escribió antes de confirmar")
            self.assertIn(p["id"], [x["id"] for x in memoria.pendientes()])
            memoria.aplicar(p["id"])
            self.assertIn("viernes", destino.read_text(encoding="utf-8"))
            self.assertNotIn(p["id"], [x["id"] for x in memoria.pendientes()])
        finally:
            destino.unlink(missing_ok=True)

    def test_no_escribe_fuera_de_memoria(self):
        with self.assertRaises(ValueError):
            memoria.proponer("../AGENTS.md", "x")


class TestConocimiento(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="arkcrow-idx-"))
        # documentos de prueba (se borran al final). El PDF es FICTICIO: solo prueba la cita por página.
        cls.dir_pdf = RAIZ / "conocimiento" / "obras" / "zz-prueba-automatica"
        cls.dir_pdf.mkdir(parents=True, exist_ok=True)
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(cls.dir_pdf / "especificaciones_ficticias.pdf"), pagesize=letter)
        for texto in ("Pagina uno: generalidades del proyecto.",
                      "Pagina dos: el enchape de muros sera en porcelanato rectificado zafiroquetzal de 60x60.",
                      "Pagina tres: cronograma general."):
            c.drawString(72, 700, texto)
            c.showPage()
        c.save()
        cls.conf = RAIZ / "conocimiento" / "confidencial" / "zz_presupuesto_prueba.md"
        cls.conf.write_text("# Presupuesto interno\nMargen interno ultrasecreto del 22 % para la oferta.\n", encoding="utf-8")
        cls.con = conocimiento.conectar(cls.tmp / "indice.sqlite")
        conocimiento.indexar(cls.con, embeddings=False, verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()
        shutil.rmtree(cls.dir_pdf, ignore_errors=True)
        cls.conf.unlink(missing_ok=True)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_aiu_empresa(self):
        r = conocimiento.buscar("¿qué AIU usa la empresa?", con=self.con)
        self.assertEqual(r[0]["ruta"], "memoria/empresa.md")
        self.assertIn("13 %", r[0]["texto"])
        self.assertIn("19 %", r[0]["texto"])

    def test_lecciones_prueba(self):
        r = conocimiento.buscar("¿qué lecciones dejó la prueba técnica?", con=self.con)
        self.assertEqual(r[0]["ruta"], "memoria/lecciones.md")
        for clave in ("nunca", "idénticas", "transporte", "5–10 %"):
            self.assertIn(clave, r[0]["texto"])

    def test_cita_documento_y_pagina_en_pdf(self):
        r = conocimiento.buscar("porcelanato zafiroquetzal", con=self.con)
        self.assertTrue(r[0]["ruta"].endswith("especificaciones_ficticias.pdf"))
        self.assertEqual(r[0]["ubicacion"], "p. 2")
        self.assertIn("p. 2]", r[0]["cita"])

    def test_confidencial_marcado_y_filtrable(self):
        r = conocimiento.buscar("margen interno ultrasecreto", con=self.con)
        self.assertTrue(r[0]["confidencial"])
        r2 = conocimiento.buscar("margen interno ultrasecreto", con=self.con, incluir_confidencial=False)
        self.assertFalse(any(x["confidencial"] for x in r2))

    def test_precios_de_la_base_consultables(self):
        r = conocimiento.buscar("precio del bloque No. 4", con=self.con)
        self.assertTrue(any("1.300" in x["texto"] for x in r[:3]))

    def test_norma_no_indexada_se_declara(self):
        self.assertEqual(asistente.normas_faltantes("¿qué dice la NSR-10 de columnetas?", self.con), ["NSR-10"])
        self.assertIn("Resolución 4272", asistente.normas_faltantes("requisitos de la resolución 4272 de 2021", self.con))
        self.con.execute("INSERT INTO docs VALUES ('conocimiento/normas/NSR-10_Titulo_D.pdf', 0, 0, 5, 0)")
        try:
            self.assertEqual(asistente.normas_faltantes("¿qué dice la NSR-10?", self.con), [])
        finally:
            self.con.execute("DELETE FROM docs WHERE ruta='conocimiento/normas/NSR-10_Titulo_D.pdf'")


class TestAsistenteOffline(unittest.TestCase):
    def test_responde_aiu_con_cita_y_modo(self):
        conocimiento.indexar(verbose=False, embeddings=False)
        a = asistente.Asistente()
        t0 = time.time()
        r = a.responder("¿Qué AIU usa la empresa?")
        self.assertLess(time.time() - t0, 30)
        self.assertEqual(r.modo.nombre, "OFFLINE")
        self.assertIn("[OFFLINE", r.mostrar())
        self.assertIn("13 %", r.texto)
        self.assertIn("[memoria/empresa.md", r.texto)
        self.assertIn("Obra activa", a.bienvenida())


if __name__ == "__main__":
    unittest.main(verbosity=2)
