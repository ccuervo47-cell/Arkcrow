# ARKCROW OBRA: asistente del arquitecto residente

Asistente de IA para obra que funciona **con y sin internet**, a **costo cero**. Hace:
- APU, memorias de cantidades y balances con fórmulas vivas, más un auditor que los revisa;
- bitácora diaria, actas de corte, ítems no previstos, cronograma y listas de chequeo;
- borradores de comunicaciones;
- consultas a normas con cita de documento y página.

Todo vive en esta carpeta (recomendado: `C:\ArkcrowObra`), así que respaldarla es copiarla.

---

## 1. Instalación (una sola vez, con internet)

### Windows
1. Copie la carpeta `ArkcrowObra` a `C:\ArkcrowObra`. Evite rutas con espacios.
2. Haga doble clic en **`INSTALAR.bat`**.
3. El instalador hace todo esto, **sin permisos de administrador**:
   - revisa la RAM, la tarjeta gráfica y el disco, y **elige el modelo de IA** adecuado:

     | RAM del equipo | Modelo principal | Respaldo |
     |---|---|---|
     | menos de 8 GB | qwen2.5:1.5b | — |
     | 8 GB | qwen2.5:3b | qwen2.5:1.5b |
     | 16 GB (o GPU NVIDIA de 6 GB o más) | qwen2.5:7b | qwen2.5:3b |
     | 32 GB (o GPU NVIDIA de 12 GB o más) | qwen2.5:14b | qwen2.5:7b |

   - instala Python (si falta) y Ollama **solo para su usuario**;
   - descarga los modelos (entre 2,7 y 12 GB según el equipo), el modelo de embeddings `bge-m3` y el de voz `whisper-small`;
   - indexa los documentos, corre las pruebas, hace el primer respaldo y crea el acceso directo **ARKCROW OBRA** en el escritorio.
4. **Antes de cada descarga o instalación pregunta (S/N).** No cambia el antivirus, el firewall ni las políticas del equipo.

Si sistemas (TI) bloquea los scripts o los instaladores, pídales:
- permitir ejecutar `INSTALAR.bat` una vez (usa `-ExecutionPolicy Bypass` **solo para ese proceso**);
- o instalar "Python 3.12" y "Ollama" para su usuario.

El registro de la instalación queda en `instalacion.log`.

### Linux / Mac
Ejecute `./instalar.sh` (para ver el plan sin instalar nada: `./instalar.sh --simular`). En Linux, Ollama se instala con el comando oficial, que pide `sudo`.

---

## 2. Uso diario
- **Abrir:** doble clic en **ARKCROW OBRA** (escritorio) o en `iniciar.bat`. Se abre el chat en el navegador; cierre la ventana negra para salir.
- **Consola:** `iniciar_consola.bat` (o `./iniciar.sh --consola`).
- **Al iniciar** muestra el **modo**, la **obra activa** y la **cola** de pendientes.
- **Cada respuesta dice con qué se generó:**
  - `[OFFLINE · modelo local qwen2.5:7b]`: sin internet, todo en el equipo;
  - `[ONLINE · búsqueda web gratuita + modelo local …]`: buscó en internet gratis y resumió con el modelo local;
  - si la conexión cambia, avisa con **🔄 CAMBIO DE MODO**.
- **Citas:** toda respuesta que sale de sus documentos se cita como `[archivo, p. N]`. Si la norma no está en la base local, lo dice y no la inventa.

### Comandos del chat de consola

| Comando | Para qué |
|---|---|
| `/obra <nombre>` | Cambiar la obra activa |
| `/buscar <texto>` | Ver los fragmentos de documentos que coinciden |
| `/cola` · `/encolar` · `/aprobar <id>` · `/ejecutar` | Tareas "cuando haya internet" (solo se ejecuta lo que usted aprueba) |
| `/memoria` · `/aplicar <id>` | Revisar y confirmar lo que el asistente propone recordar |
| `/respaldo` | Respaldo inmediato |
| `/local <pregunta>` | Forzar que no use internet |

### Herramientas de obra (skills)
Cada una tiene su manual en `skills/<nombre>/SKILL.md`. Atajo: `python skills/<nombre>/scripts/run.py ...`

| Necesito… | Skill |
|---|---|
| APU, memoria y balance con AIU + auditoría | `presupuesto-balance`, `apu`, `memoria-cantidades` |
| Revisar un Excel/Word/PDF antes de entregarlo | `revisor-calidad` (obligatorio) |
| Acta de corte con avance y semáforo | `cortes-actas` |
| Ítem no previsto con APU y oficio | `items-no-previstos` |
| Bitácora diaria / informe semanal (texto o voz) | `bitacora-informe-diario` |
| Organizar fotos y anexo fotográfico | `registro-fotografico` |
| Cronograma, Gantt y ruta crítica | `cronograma` |
| Listas de chequeo de calidad y SST | `calidad-sst-checklists` |
| Correos, oficios, actas de comité (borradores) | `comunicaciones` |
| Cantidades desde IFC (Revit) o planos PDF | `lectura-planos-bim` |
| Consultar normas con cita | `normativa-co` |

Los entregables quedan en `proyectos/<obra>/salidas/` con nombre y fecha.

---

## 3. Costo cero
- **Sin internet:** el modelo local responde con la base local.
- **Con internet:** las preguntas que lo necesitan ("busca…", "precio actual…", "norma vigente…") van a una **búsqueda web gratuita** (DuckDuckGo, y Wikipedia como respaldo) y el modelo local resume y cita las URL.
- **Qué sale del equipo:** solo el texto de la búsqueda; sus documentos nunca. Si la pregunta parece confidencial, pide permiso antes de buscar.
- **Nube de pago:** existe como opción, pero viene **apagada** (`ARKCROW_NUBE_DE_PAGO=no` en `.env`). Solo se activa si usted pone `si` y una clave. Tiene costo por uso.

---

## 4. Agregar normas, documentos y precios
- **Normas:** guarde el PDF oficial en `conocimiento/normas/`. La lista sugerida está en `conocimiento/normas/LEEME.md` (NSR-10, RETIE, RETILAP, RAS, NTC 1500, Res. 3100/2019, Dec. 1072/2015, Res. 0312/2019, Res. 4272/2021).
- **Documentos de la obra:** van en `conocimiento/obras/<obra>/`.
- **Lo confidencial** (contratos, presupuestos internos) va en `conocimiento/confidencial/`, o con "CONFIDENCIAL" en el nombre del archivo.
- **Reindexar:** después de agregar archivos, use el botón **Reindexar documentos** del chat, o `python -m arkcrow.conocimiento indexar`.
- **Precios:**
  - están en `datos/arkcrow.sqlite` (tabla `insumos`) y en `conocimiento/precios/precios_base.md`;
  - los de la prueba técnica (oct-2026) están marcados **POR ACTUALIZAR**, y los complementarios **SUPUESTO**;
  - para cambiarlos, edite la tabla con "DB Browser for SQLite" o pídale al asistente una propuesta (`actualizar_precios` en la cola). La base nunca se cambia sola.

---

## 5. Cambiar de modelo
1. Descargue el modelo con internet, por ejemplo `ollama pull qwen2.5:14b`.
2. En `.env`, cambie `ARKCROW_MODELO=` (principal) y `ARKCROW_MODELO_RESP=` (respaldo).
3. Si el equipo se pone lento, use uno más pequeño (`qwen2.5:3b`).

---

## 6. Respaldos
- `iniciar.bat` hace un respaldo **diario y verificado** de `memoria/`, `proyectos/` y las bases de datos.
- Para guardarlos en una USB o en la nube de la empresa: en `.env`, `ARKCROW_RESPALDOS=E:\RespaldosArkcrow`.
- Se conservan los últimos 30 (`ARKCROW_RESPALDOS_MAX`).
- Para restaurar, descomprima el .zip sobre la carpeta ArkcrowObra.

---

## 7. Solución de problemas

| Síntoma | Qué hacer |
|---|---|
| La etiqueta dice "solo búsqueda" | Ollama no está corriendo o falta el modelo. Abra `iniciar.bat` otra vez; en la consola, `ollama list` debe mostrar el modelo |
| Responde lento (más de 30 s) | Cierre programas pesados o use el modelo de respaldo (más pequeño) en `.env` |
| "No tengo NSR-10 en la base local" | Agregue el PDF a `conocimiento/normas/` y reindexe |
| El revisor dice "No hay motor de cálculo" | Necesita Excel (con `pywin32`, ya instalado) o LibreOffice |
| No abre el navegador | Abra a mano `http://127.0.0.1:8765` |
| La búsqueda web no devuelve nada | El proxy o firewall de la empresa puede bloquear DuckDuckGo; use la cola cuando esté en otra red |
| Error de pip o descargas en la instalación | Proxy corporativo: el instalador lo detecta, pero si pide usuario y clave, hable con TI |

Pruebas automáticas: `.venv\Scripts\python -m unittest discover tests -v`

---

## 8. Estructura
```
ArkcrowObra/
  INSTALAR.bat · instalar.ps1 · instalar.sh      instalación
  iniciar.bat · iniciar_consola.bat · iniciar.sh  uso diario
  AGENTS.md · CLAUDE.md                           instrucciones del agente (Codex / Claude Code)
  .env.example                                    configuración (copiar a .env)
  nucleo/arkcrow/                                 motor (Python)
  skills/ (+ .claude/skills/)                     13 skills
  memoria/  conocimiento/  proyectos/  plantillas/  datos/  respaldos/  modelos/  tests/
```
