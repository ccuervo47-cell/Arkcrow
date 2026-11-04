"""Pruebas de la interfaz web local (servidor en 127.0.0.1, sin recursos externos)."""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "nucleo"))

from arkcrow import enrutador, web  # noqa: E402


class TestWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = mock.patch.dict(os.environ, {"ARKCROW_FORZAR_OFFLINE": "1"})
        cls.env.start()
        enrutador._CACHE["v"] = None
        cls.srv = web.servir(18765, abrir=False)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.env.stop()

    def _post(self, ruta, datos, tipo="application/json", host=None):
        req = urllib.request.Request(self.url + ruta, data=json.dumps(datos).encode(), method="POST",
                                     headers={"Content-Type": tipo, **({"Host": host} if host else {})})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def test_pagina_sin_recursos_externos(self):
        html = urllib.request.urlopen(self.url + "/", timeout=10).read().decode()
        self.assertIn("ARKCROW OBRA", html)
        for externo in ("<script src", "<link ", "cdn", "googleapis", "@import"):
            self.assertNotIn(externo, html.lower())

    def test_estado_y_chat_offline(self):
        e = json.loads(urllib.request.urlopen(self.url + "/api/estado", timeout=10).read())
        self.assertFalse(e["online"])
        self.assertIn("OFFLINE", e["modo"])
        r = self._post("/api/chat", {"pregunta": "¿qué AIU usa la empresa?"})
        self.assertEqual(r["modo"], "OFFLINE")
        self.assertIn("13 %", r["texto"])
        self.assertIn("[memoria/empresa.md", r["texto"])

    def test_confirmacion_confidencial_ida_y_vuelta(self):
        with mock.patch.object(enrutador, "hay_internet", return_value=True), \
             mock.patch("arkcrow.enrutador.llm.elegir_modelo", return_value=None):
            r = self._post("/api/chat", {"pregunta": "busca en internet el margen del presupuesto interno"})
            self.assertIn("CONFIDENCIAL", r["confirmar"])
            r2 = self._post("/api/chat", {"pregunta": "busca en internet el margen del presupuesto interno",
                                          "autorizar": False})
        self.assertIn("No se hizo la búsqueda web", r2["privacidad"])

    def test_protecciones(self):
        with self.assertRaises(urllib.error.HTTPError) as c:
            self._post("/api/chat", {"pregunta": "x"}, tipo="application/x-www-form-urlencoded")
        self.assertEqual(c.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as c:
            self._post("/api/chat", {"pregunta": "x"}, host="atacante.com")
        self.assertEqual(c.exception.code, 403)

    def test_subir_documento_e_indexar(self):
        import base64
        contenido = "Especificación de prueba: el adoquín del bicicletero será de 20x10x6 cm zafirokwal.".encode()
        destino = RAIZ / "conocimiento" / "obras" / "zz-prueba-subida"
        try:
            r = self._post("/api/subir", {"nombre": "espec.txt", "destino": "obras/zz-prueba-subida",
                                          "datos": "data:text/plain;base64," + base64.b64encode(contenido).decode()})
            self.assertEqual(r["guardado"], "conocimiento/obras/zz-prueba-subida/espec.txt")
            r2 = self._post("/api/subir", {"nombre": "espec.txt", "destino": "obras/zz-prueba-subida",
                                           "datos": base64.b64encode(contenido).decode()})
            self.assertTrue(r2["guardado"].endswith("espec_2.txt"), "no debe sobrescribir")
            chat = self._post("/api/chat", {"pregunta": "adoquín zafirokwal"})
            self.assertIn("zz-prueba-subida/espec", chat["texto"])
            for malo in ({"nombre": "virus.exe", "destino": "normas"}, {"nombre": "a.txt", "destino": "../../AGENTS"}):
                with self.assertRaises(urllib.error.HTTPError):
                    self._post("/api/subir", {**malo, "datos": "eA=="})
        finally:
            import shutil
            shutil.rmtree(destino, ignore_errors=True)
            self._post("/api/indexar", {})

    def test_solo_escucha_en_localhost(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
