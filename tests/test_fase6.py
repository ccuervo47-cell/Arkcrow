"""Pruebas de la Fase 6: enrutador online/offline, privacidad, nube, cola de sincronización y respaldos.

Ejecutar desde ArkcrowObra:  python -m unittest tests.test_fase6 -v

Notas de honestidad:
- El corte de red es REAL para el proceso: se instala un proxy inaccesible (todo el tráfico falla) y luego se
  restaura; además, si existe `unshare`, se prueba un proceso en un espacio de red sin interfaces.
- Las llamadas a la nube usan un CLIENTE FALSO (no hay clave de API en el entorno de pruebas): se verifica qué
  se enviaría (modelo, fallbacks, búsqueda web, exclusión de confidenciales), no la respuesta real de Claude.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "nucleo"))

from arkcrow import asistente, cola, enrutador, llm, nube, respaldo  # noqa: E402


_NOPROXY = {k: os.environ.get(k) for k in ("no_proxy", "NO_PROXY")}


def cortar_red():
    """Todo el tráfico HTTP(S) del proceso pasa por un proxy inexistente (sin excepciones no_proxy)."""
    for k in _NOPROXY:
        os.environ[k] = ""
    urllib.request.install_opener(urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": "http://127.0.0.1:9", "https": "http://127.0.0.1:9"})))
    enrutador._CACHE["v"] = None


def restaurar_red():
    for k, v in _NOPROXY.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    urllib.request.install_opener(urllib.request.build_opener())
    enrutador._CACHE["v"] = None


class TestEnrutador(unittest.TestCase):
    def tearDown(self):
        restaurar_red()

    @unittest.skipUnless(enrutador.hay_internet(forzar=True), "esta máquina no tiene internet ahora")
    def test_alternar_conexion_en_una_sesion(self):
        a = asistente.Asistente()
        self.assertTrue(a.ultimo_online)
        r1 = a.responder("¿qué AIU usa la empresa?")
        self.assertEqual(r1.decision.modo, "ONLINE")
        self.assertIn("[ONLINE", r1.mostrar())
        cortar_red()
        r2 = a.responder("¿qué AIU usa la empresa?")
        self.assertEqual(r2.decision.modo, "OFFLINE")
        self.assertIn("CAMBIO DE MODO: ahora OFFLINE", r2.mostrar())
        self.assertIn("13 %", r2.texto)                       # sigue respondiendo sin red
        restaurar_red()
        r3 = a.responder("¿qué AIU usa la empresa?")
        self.assertIn("CAMBIO DE MODO: ahora ONLINE", r3.mostrar())

    @unittest.skipUnless(shutil.which("unshare") and sys.platform.startswith("linux"), "requiere unshare (Linux)")
    def test_proceso_sin_interfaces_de_red(self):
        codigo = ("import sys; sys.path.insert(0,'nucleo'); from arkcrow import enrutador; "
                  "print('ONLINE' if enrutador.hay_internet() else 'OFFLINE')")
        r = subprocess.run(["unshare", "-rn", sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest(f"unshare no permitido: {r.stderr.strip()[:80]}")
        self.assertEqual(r.stdout.strip(), "OFFLINE")

    def test_offline_sugiere_cola(self):
        cortar_red()
        r = asistente.Asistente().responder("busca el precio actual del bloque No. 4 en internet")
        self.assertTrue(r.sugerir_cola)
        self.assertIn("/encolar", r.texto)


class TestPrivacidad(unittest.TestCase):
    FUENTES = [{"ruta": "conocimiento/confidencial/presupuesto.md", "confidencial": True, "texto": "MARGEN SECRETO 22 %",
                "cita": "[conocimiento/confidencial/presupuesto.md, texto]"},
               {"ruta": "memoria/empresa.md", "confidencial": False, "texto": "AIU 13 % 3 % 8 %",
                "cita": "[memoria/empresa.md, sección «AIU»]"}]

    def _online(self):
        return [mock.patch.object(enrutador, "hay_internet", return_value=True),
                mock.patch.object(nube, "configurada", return_value=True),
                mock.patch.object(enrutador, "nube_de_pago", return_value=True),
                mock.patch.object(llm, "elegir_modelo", return_value=None)]

    def _con(self, parches, fn):
        for p in parches:
            p.start()
        try:
            return fn()
        finally:
            for p in parches:
                p.stop()

    def test_sin_autorizacion_excluye_confidenciales(self):
        d = self._con(self._online(), lambda: enrutador.decidir("explica el AIU", self.FUENTES, confirmar=lambda t: False))
        self.assertEqual(d.motor, "nube")
        self.assertFalse(any(f["confidencial"] for f in d.fuentes))
        self.assertIn("excluyeron 1", d.aviso_privacidad)

    def test_pregunta_confidencial_no_sale(self):
        d = self._con(self._online(), lambda: enrutador.decidir("analiza el margen del presupuesto interno",
                                                                 self.FUENTES, confirmar=lambda t: False))
        self.assertNotEqual(d.motor, "nube")
        self.assertIn("No se envió nada", d.aviso_privacidad)

    def test_con_autorizacion_explicita(self):
        preguntas = []
        d = self._con(self._online(), lambda: enrutador.decidir(
            "explica el AIU", self.FUENTES, confirmar=lambda t: preguntas.append(t) or True))
        self.assertEqual(d.motor, "nube")
        self.assertEqual(len(d.fuentes), 2)
        self.assertIn("CONFIDENCIAL", preguntas[0])

    def test_lo_enviado_a_la_nube_no_contiene_confidencial(self):
        enviado = {}

        def falso_preguntar(sistema, mensajes, web=False, **k):
            enviado["payload"] = sistema + json.dumps(mensajes, ensure_ascii=False)
            return nube.RespuestaNube("respuesta", nube.MODELO_NUBE)

        parches = self._online() + [mock.patch.object(nube, "preguntar", side_effect=falso_preguntar),
                                    mock.patch("arkcrow.conocimiento.buscar", return_value=self.FUENTES)]
        r = self._con(parches, lambda: asistente.Asistente(confirmar=lambda t: False).responder("explica el AIU"))
        self.assertEqual(r.decision.motor, "nube")
        self.assertIn("AIU 13 %", enviado["payload"])
        self.assertNotIn("MARGEN SECRETO", enviado["payload"])
        self.assertIn("🔒", r.mostrar())


class TestNubeClienteFalso(unittest.TestCase):
    def _cliente(self, respuestas):
        llamadas = []

        def create(**kw):
            llamadas.append(kw)
            return respuestas.pop(0)
        return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create))), llamadas

    def test_parametros_busqueda_web_y_pause_turn(self):
        texto = SimpleNamespace(type="text", text="Según la fuente...", citations=[
            SimpleNamespace(url="https://ejemplo.gov.co/norma", title="Norma X")])
        pausa = SimpleNamespace(stop_reason="pause_turn", content=[SimpleNamespace(type="server_tool_use")], model="m")
        final = SimpleNamespace(stop_reason="end_turn", content=[texto], model=nube.MODELO_NUBE)
        cli, llamadas = self._cliente([pausa, final])
        r = nube.preguntar("sistema", [{"role": "user", "content": "q"}], web=True, cliente=cli)
        self.assertEqual(len(llamadas), 2, "debe reanudar pause_turn")
        p = llamadas[0]
        self.assertEqual(p["model"], "claude-opus-5-5")
        self.assertEqual(p["fallbacks"], "default")
        self.assertIn("server-side-fallback-2026-07-01", p["betas"])
        self.assertEqual(p["tools"][0]["type"], "web_search_20260209")
        self.assertEqual(llamadas[1]["messages"][-1]["role"], "assistant")
        self.assertEqual(r.fuentes_web[0]["url"], "https://ejemplo.gov.co/norma")

    def test_rechazo(self):
        cli, _ = self._cliente([SimpleNamespace(stop_reason="refusal", content=[], model="m")])
        r = nube.preguntar("s", [{"role": "user", "content": "q"}], cliente=cli)
        self.assertTrue(r.rechazada)


class TestCola(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.p = mock.patch.object(cola, "COLA", self.tmp / "cola.json")
        self.p.start()

    def tearDown(self):
        self.p.stop()
        shutil.rmtree(self.tmp)

    def test_solo_ejecuta_lo_aprobado_y_con_internet(self):
        a = cola.agregar("consulta_web", "NSR-10 actualización 2026", {"pregunta": "x"})
        b = cola.agregar("actualizar_precios", "Precios de bloque y cemento")
        c = cola.agregar("enviar_borrador", "Correo ventana V-39", {"archivo": "x.eml"})
        self.assertEqual(len(cola.listar()), 3)
        corridas = []
        falsos = {k: (lambda t, k=k: corridas.append(t["id"]) or f"ok {k}") for k in cola.TIPOS}
        cola.aprobar(a["id"])
        cola.aprobar(c["id"])
        self.assertEqual(cola.ejecutar_aprobadas(lambda: False, falsos), [], "sin internet no ejecuta")
        hechas = cola.ejecutar_aprobadas(lambda: True, falsos)
        self.assertEqual(sorted(corridas), sorted([a["id"], c["id"]]))
        self.assertTrue(all(t["estado"] == "hecha" for t in hechas))
        self.assertEqual([t["id"] for t in cola.listar("pendiente")], [b["id"]], "lo no aprobado sigue pendiente")
        cola.descartar(b["id"])
        self.assertEqual(cola.listar("pendiente"), [])

    def test_enviar_borrador_nunca_envia(self):
        t = cola.agregar("enviar_borrador", "Correo", {"archivo": "x.eml"})
        self.assertIn("ARKCROW no envía", cola.EJECUTORES["enviar_borrador"](t))
        with self.assertRaises(ValueError):
            cola.agregar("borrar_todo", "x")


class TestRespaldo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = mock.patch.dict(os.environ, {"ARKCROW_RESPALDOS": str(self.tmp), "ARKCROW_RESPALDOS_MAX": "2"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp)

    def test_respaldo_verificado_y_diario(self):
        z = respaldo.hacer()
        nombres = zipfile.ZipFile(z).namelist()
        self.assertIn("memoria/perfil.md", nombres)
        self.assertIn("datos/arkcrow.sqlite", nombres)
        self.assertTrue(any(n.startswith("proyectos/sala-juntas-prueba/") for n in nombres))
        self.assertEqual(respaldo.verificar(z), [])
        self.assertIsNone(respaldo.si_toca(), "no repite en menos de 24 h")

    def test_rotacion_y_deteccion_de_dano(self):
        import time
        for _ in range(3):
            respaldo.hacer()
            time.sleep(1.1)
        self.assertEqual(len(respaldo.listar()), 2)
        malo = self.tmp / "arkcrow_respaldo_malo.zip"
        with zipfile.ZipFile(malo, "w") as zf:
            zf.writestr("otra/cosa.txt", "x")
        self.assertIn("no contiene memoria/", respaldo.verificar(malo))


if __name__ == "__main__":
    unittest.main(verbosity=2)
