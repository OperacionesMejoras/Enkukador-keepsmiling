"""Vaciado (cascarón) sin booleanas: cavidad invertida concatenada al modelo.

Como «Modelos huecos» del GH: no se resta nada. Se calcula la cavidad (el
interior que queda a más de `espesor` mm de la superficie), se invierten sus
normales y se agrega al mismo STL. El slicer suma los dos cuerpos con su
orientación y la cavidad queda vacía.

La cavidad sale de un campo de distancia (método de KeepModelReferencer/
ahuecar.py, ya medido ahí): voxelizado por rebanadas, transformada de distancia
euclídea y marching cubes. La base se replica hacia abajo antes de medir, así
la cavidad llega hasta z=0 y el modelo queda abierto por abajo (drenaje). Por
último se recorta en z=0: si quedara algo por debajo, el slicer apoyaría eso en
la cama y el modelo flotaría.
"""

from __future__ import annotations

import numpy as np
import trimesh

COMPENSACION = 1.5  # sesgo de la grilla, K * paso² (medido en KeepModelReferencer)


def _voxelizar(malla: trimesh.Trimesh, paso: float):
    """Volumen binario rebanando en Z y rasterizando cada corte en 2D."""
    from PIL import Image, ImageDraw

    x0, y0, z0 = malla.bounds[0]
    nx = int(np.ceil((malla.bounds[1][0] - x0) / paso)) + 2
    ny = int(np.ceil((malla.bounds[1][1] - y0) / paso)) + 2
    # Arranca en z0+paso para que z=0 caiga justo sobre un plano de vóxeles.
    alturas = np.arange(z0 + paso, malla.bounds[1][2], paso)
    cortes = malla.section_multiplane(
        plane_origin=[0, 0, 0], plane_normal=[0, 0, 1], heights=alturas
    )

    vol = np.zeros((nx, ny, len(alturas)), dtype=bool)
    for k, corte in enumerate(cortes):
        if corte is None:
            continue
        polis = [p for p in corte.polygons_full if p is not None]
        if not polis:
            continue
        img = Image.new("1", (nx, ny), 0)
        dib = ImageDraw.Draw(img)
        for poli in polis:
            dib.polygon(
                [((x - x0) / paso, (y - y0) / paso) for x, y in poli.exterior.coords], fill=1
            )
            for anillo in poli.interiors:
                dib.polygon([((x - x0) / paso, (y - y0) / paso) for x, y in anillo.coords], fill=0)
        vol[:, :, k] = np.array(img).T
    return vol, np.array([x0, y0, z0 + paso])


def cavidad(malla: trimesh.Trimesh, espesor: float = 2.0, paso: float = 0.2) -> trimesh.Trimesh:
    """Interior a más de `espesor` mm de la superficie, cerrado y con normales hacia afuera."""
    from scipy import ndimage
    from skimage import measure

    umbral = espesor + COMPENSACION * paso**2
    vol, origen = _voxelizar(malla, paso)

    # Replicar la base hacia abajo: así la base no cuenta como superficie y la
    # cavidad llega hasta z=0 (abierta por abajo).
    relleno = int(np.ceil(umbral / paso)) + 4
    vol = np.concatenate([np.repeat(vol[:, :, :1], relleno, axis=2), vol], axis=2)
    origen = origen - np.array([0.0, 0.0, relleno * paso])

    dentro = ndimage.distance_transform_edt(vol, sampling=(paso,) * 3) > umbral
    if not dentro.any():
        raise ValueError(f"con {espesor} mm de pared no queda cavidad: el modelo es más fino")
    dentro = np.pad(dentro, 1, constant_values=False)  # que marching cubes la cierre
    origen = origen - paso

    verts, caras, _, _ = measure.marching_cubes(dentro.astype(np.float32), 0.5, spacing=(paso,) * 3)
    hueco = trimesh.Trimesh(verts + origen, caras, process=True)
    if hueco.volume < 0:
        hueco.invert()
    if hueco.body_count > 1:
        hueco = max(hueco.split(only_watertight=False), key=lambda p: abs(p.volume))

    # Recortar en z=0 y tapar: nada por debajo de la base.
    hueco = trimesh.intersections.slice_mesh_plane(hueco, [0, 0, 1], [0, 0, 0], cap=True)
    if hueco.volume < 0:
        hueco.invert()
    return hueco


def vaciar(malla: trimesh.Trimesh, espesor: float = 2.0, paso: float = 0.2) -> trimesh.Trimesh:
    """Modelo + su cavidad invertida, concatenados (sin booleanas)."""
    from .base import pieza_principal

    solido = pieza_principal(malla)
    if not solido.is_watertight:
        solido = solido.copy()
        solido.merge_vertices()
        solido.fill_holes()
    hueco = cavidad(solido, espesor, paso)
    hueco.invert()  # Mesh Flip: volumen negativo = vacío para el slicer
    return trimesh.util.concatenate([malla, hueco])
