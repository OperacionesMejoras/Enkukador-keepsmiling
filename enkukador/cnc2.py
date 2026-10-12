"""Salida CNC2: modelo alineado + chapa con ID y movimiento + ranuras + marca.

Como el GH, sin booleanas: todo se concatena en un STL. Las piezas, medidas
sobre salidas CNC2 reales (caso AP962, Modelos planos V5):

- Chapa de 2 mm (z 0..2) entre las ramas de la arcada: una banda de 4,25 mm
  de alto con el ID y, al centro, una lengüeta de 8,8 mm de ancho con el número
  de movimiento. Los costados y la punta se recortan con el borde interno de la
  arcada, metiéndose en el material para quedar unidos. La punta queda 8,83 mm
  arriba del borde inferior de la banda. El texto va calado (atraviesa la
  chapa), en Arial Bold de 2,3 mm de alto (acá Liberation Sans Bold, que tiene
  las mismas medidas).
- Ranuras para los extractores: dos cavidades fijas (mallas invertidas), las
  mismas en todos los modelos; se copian de una salida real.
- Marca de orientación: pestaña de 0,76 x 3 x 1,5 mm en x=0 que asoma ~1 mm por
  delante de la arcada.

El GH ubicaba la chapa con su propia curva de contorno suavizada; acá se usa el
contorno real a 0,5 mm. Comparado con las salidas del GH la chapa queda a unos
±0,3 mm de posición; forma, medidas y texto son los mismos.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import numpy as np
import trimesh
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from . import arco

DATOS = Path(__file__).parent / "datos"
FUENTES = (
    # Arial Bold real en Windows (la que usaba el GH); en Linux, sus equivalentes.
    str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arialbd.ttf"),
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)

ESPESOR = 2.0
ALTO_BANDA = 4.25
ANCHO_LENGUETA = 8.8
ALTO_TOTAL = 8.83  # del borde inferior a la punta, en x=0
SOLAPE = 1.2  # cuánto se mete la chapa en la arcada
ALTO_LETRA = 2.3
SEPARACION_ID = 0.7  # entre caracteres, como el deslizador del GH
SEPARACION_MOV = 0.5
Y_ID = 0.95  # base del ID sobre el borde inferior
Y_MOV = 3.98  # base del movimiento
MARCA = (0.76, 3.0, 1.5)  # ancho, largo, alto
MARCA_ASOMA = 1.0


@cache
def _ranuras() -> trimesh.Trimesh:
    # Guardadas como datos numéricos y no como STL: ni el repo ni el instalador llevan mallas.
    d = np.load(DATOS / "ranuras_cnc2.npz")
    return trimesh.Trimesh(d["vertices"].astype(float), d["caras"], process=False)


def _fuente() -> str | None:
    return next((f for f in FUENTES if Path(f).exists()), None)


def texto(contenido: str, alto: float, separacion: float | None = None) -> Polygon:
    """Contorno 2D del texto, centrado en x=0, con la base en y=0 y `alto` de mayúscula.

    Con `separacion`, cada carácter se ubica suelto dejando ese espacio entre
    uno y otro (como hacía el GH); si no, con el espaciado propio de la fuente.
    """
    if separacion is not None and len(contenido) > 1:
        glifos, x = [], 0.0
        for ch in contenido:
            g = texto(ch, alto)
            ancho = g.bounds[2] - g.bounds[0]
            glifos.append(affinity.translate(g, x + ancho / 2, 0))
            x += ancho + separacion
        forma = unary_union(glifos)
        x0, _, x1, _ = forma.bounds
        return affinity.translate(forma, -(x0 + x1) / 2, 0)
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath

    fuente = _fuente()
    props = FontProperties(fname=fuente) if fuente else FontProperties(weight="bold")
    camino = TextPath((0, 0), contenido, size=10, prop=props)
    forma = Polygon()
    for anillo in camino.to_polygons():
        if len(anillo) >= 3:
            forma = forma.symmetric_difference(
                Polygon(anillo).buffer(0)
            )  # par-impar: huecos de A, P, 6...
    x0, y0, x1, y1 = forma.bounds
    k = alto / (y1 - y0)
    forma = affinity.scale(forma, k, k, origin=(0, 0))
    x0, y0, x1, y1 = forma.bounds
    return affinity.translate(forma, -(x0 + x1) / 2, -y0)


def _cruces_x0(contorno: Polygon) -> list[float]:
    cr = contorno.exterior.intersection(LineString([(0, -200), (0, 200)]))
    return sorted(g.y for g in getattr(cr, "geoms", [cr]) if hasattr(g, "y"))


def chapa(contorno: Polygon, id_caso: str, movimiento: str) -> trimesh.Trimesh:
    """Chapa con texto calado, en el marco alineado (contorno de la arcada a 0,5 mm)."""
    ys = _cruces_x0(contorno)
    if len(ys) < 2:
        raise ValueError("no se encontró el borde interno de la arcada en x=0")
    interno = ys[0]  # el primer cruce desde abajo es la orilla lingual, adelante
    tope = interno + SOLAPE
    y0 = tope - ALTO_TOTAL

    # Paladar ensanchado: recorta costados y punta, metiéndose en la arcada. Si
    # el corte trae huecos chicos (agujeros de la base), no son el paladar.
    detras = Point(0, interno - 1.0)
    huecos = [Polygon(r) for r in contorno.interiors if Polygon(r).contains(detras)]
    limite = (huecos[0] if huecos else _paladar(contorno, interno)).buffer(SOLAPE)

    banda = box(-50, y0, 50, y0 + ALTO_BANDA)
    lengueta = box(-ANCHO_LENGUETA / 2, y0, ANCHO_LENGUETA / 2, tope + 5)
    forma = unary_union([banda, lengueta]).intersection(limite)
    forma = forma.buffer(0.6).buffer(-0.6)  # redondeo en los encuentros, como el original
    if forma.geom_type != "Polygon":
        forma = max(forma.geoms, key=lambda g: g.area)

    letras = unary_union(
        [
            affinity.translate(texto(id_caso, ALTO_LETRA, SEPARACION_ID), 0, y0 + Y_ID),
            affinity.translate(texto(movimiento, ALTO_LETRA, SEPARACION_MOV), 0, y0 + Y_MOV),
        ]
    )
    # Como el GH, se cala solo el contorno exterior de cada carácter: los
    # interiores (A, P, 6, 9, 0) no quedan como islas sueltas.
    partes = getattr(letras, "geoms", [letras])
    letras = unary_union([Polygon(p.exterior) for p in partes])
    forma = forma.difference(letras)
    if forma.geom_type != "Polygon":
        forma = max(forma.geoms, key=lambda g: g.area)
    return extruir(forma, ESPESOR)


def extruir(forma: Polygon, alto: float) -> trimesh.Trimesh:
    """Extrusión cerrada garantizada (manifold3d). La de trimesh deja, con
    algunas letras, una arista repetida y la chapa no queda estanca."""
    import manifold3d as m3

    anillos = [np.asarray(r.coords)[:-1] for r in (forma.exterior, *forma.interiors)]
    malla = m3.Manifold.extrude(m3.CrossSection(anillos, m3.FillRule.EvenOdd), alto).to_mesh()
    return trimesh.Trimesh(malla.vert_properties[:, :3], malla.tri_verts)


def _paladar(contorno: Polygon, interno: float) -> Polygon:
    """Si la U está abierta (sin hueco cerrado), el paladar es lo que queda entre las ramas."""
    x0, y0, x1, _ = contorno.bounds
    caja = box(x0, y0 - 1, x1, interno)
    return caja.difference(contorno)


def marca(contorno: Polygon) -> trimesh.Trimesh:
    ys = _cruces_x0(contorno)
    frente = ys[-1]
    ancho, largo, alto = MARCA
    m = trimesh.creation.box([ancho, largo, alto])
    m.apply_translation([0, frente + MARCA_ASOMA - largo / 2, alto / 2])
    return m


def partes_de_nombre(ruta: str | Path) -> tuple[str, str]:
    """ID del caso (primera palabra) y movimiento (última): 'AP962 ... Inf 05' -> ('AP962', '05')."""
    palabras = Path(ruta).stem.split()
    return palabras[0], palabras[-1]


def generar(
    alineado: trimesh.Trimesh, id_caso: str, movimiento: str, ranuras: bool = True
) -> trimesh.Trimesh:
    """Arma el STL CNC2 a partir del modelo ya alineado (base en z=0, incisivos a +Y)."""
    from .base import pieza_principal

    contorno = arco.contorno_base(pieza_principal(alineado), 0.5)
    piezas = [alineado, chapa(contorno, id_caso, movimiento), marca(contorno)]
    if ranuras:
        piezas.append(_ranuras())  # ya vienen invertidas (volumen negativo)
    return trimesh.util.concatenate(piezas)


def volumenes(m: trimesh.Trimesh) -> list[float]:
    return sorted((float(p.volume) for p in m.split(only_watertight=False)), key=lambda v: -abs(v))
