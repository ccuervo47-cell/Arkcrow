"""Base de datos local de precios (SQLite).

Tabla `insumos`: mano de obra (MO), equipos (EQ), materiales (MAT) y tarifas de transporte (TR).
Cada material indica cómo se transporta:
  transp_tipo = 'ton'      -> se multiplica la cantidad por transp_factor (toneladas por unidad)
  transp_tipo = 'm3'       -> se multiplica la cantidad por transp_factor (m³ por unidad)
  transp_tipo = 'incluido' -> el precio ya incluye el transporte (p. ej. concreto premezclado)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DB_PATH = RAIZ / "datos" / "arkcrow.sqlite"

FUENTE_PRUEBA = "Precios de la prueba técnica, oct-2026, POR ACTUALIZAR"
FUENTE_SUPUESTO = "SUPUESTO ARKCROW (precio estimado de mercado Bogotá) - VERIFICAR CON COTIZACIÓN"

# codigo, tipo, descripcion, unidad, precio, transp_tipo, transp_factor, fuente
SEMILLA = [
    # --- Mano de obra (jornal) ---
    ("MO-ARQ", "MO", "Arquitecto", "jornal", 200000, None, None, FUENTE_PRUEBA),
    ("MO-RES", "MO", "Residente", "jornal", 150000, None, None, FUENTE_PRUEBA),
    ("MO-OFI", "MO", "Oficial", "jornal", 60000, None, None, FUENTE_PRUEBA),
    ("MO-INS", "MO", "Instalador", "jornal", 80000, None, None, FUENTE_PRUEBA),
    ("MO-AYU", "MO", "Ayudante", "jornal", 60000, None, None, FUENTE_PRUEBA),
    ("MO-ELE", "MO", "Técnico electricista", "jornal", 80000, None, None, FUENTE_PRUEBA),
    # --- Equipos (tarifa de alquiler por día) ---
    ("EQ-AND", "EQ", "Andamio multidireccional", "día", 22000, None, None, FUENTE_PRUEBA),
    ("EQ-ARN", "EQ", "Arnés + eslinga + línea de vida", "día", 15800, None, None, FUENTE_PRUEBA),
    ("EQ-ASP", "EQ", "Aspiradora industrial", "día", 18000, None, None, FUENTE_PRUEBA),
    ("EQ-BOQ", "EQ", "Boquillera", "día", 6500, None, None, FUENTE_PRUEBA),
    ("EQ-CAR", "EQ", "Carretilla", "día", 10800, None, None, FUENTE_PRUEBA),
    ("EQ-COR", "EQ", "Cortadora de enchape", "día", 8500, None, None, FUENTE_PRUEBA),
    ("EQ-ESC", "EQ", "Escalera certificada", "día", 20300, None, None, FUENTE_PRUEBA),
    ("EQ-ESP", "EQ", "Espátula", "día", 6500, None, None, FUENTE_PRUEBA),
    ("EQ-HME", "EQ", "Herramienta menor (tarifa de alquiler; se recomienda usar % de MO)", "día", 10500, None, None, FUENTE_PRUEBA),
    ("EQ-LLA", "EQ", "Llana metálica", "día", 7000, None, None, FUENTE_PRUEBA),
    ("EQ-MAS", "EQ", "Mascarilla", "día", 8900, None, None, FUENTE_PRUEBA),
    ("EQ-MUL", "EQ", "Multímetro / probador de red", "día", 28000, None, None, FUENTE_PRUEBA),
    ("EQ-PAL", "EQ", "Pala", "día", 6500, None, None, FUENTE_PRUEBA),
    ("EQ-PLU", "EQ", "Palustre", "día", 6000, None, None, FUENTE_PRUEBA),
    ("EQ-PUL", "EQ", "Pulidora con disco", "día", 15000, None, None, FUENTE_PRUEBA),
    ("EQ-ROD", "EQ", "Rodillo", "día", 4500, None, None, FUENTE_PRUEBA),
    ("EQ-TPE", "EQ", "Taladro percutor", "día", 20500, None, None, FUENTE_PRUEBA),
    ("EQ-TIN", "EQ", "Taladro inalámbrico", "día", 15300, None, None, FUENTE_PRUEBA),
    ("EQ-PIS", "EQ", "Pistola de calafateo", "día", 4000, None, None, FUENTE_PRUEBA),
    ("EQ-VIB", "EQ", "Vibrador de manguera", "día", 18000, None, None, FUENTE_PRUEBA),
    # --- Materiales de la prueba ---
    ("MAT-CON3000", "MAT", "Concreto premezclado 3000 psi", "m³", 560000, "incluido", None, FUENTE_PRUEBA),
    ("MAT-ACE60", "MAT", "Acero de refuerzo 60.000 psi", "kg", 5200, "ton", 0.001, FUENTE_PRUEBA),
    ("MAT-CEM", "MAT", "Cemento gris (bulto 50 kg)", "bulto", 34000, "ton", 0.050, FUENTE_PRUEBA),
    ("MAT-ARE", "MAT", "Arena lavada", "m³", 95000, "m3", 1.0, FUENTE_PRUEBA),
    ("MAT-BLQ4", "MAT", "Bloque de arcilla No. 4", "und", 1300, "ton", 0.0037, FUENTE_PRUEBA),
    ("MAT-EST", "MAT", "Estuco plástico", "kg", 2200, "ton", 0.001, FUENTE_PRUEBA),
    ("MAT-PVT1", "MAT", "Pintura vinilo tipo 1", "gal", 85000, "ton", 0.0055, FUENTE_PRUEBA),
    ("MAT-PYE12", "MAT", "Placa de yeso 1/2\" (1,22 x 2,44 m)", "und", 32000, "ton", 0.026, FUENTE_PRUEBA),
    ("MAT-LAM8", "MAT", "Piso laminado AC4 8 mm", "m²", 75000, "ton", 0.0075, FUENTE_PRUEBA),
    ("MAT-GPVC", "MAT", "Guardaescoba PVC", "ml", 9500, "ton", 0.0006, FUENTE_PRUEBA),
    # --- Materiales complementarios (SUPUESTOS, por verificar) ---
    ("MAT-ALA", "MAT", "Alambre negro calibre 18", "kg", 7500, "ton", 0.001, FUENTE_SUPUESTO),
    ("MAT-VIG", "MAT", "Perfil vigueta (canal) cal. 26 x 2,44 m", "und", 11500, "ton", 0.0016, FUENTE_SUPUESTO),
    ("MAT-OMG", "MAT", "Perfil omega cal. 26 x 2,44 m", "und", 9800, "ton", 0.0013, FUENTE_SUPUESTO),
    ("MAT-ANG", "MAT", "Ángulo perimetral cal. 26 x 2,44 m", "und", 7200, "ton", 0.0008, FUENTE_SUPUESTO),
    ("MAT-TDW", "MAT", "Tornillo drywall 6 x 1\"", "und", 45, "ton", 0.000003, FUENTE_SUPUESTO),
    ("MAT-CHZ", "MAT", "Chazo plástico + tornillo de fijación", "und", 600, "ton", 0.00001, FUENTE_SUPUESTO),
    ("MAT-CIN", "MAT", "Cinta de papel para juntas", "ml", 160, "ton", 0.000005, FUENTE_SUPUESTO),
    ("MAT-MAS", "MAT", "Masilla para drywall", "kg", 3400, "ton", 0.001, FUENTE_SUPUESTO),
    ("MAT-ESP2", "MAT", "Espuma (manto) para piso laminado 2 mm", "m²", 4500, "ton", 0.0002, FUENTE_SUPUESTO),
    ("MAT-SIL", "MAT", "Adhesivo / silicona para guardaescoba (cartucho)", "und", 14000, "ton", 0.0003, FUENTE_SUPUESTO),
    ("MAT-FOR", "MAT", "Formaleta de borde en madera (tabla 3 m, 3 usos)", "ml", 4500, "ton", 0.004, FUENTE_SUPUESTO),
    # --- Transporte ---
    ("TR-TON", "TR", "Transporte por tonelada-kilómetro", "ton-km", 3500, None, None, FUENTE_PRUEBA),
    ("TR-M3", "TR", "Transporte por metro cúbico-kilómetro", "m³-km", 2500, None, None, FUENTE_PRUEBA),
]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS insumos (
    codigo        TEXT PRIMARY KEY,
    tipo          TEXT NOT NULL CHECK (tipo IN ('MO','EQ','MAT','TR')),
    descripcion   TEXT NOT NULL,
    unidad        TEXT NOT NULL,
    precio        REAL NOT NULL,
    transp_tipo   TEXT,
    transp_factor REAL,
    fuente        TEXT NOT NULL,
    fecha_precio  TEXT NOT NULL DEFAULT '2026-10',
    estado        TEXT NOT NULL DEFAULT 'POR ACTUALIZAR'
);
"""


def conectar(ruta: Path | str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    return con


def inicializar(ruta: Path | str = DB_PATH, reemplazar: bool = False) -> int:
    """Crea la base y carga la semilla. No sobrescribe precios existentes salvo `reemplazar`."""
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    con = conectar(ruta)
    con.executescript(ESQUEMA)
    verbo = "INSERT OR REPLACE" if reemplazar else "INSERT OR IGNORE"
    con.executemany(
        f"{verbo} INTO insumos (codigo,tipo,descripcion,unidad,precio,transp_tipo,transp_factor,fuente) "
        "VALUES (?,?,?,?,?,?,?,?)",
        SEMILLA,
    )
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM insumos").fetchone()[0]
    con.close()
    return n


def insumos(ruta: Path | str = DB_PATH) -> dict[str, dict]:
    con = conectar(ruta)
    filas = {r["codigo"]: dict(r) for r in con.execute("SELECT * FROM insumos ORDER BY tipo, codigo")}
    con.close()
    return filas


if __name__ == "__main__":
    print(f"Insumos en la base: {inicializar()} -> {DB_PATH}")
