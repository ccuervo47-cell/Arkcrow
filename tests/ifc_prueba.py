"""Construye un IFC sintético de la sala de juntas (muros a ejes 3,68 x 3,24 m, h = 3,00 m, e = 0,14 m,
puerta P-101 0,85 x 2,10 y ventana V-39 1,50 x 1,20) para probar la lectura de IFC."""
from pathlib import Path

import numpy as np


def _ubicar(api, f, elem, x, y, z=0.0, rot=0.0):
    c, s = np.cos(rot), np.sin(rot)
    mat = np.array([[c, -s, 0, x], [s, c, 0, y], [0, 0, 1, z], [0, 0, 0, 1]], dtype=float)
    api.geometry.edit_object_placement(f, product=elem, matrix=mat, is_si=True)


def crear(destino: Path) -> Path:
    import importlib

    import ifcopenshell.api as api
    for sub in ("project", "root", "unit", "context", "aggregate", "geometry", "spatial", "feature", "pset"):
        importlib.import_module(f"ifcopenshell.api.{sub}")
    f = api.project.create_file(version="IFC4")
    proj = api.root.create_entity(f, ifc_class="IfcProject", name="Sala de juntas (prueba)")
    api.unit.assign_unit(f)
    ctx = api.context.add_context(f, context_type="Model")
    body = api.context.add_context(f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=ctx)
    site = api.root.create_entity(f, ifc_class="IfcSite", name="Obra")
    bld = api.root.create_entity(f, ifc_class="IfcBuilding", name="Edificio")
    piso = api.root.create_entity(f, ifc_class="IfcBuildingStorey", name="Piso 1")
    api.aggregate.assign_object(f, relating_object=proj, products=[site])
    api.aggregate.assign_object(f, relating_object=site, products=[bld])
    api.aggregate.assign_object(f, relating_object=bld, products=[piso])
    e, h = 0.14, 3.0
    # muros a ejes: (nombre, x, y, rot, largo)
    datos = [("Eje 1", 0.0, 0.0, 0.0, 3.68), ("Eje 2", 0.0, 3.24, 0.0, 3.68),
             ("Eje A", 0.0, 0.0, np.pi / 2, 3.24), ("Eje B", 3.68, 0.0, np.pi / 2, 3.24)]
    muros = {}
    for nombre, x, y, rot, largo in datos:
        w = api.root.create_entity(f, ifc_class="IfcWall", name=nombre)
        rep = api.geometry.add_wall_representation(f, context=body, length=largo, height=h, thickness=e)
        api.geometry.assign_representation(f, product=w, representation=rep)
        _ubicar(api, f, w, x, y, 0, rot)
        api.spatial.assign_container(f, relating_structure=piso, products=[w])
        muros[nombre] = (w, x, y, rot)

    def vano(muro, marca, clase, ancho, alto, desde, antepecho):
        w, x, y, rot = muros[muro]
        op = api.root.create_entity(f, ifc_class="IfcOpeningElement", name=f"Vano {marca}")
        rep = api.geometry.add_wall_representation(f, context=body, length=ancho, height=alto, thickness=e + 0.02)
        api.geometry.assign_representation(f, product=op, representation=rep)
        c, s = np.cos(rot), np.sin(rot)
        _ubicar(api, f, op, x + desde * c, y + desde * s, antepecho, rot)
        api.feature.add_feature(f, feature=op, element=w)
        el = api.root.create_entity(f, ifc_class=clase, name=marca)
        el.OverallWidth, el.OverallHeight = ancho, alto
        _ubicar(api, f, el, x + desde * c, y + desde * s, antepecho, rot)
        api.feature.add_filling(f, opening=op, element=el)
        api.spatial.assign_container(f, relating_structure=piso, products=[el])

    vano("Eje 1", "P-101", "IfcDoor", 0.85, 2.10, 0.6, 0.0)
    vano("Eje 2", "V-39", "IfcWindow", 1.50, 1.20, 1.1, 0.9)
    sp = api.root.create_entity(f, ifc_class="IfcSpace", name="101")
    sp.LongName = "Sala de juntas"
    api.aggregate.assign_object(f, relating_object=piso, products=[sp])
    qto = api.pset.add_qto(f, product=sp, name="Qto_SpaceBaseQuantities")
    api.pset.edit_qto(f, qto=qto, properties={"NetFloorArea": 3.54 * 3.10, "NetPerimeter": 2 * (3.54 + 3.10)})
    destino.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(destino))
    return destino
