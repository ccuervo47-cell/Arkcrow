"""Listas de chequeo de calidad y SST (Excel con validación SI/NO/N.A. y resultado automático).

Los criterios son de PRÁCTICA USUAL de obra y se marcan así en la hoja. Las tolerancias numéricas deben
confirmarse contra las especificaciones del proyecto y la norma indexada (skill normativa-co).
Ítems con ★ son críticos: un "NO" en ellos da NO APROBADO aunque el resto cumpla.

Uso:
  python -m arkcrow.checklists listar
  python -m arkcrow.checklists generar <obra> <clave> [--lugar "Eje A, piso 1"] [--fecha AAAA-MM-DD]
  python -m arkcrow.checklists generar <obra> todas
"""
from __future__ import annotations

import argparse
from datetime import date

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from . import documentos as D
from .libro_costos import CENTRO, F_ENTRADA, F_NEGRITA, F_NORMAL, F_TITULO, PCT, RELLENO_CAP, RELLENO_ENTRADA, \
    RELLENO_SUB, RELLENO_TITULO, RELLENO_TOTAL, _c

C = "★"  # crítico
LISTAS: dict[str, dict] = {
    "mamposteria": {"titulo": "Recibo de mampostería", "tipo": "CALIDAD", "items": [
        (C, "Materiales", "Bloque sin fisuras ni despuntes; tipo y dimensiones según especificación"),
        ("", "Materiales", "Mortero de pega con la dosificación especificada (p. ej. 1:4) y usado antes de su fraguado"),
        (C, "Geometría", "Muro aplomado: desplome dentro de la tolerancia especificada (referencia usual ≤ 5 mm en 3 m - SUPUESTO)"),
        ("", "Geometría", "Hiladas niveladas y alineadas con el hilo; trabe de juntas correcto"),
        ("", "Juntas", "Juntas llenas, espesor uniforme (referencia usual 10 mm ± 3 mm - SUPUESTO)"),
        (C, "Confinamiento", "Columnetas y vigas de amarre según diseño y NSR-10 (esquinas, bordes de vanos, tramos largos)"),
        ("", "Vanos", "Vanos con medidas del plano de carpintería; dinteles o viga sobre vanos"),
        ("", "Instalaciones", "Regatas y pases coordinados antes de pañetar; no se rompe el bloque en exceso"),
        ("", "Limpieza", "Rebabas de mortero retiradas; muro humedecido/curado según especificación"),
    ]},
    "panetes": {"titulo": "Recibo de pañetes", "tipo": "CALIDAD", "items": [
        ("", "Preparación", "Superficie limpia, humedecida y con instalaciones embebidas probadas"),
        (C, "Planitud", "Planitud con regla de 3 m dentro de tolerancia (referencia usual ≤ 3 mm - SUPUESTO)"),
        ("", "Plomo y escuadra", "Aristas y filos rectos, a plomo y a escuadra"),
        (C, "Adherencia", "Sin zonas huecas al golpeteo, sin fisuras ni desprendimientos"),
        ("", "Espesor", "Espesor según especificación (p. ej. 1,5 cm) y dosificación correcta"),
        ("", "Curado", "Curado húmedo durante el tiempo especificado"),
        ("", "Dilataciones", "Dilataciones y remates contra carpinterías/cielos bien ejecutados"),
    ]},
    "enchapes": {"titulo": "Recibo de enchapes", "tipo": "CALIDAD", "items": [
        ("", "Material", "Referencia, lote y tono iguales a la muestra aprobada"),
        (C, "Adherencia", "Sin piezas huecas al golpeteo (pegante con llana dentada y doble encolado si aplica)"),
        ("", "Planitud", "Sin cejas entre piezas (referencia usual ≤ 1 mm - SUPUESTO); planitud con regla de 2 m"),
        ("", "Juntas", "Juntas uniformes, alineadas y emboquilladas completas; color de boquilla aprobado"),
        ("", "Pendientes", "Pendiente hacia sifones en zonas húmedas; sin empozamientos (prueba con agua)"),
        ("", "Cortes", "Cortes limpios, piezas completas en zonas visibles, remates y wings instalados"),
        ("", "Limpieza", "Superficie limpia, sin residuos de pegante ni boquilla"),
    ]},
    "drywall": {"titulo": "Recibo de cielo raso / muro en drywall", "tipo": "CALIDAD", "items": [
        ("", "Estructura", "Perfilería del calibre especificado; separación de omegas/parales según diseño (p. ej. 40-61 cm)"),
        (C, "Fijación", "Estructura colgada/anclada firme, sin deflexiones; cuelgues independientes de ductos y luminarias"),
        ("", "Placas", "Placas del tipo especificado (RH en zonas húmedas), juntas trabadas y sobre perfil"),
        ("", "Tornillería", "Tornillos a la separación especificada, cabeza a ras sin romper el papel"),
        (C, "Juntas", "Cinta y masilla en todas las juntas; sin fisuras ni marcas visibles con luz rasante"),
        ("", "Nivel", "Cielo nivelado (referencia usual ≤ 3 mm en 3 m - SUPUESTO); dilatación perimetral"),
        ("", "Coordinación", "Pases de luminarias, rejillas y detectores coordinados con las instalaciones"),
    ]},
    "pintura": {"titulo": "Recibo de pintura", "tipo": "CALIDAD", "items": [
        ("", "Preparación", "Superficie estucada, lijada, limpia y seca; resanes terminados"),
        ("", "Material", "Tipo y color aprobados (vinilo tipo 1 u otro especificado); producto dentro de su vigencia"),
        (C, "Manos", "Número de manos especificado; cubrimiento uniforme sin transparencias"),
        ("", "Acabado", "Sin chorreaduras, burbujas, marcas de rodillo ni cambios de tono"),
        ("", "Remates", "Filos, esquinas y encuentros con cielos y carpinterías limpios"),
        ("", "Protección", "Pisos, carpinterías y aparatos protegidos y limpios al terminar"),
    ]},
    "instalaciones": {"titulo": "Recibo de instalaciones (eléctricas / hidrosanitarias)", "tipo": "CALIDAD", "items": [
        (C, "Eléctricas", "Recorridos, calibres y protecciones según planos y RETIE (verificar en norma indexada)"),
        (C, "Eléctricas", "Pruebas de continuidad y aislamiento registradas; polaridad y puesta a tierra verificadas"),
        ("", "Eléctricas", "Cajas niveladas, aparatos firmes, tableros marcados con cuadro de circuitos"),
        (C, "Hidráulicas", "Prueba de presión de red de suministro registrada (presión y tiempo según especificación)"),
        (C, "Sanitarias", "Prueba de estanqueidad/hidrostática de desagües registrada; pendientes según diseño"),
        ("", "Hidrosanitarias", "Puntos en la localización y altura del plano; tapones en puntos sin aparato"),
        ("", "Coordinación", "Pases por estructura aprobados; sin interferencias con otras redes"),
    ]},
    "alturas": {"titulo": "Permiso de trabajo en alturas", "tipo": "SST", "items": [
        (C, "Documentos", "Permiso de trabajo diligenciado y firmado por el coordinador de alturas antes de iniciar"),
        (C, "Personal", "Trabajadores con certificado de capacitación en alturas vigente (Res. 4272/2021 - verificar en norma indexada)"),
        (C, "Personal", "Aptitud médica ocupacional para trabajo en alturas vigente"),
        ("", "Personal", "Afiliación a seguridad social y ARL vigente"),
        (C, "Equipos", "Arnés, eslingas, conectores y línea de vida inspeccionados pre-uso y en buen estado"),
        (C, "Anclajes", "Puntos de anclaje certificados o calculados por persona calificada"),
        ("", "Área", "Área delimitada y señalizada; control de caída de objetos"),
        (C, "Rescate", "Plan de emergencias y rescate disponible y conocido por el equipo"),
        ("", "Condiciones", "Condiciones climáticas adecuadas (sin lluvia fuerte, tormenta eléctrica ni viento fuerte)"),
        ("", "Supervisión", "Coordinador de trabajo en alturas presente/designado durante la tarea"),
    ]},
    "andamios": {"titulo": "Inspección de andamios", "tipo": "SST", "items": [
        (C, "Certificación", "Andamio certificado por el fabricante/proveedor; piezas originales y completas"),
        (C, "Base", "Apoyo sobre superficie firme y nivelada, con placas base o tornillos niveladores"),
        (C, "Estructura", "Crucetas y diagonales completas, pasadores y seguros instalados"),
        (C, "Plataforma", "Plataformas completas y aseguradas, sin huecos"),
        (C, "Barandas", "Baranda superior, intermedia y rodapié en todos los lados expuestos"),
        ("", "Acceso", "Escalera de acceso integrada o asegurada; no se trepa por crucetas"),
        ("", "Ruedas", "Ruedas con freno activado (andamio móvil); no se mueve con personas encima"),
        ("", "Anclaje", "Anclado a la estructura cuando la relación altura/base lo exige (según fabricante)"),
        ("", "Señalización", "Tarjeta de inspección (verde/roja) visible y firmada por persona competente"),
    ]},
}

TEMAS_CHARLA = {
    "alturas": ["Uso correcto del arnés y doble eslinga", "Inspección pre-uso", "Puntos de anclaje", "Plan de rescate"],
    "herramientas": ["Inspección de herramientas eléctricas", "Guardas y discos", "Cables y extensiones", "EPP: gafas, guantes"],
    "orden-aseo": ["Áreas de circulación libres", "Manejo de escombros", "Almacenamiento de materiales", "Puntos ecológicos"],
    "epp": ["Casco, botas, gafas, guantes y protección auditiva", "Estado y reposición", "Uso según la tarea"],
}


def _hoja_checklist(wb, clave: str, obra: str, lugar: str, fecha: date, enc: dict):
    lista = LISTAS[clave]
    ws = wb.create_sheet(clave.upper()[:28])
    for col, w in zip("ABCDEF", [5, 4, 16, 70, 12, 34]):
        ws.column_dimensions[col].width = w
    ws.merge_cells("A1:F1")
    _c(ws, "A1", f"{lista['tipo']} · {lista['titulo'].upper()}", F_TITULO, relleno=RELLENO_TITULO, alin=CENTRO)
    for k, (lab, val) in enumerate((("Obra", enc.get("objeto", obra)), ("Contrato N°", enc.get("contrato", "")),
                                    ("Localización / frente", lugar), ("Fecha", fecha.strftime("%d/%m/%Y")),
                                    ("Responsable", enc.get("elaboro", ""))), start=2):
        ws.merge_cells(f"A{k}:C{k}")
        _c(ws, f"A{k}", lab, F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"D{k}:F{k}")
        _c(ws, f"D{k}", val, F_ENTRADA, relleno=RELLENO_ENTRADA)
    h = 8
    for col, t in zip("ABCDEF", ["N°", "★", "Aspecto", "Criterio de aceptación", "Cumple\n(SI/NO/N.A.)", "Observación"]):
        _c(ws, f"{col}{h}", t, F_NEGRITA, relleno=RELLENO_CAP, alin=CENTRO)
    ws.row_dimensions[h].height = 26
    dv = DataValidation(type="list", formula1='"SI,NO,N.A."', allow_blank=True)
    ws.add_data_validation(dv)
    ini = h + 1
    for n, (crit, aspecto, criterio) in enumerate(lista["items"], start=1):
        r = h + n
        _c(ws, f"A{r}", n, F_NORMAL, alin=CENTRO)
        _c(ws, f"B{r}", crit, Font(name="Arial", size=10, bold=True, color="C00000"), alin=CENTRO)
        _c(ws, f"C{r}", aspecto, F_NORMAL)
        _c(ws, f"D{r}", criterio, F_NORMAL, alin=Alignment(wrap_text=True, vertical="center"))
        _c(ws, f"E{r}", None, F_ENTRADA, relleno=RELLENO_ENTRADA, alin=CENTRO)
        _c(ws, f"F{r}", None, F_ENTRADA, relleno=RELLENO_ENTRADA, alin=Alignment(wrap_text=True))
        dv.add(f"E{r}")
        ws.row_dimensions[r].height = 30
    fin = h + len(lista["items"])
    ws.conditional_formatting.add(f"E{ini}:E{fin}", CellIsRule(operator="equal", formula=['"NO"'],
                                                               fill=PatternFill("solid", fgColor="FFC7CE")))
    ws.conditional_formatting.add(f"E{ini}:E{fin}", CellIsRule(operator="equal", formula=['"SI"'],
                                                               fill=PatternFill("solid", fgColor="C6EFCE")))
    r = fin + 2
    rot = [("Ítems evaluados", f'=COUNTIF(E{ini}:E{fin},"SI")+COUNTIF(E{ini}:E{fin},"NO")', "0"),
           ("% de cumplimiento", f'=IF(B{r}=0,0,COUNTIF(E{ini}:E{fin},"SI")/B{r})', PCT),
           ("Críticos con NO", f'=COUNTIFS(B{ini}:B{fin},"{C}",E{ini}:E{fin},"NO")', "0"),
           ("Sin diligenciar", f'=COUNTBLANK(E{ini}:E{fin})', "0")]
    for k, (lab, f, fmt) in enumerate(rot):
        ws.merge_cells(f"C{r + k}:D{r + k}")
        _c(ws, f"C{r + k}", lab, F_NEGRITA, relleno=RELLENO_SUB, alin=Alignment(horizontal="right"))
        _c(ws, f"E{r + k}", f.replace(f"B{r}", f"E{r}"), F_NEGRITA, fmt, alin=CENTRO)
    res = r + len(rot)
    ws.merge_cells(f"C{res}:D{res}")
    _c(ws, f"C{res}", "RESULTADO", F_NEGRITA, relleno=RELLENO_TOTAL, alin=Alignment(horizontal="right"))
    ws.merge_cells(f"E{res}:F{res}")
    _c(ws, f"E{res}", f'=IF(E{r + 3}>0,"PENDIENTE: faltan ítems por diligenciar",IF(E{r + 2}>0,"NO APROBADO: ítem crítico",'
                      f'IF(E{r + 1}>=0.9,"APROBADO","APROBADO CON OBSERVACIONES")))', F_NEGRITA, relleno=RELLENO_TOTAL, alin=CENTRO)
    _c(ws, f"A{res + 2}", "Criterios de práctica usual de obra. Las tolerancias marcadas SUPUESTO deben confirmarse con las "
                          "especificaciones del proyecto y la norma indexada.", Font(name="Arial", size=8, italic=True), borde=False)
    fr = res + 5
    for c1, c2, t in (("A", "D", "Residente de obra"), ("E", "F", "Interventoría / SST")):
        ws.merge_cells(f"{c1}{fr}:{c2}{fr}")
        _c(ws, f"{c1}{fr}", f"______________________\n{t}", F_NORMAL, alin=CENTRO, borde=False)
        ws.row_dimensions[fr].height = 36
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToHeight = 0
    return ws


def _hoja_charla(wb, obra, fecha, enc, tema="alturas"):
    ws = wb.create_sheet("CHARLA 5 MIN")
    for col, w in zip("ABCDE", [5, 34, 22, 18, 24]):
        ws.column_dimensions[col].width = w
    ws.merge_cells("A1:E1")
    _c(ws, "A1", "SST · CHARLA DE 5 MINUTOS", F_TITULO, relleno=RELLENO_TITULO, alin=CENTRO)
    for k, (lab, val) in enumerate((("Obra", enc.get("objeto", obra)), ("Fecha / hora", f"{fecha:%d/%m/%Y}  ____:____"),
                                    ("Tema", tema), ("Dirigida por", enc.get("elaboro", ""))), start=2):
        ws.merge_cells(f"A{k}:B{k}")
        _c(ws, f"A{k}", lab, F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"C{k}:E{k}")
        _c(ws, f"C{k}", val, F_ENTRADA, relleno=RELLENO_ENTRADA)
    r = 7
    _c(ws, f"A{r}", "Puntos clave", F_NEGRITA, relleno=RELLENO_CAP)
    ws.merge_cells(f"A{r}:E{r}")
    for p in TEMAS_CHARLA.get(tema, ["(escriba los puntos)"]):
        r += 1
        ws.merge_cells(f"A{r}:E{r}")
        _c(ws, f"A{r}", f"• {p}", F_NORMAL)
    r += 2
    for col, t in zip("ABCDE", ["N°", "Nombre", "Cargo", "Empresa", "Firma"]):
        _c(ws, f"{col}{r}", t, F_NEGRITA, relleno=RELLENO_CAP, alin=CENTRO)
    for n in range(1, 16):
        for col in "ABCDE":
            _c(ws, f"{col}{r + n}", n if col == "A" else None, F_NORMAL, alin=CENTRO)
        ws.row_dimensions[r + n].height = 20
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToHeight = 0


def generar(obra: str, clave: str, lugar: str = "", fecha: date | None = None, tema_charla: str = "alturas"):
    fecha = fecha or date.today()
    enc = D.encabezado_obra(obra)
    wb = Workbook()
    wb.remove(wb.active)
    claves = list(LISTAS) if clave == "todas" else [clave]
    for k in claves:
        if k == "charla":
            continue
        if k not in LISTAS:
            raise KeyError(f"Lista desconocida: {k}. Opciones: {', '.join(LISTAS)}, charla, todas")
        _hoja_checklist(wb, k, obra, lugar, fecha, enc)
    if clave in ("todas", "charla"):
        _hoja_charla(wb, obra, fecha, enc, tema_charla)
    destino = D.salidas(obra) / f"Checklist_{clave}_{fecha:%Y-%m-%d}.xlsx"
    wb.save(destino)
    return destino


def main(argv=None):
    ap = argparse.ArgumentParser(description="Listas de chequeo de calidad y SST")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("listar")
    g = sub.add_parser("generar")
    g.add_argument("obra")
    g.add_argument("clave")
    g.add_argument("--lugar", default="")
    g.add_argument("--fecha")
    g.add_argument("--tema", default="alturas", help=f"tema de la charla: {', '.join(TEMAS_CHARLA)}")
    a = ap.parse_args(argv)
    if a.cmd == "listar":
        for k, v in LISTAS.items():
            print(f"{k:14s} {v['tipo']:8s} {v['titulo']} ({len(v['items'])} ítems)")
        print(f"{'charla':14s} SST      Charla de 5 minutos (temas: {', '.join(TEMAS_CHARLA)})")
        return
    f = generar(a.obra, a.clave, a.lugar, date.fromisoformat(a.fecha) if a.fecha else None, a.tema)
    from .revisor_calidad import revisar
    ok, _, _ = revisar(f, entregar=True)
    print(f"Lista: {f}  ·  revisor: {'APROBADO' if ok else 'NO APROBADO'}")


if __name__ == "__main__":
    main()
