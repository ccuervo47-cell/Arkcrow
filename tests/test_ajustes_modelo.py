"""Ajustes tras la prueba en el equipo real: Excel con encabezados repetidos y modelo local lento."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "nucleo"))

from arkcrow import asistente, conocimiento, enrutador, llm  # noqa: E402


class TestExcelConFormatoRepetido(unittest.TestCase):
    def test_encabezado_comun_una_sola_vez(self):
        from openpyxl import Workbook
        wb = Workbook()
        wb.remove(wb.active)
        items = {"3.4": "Siembra de grama en rollo | m2 | 120", "5.1": "Adoquín de concreto 20x10x6 | m2 | 85",
                 "5.2": "Bordillo prefabricado A-10 | ml | 64", "6.1": "Luminaria LED poste 4 m | und | 6"}
        for hoja, item in items.items():
            ws = wb.create_sheet(hoja)
            ws.append(["FORMATO DE ANÁLISIS DE PRECIOS UNITARIOS 'APUs'", "CÓDIGO"])
            ws.append(["INVITACIÓN No.", "125-2026"])
            ws.append(["OBJETO", "ADECUACIÓN DE ESPACIOS ..."])
            ws.append(item.split(" | "))
        f = Path(tempfile.mkdtemp()) / "apus.xlsx"
        wb.save(f)
        partes = list(conocimiento._xlsx(f))
        self.assertEqual(partes[0][0], "encabezado común de las hojas")
        self.assertIn("125-2026", partes[0][1])
        propias = dict(partes[1:])
        self.assertEqual(propias["hoja «5.1»"], "Adoquín de concreto 20x10x6 | m2 | 85")
        self.assertFalse(any("FORMATO DE ANÁLISIS" in t for t in propias.values()))


class TestModeloLento(unittest.TestCase):
    def test_avisa_que_tardo_y_muestra_fragmentos(self):
        with mock.patch.dict(os.environ, {"ARKCROW_FORZAR_OFFLINE": "1"}), \
             mock.patch.object(llm, "elegir_modelo", return_value="qwen2.5:7b"), \
             mock.patch.object(llm, "chat", side_effect=llm.OllamaNoDisponible("<urlopen error timed out>")):
            enrutador._CACHE["v"] = None
            r = asistente.Asistente().responder("¿qué AIU usa la empresa?")
        self.assertIn("tardó demasiado", r.texto)
        self.assertNotIn("No hay modelo", r.texto)
        self.assertIn("[memoria/empresa.md", r.texto)

    def test_prompt_acotado(self):
        enviado = {}

        def falso(mensajes, modelo=None, **k):
            enviado["n"] = sum(len(m["content"]) for m in mensajes)
            return "ok [memoria/empresa.md, sección «AIU»]"
        with mock.patch.dict(os.environ, {"ARKCROW_FORZAR_OFFLINE": "1"}), \
             mock.patch.object(llm, "elegir_modelo", return_value="qwen2.5:7b"), \
             mock.patch.object(llm, "chat", side_effect=falso):
            enrutador._CACHE["v"] = None
            asistente.Asistente().responder("dame todo lo necesario para ejecutar la obra")
        # reglas + memoria (≤3.500) + 4 fragmentos (≤1.000 c/u): ≈ 12.000 caracteres (~3.500 tokens)
        self.assertLess(enviado["n"], 13000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
