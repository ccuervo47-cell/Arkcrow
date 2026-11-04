"""Pruebas del modo COSTO CERO: búsqueda web gratuita + modelo local, nube de pago apagada por defecto.

No hay acceso a buscadores desde el entorno de pruebas: el análisis de resultados se prueba con una página de
DuckDuckGo guardada (tests/datos/ddg_ejemplo.html) y la búsqueda se reemplaza por resultados de ejemplo.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "nucleo"))

from arkcrow import asistente, cola, enrutador, llm, nube, web_libre  # noqa: E402

PAGINAS = [{"titulo": "Reglamento NSR-10 - Ministerio de Vivienda", "url": "https://www.minvivienda.gov.co/nsr-10",
            "resumen": "NSR-10 títulos A a K", "texto": "Texto de la página oficial de ejemplo."}]


class TestWebLibre(unittest.TestCase):
    def test_parsear_resultados_duckduckgo(self):
        r = web_libre.parsear_duckduckgo((RAIZ / "tests" / "datos" / "ddg_ejemplo.html").read_text(encoding="utf-8"))
        self.assertEqual(len(r), 2, "debe descartar el anuncio")
        self.assertEqual(r[0]["url"], "https://www.minvivienda.gov.co/nsr-10")
        self.assertEqual(r[0]["titulo"], "Reglamento NSR-10 - Ministerio de Vivienda")
        self.assertIn("Sismo Resistente", r[0]["resumen"])
        self.assertEqual(r[1]["url"], "https://ejemplo.com/precios-cemento")
        self.assertIn("&", r[1]["titulo"])

    def test_texto_de_pagina_sin_scripts(self):
        t = web_libre.texto_de_pagina("<html><script>var x=1;</script><nav>menu</nav><p>Hola &amp; obra</p></html>")
        self.assertEqual(t, "Hola & obra")


class TestCostoCero(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"ARKCROW_NUBE_DE_PAGO": "no", "ANTHROPIC_API_KEY": "clave-de-prueba"})
        self.env.start()
        self.p = [mock.patch.object(enrutador, "hay_internet", return_value=True),
                  mock.patch.object(llm, "elegir_modelo", return_value=None)]
        for p in self.p:
            p.start()

    def tearDown(self):
        for p in self.p:
            p.stop()
        self.env.stop()

    def test_nube_de_pago_apagada_aunque_haya_clave(self):
        self.assertFalse(enrutador.nube_de_pago())
        d = enrutador.decidir("busca en internet la norma vigente de alturas", [])
        self.assertEqual(d.motor, "web")
        self.assertIn("búsqueda web gratuita", d.etiqueta())
        d2 = enrutador.decidir("¿qué AIU usa la empresa?", [])
        self.assertEqual(d2.motor, "busqueda")

    def test_nunca_llama_a_la_nube(self):
        with mock.patch.object(nube, "preguntar", side_effect=AssertionError("¡llamó a la nube de pago!")), \
             mock.patch.object(web_libre, "investigar", return_value=PAGINAS):
            r = asistente.Asistente().responder("busca en internet el reglamento NSR-10 vigente")
        self.assertEqual(r.decision.motor, "web")
        self.assertIn("https://www.minvivienda.gov.co/nsr-10", r.texto)

    def test_con_modelo_local_resume_y_cita(self):
        visto = {}

        def falso_chat(mensajes, modelo=None, **k):
            visto["prompt"] = mensajes[-1]["content"]
            return "Según [WEB 1], el reglamento es la NSR-10."
        with mock.patch.object(llm, "elegir_modelo", return_value="qwen2.5:7b"), \
             mock.patch.object(llm, "chat", side_effect=falso_chat), \
             mock.patch.object(web_libre, "investigar", return_value=PAGINAS):
            r = asistente.Asistente().responder("busca el reglamento NSR-10 vigente")
        self.assertIn("[ONLINE · búsqueda web gratuita + modelo local qwen2.5:7b]", r.mostrar())
        self.assertIn("RESULTADOS WEB", visto["prompt"])
        self.assertIn("Fuentes web:", r.texto)

    def test_busqueda_confidencial_requiere_autorizacion(self):
        with mock.patch.object(web_libre, "investigar", side_effect=AssertionError("no debía buscar")):
            d = enrutador.decidir("busca en internet el margen del presupuesto interno", [], confirmar=lambda t: False)
        self.assertNotEqual(d.motor, "web")
        self.assertIn("No se hizo la búsqueda web", d.aviso_privacidad)

    def test_cola_usa_web_gratis(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            with mock.patch.object(cola, "COLA", tmp / "cola.json"), mock.patch.object(cola, "RAIZ", tmp), \
                 mock.patch.object(nube, "preguntar", side_effect=AssertionError("¡nube de pago!")), \
                 mock.patch.object(web_libre, "investigar", return_value=PAGINAS):
                t = cola.agregar("consulta_web", "NSR-10 vigente", {"pregunta": "NSR-10 vigente"})
                cola.aprobar(t["id"])
                hecha = cola.ejecutar_aprobadas(lambda: True)[0]
            self.assertEqual(hecha["estado"], "hecha", hecha["resultado"])
            guardado = next((tmp / "datos" / "resultados_cola").glob("*.md")).read_text(encoding="utf-8")
            self.assertIn("minvivienda.gov.co", guardado)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
