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

    # Un vóxel vacío de margen en X e Y: si el modelo toca el borde de la
    # grilla, la EDT no ve el afuera de ese lado y la cavidad sale por ahí.
    x0, y0, z0 = malla.bounds[0] - np.array([paso, paso, 0.0])
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


def _distancia_exacta(malla: trimesh.Trimesh, puntos: np.ndarray, vecinos: int = 16) -> np.ndarray:
    """Distancia de cada punto a la superficie, sin contar la base plana (z=0, normal -Z).

    Candidatos por KD-tree de centroides y distancia exacta punto-triángulo. La
    base no cuenta: el modelo se trata como extruido hacia abajo, así la
    cavidad llega hasta z=0.
    """
    from scipy.spatial import cKDTree

    base = (malla.face_normals[:, 2] < -0.99) & (malla.triangles_center[:, 2] < 0.05)
    tris = malla.triangles[~base]
    arbol = cKDTree(tris.mean(axis=1))
    p = puntos.copy()
    p[:, 2] = np.maximum(p[:, 2], 0.0)  # lo replicado por debajo mide como en z=0
    k = min(vecinos, len(tris))
    dist = np.empty(len(p))
    for i in range(0, len(p), 40000):
        q = p[i : i + 40000]
        _, idx = arbol.query(q, k=k)
        cand = tris[idx.ravel()]
        qq = np.repeat(q, k, axis=0)
        d = np.linalg.norm(trimesh.triangles.closest_point(cand, qq) - qq, axis=1)
        dist[i : i + 40000] = d.reshape(-1, k).min(axis=1)
    return dist


def cavidad(
    malla: trimesh.Trimesh, espesor: float = 2.0, paso: float = 0.2, liso: bool = True
) -> trimesh.Trimesh:
    """Interior a más de `espesor` mm de la superficie, cerrado y con normales hacia afuera.

    liso=True: el campo de distancia es exacto cerca de la pared (banda de
    ±2 pasos) y marching cubes interpola el cruce, más un suavizado de Taubin.
    Sale sin escalones de vóxel. liso=False: el método anterior (umbral binario
    sobre la EDT), con escalones de `paso`.
    """
    from scipy import ndimage
    from skimage import measure

    umbral = espesor if liso else espesor + COMPENSACION * paso**2
    vol, origen = _voxelizar(malla, paso)

    # Replicar la base hacia abajo: así la base no cuenta como superficie y la
    # cavidad llega hasta z=0 (abierta por abajo).
    relleno = int(np.ceil(umbral / paso)) + 4
    vol = np.concatenate([np.repeat(vol[:, :, :1], relleno, axis=2), vol], axis=2)
    origen = origen - np.array([0.0, 0.0, relleno * paso])

    edt = ndimage.distance_transform_edt(vol, sampling=(paso,) * 3)
    if not (edt > umbral).any():
        raise ValueError(f"con {espesor} mm de pared no queda cavidad: el modelo es más fino")

    if liso:
        # La EDT de un volumen binario mide a centros de vóxel: sirve de guía, no
        # de superficie. Cerca del nivel se reemplaza por la distancia real.
        campo = edt.astype(np.float32)
        banda = vol & (np.abs(edt - umbral) < 2.0 * paso)
        ijk = np.argwhere(banda)
        campo[banda] = _distancia_exacta(malla, ijk * paso + origen)
        nivel = umbral
    else:
        campo = (edt > umbral).astype(np.float32)
        nivel = 0.5
    campo = np.pad(campo, 1, constant_values=0.0)  # que marching cubes la cierre
    origen = origen - paso

    verts, caras, _, _ = measure.marching_cubes(campo, nivel, spacing=(paso,) * 3)
    hueco = trimesh.Trimesh(verts + origen, caras, process=True)
    if hueco.volume < 0:
        hueco.invert()
    if hueco.body_count > 1:
        hueco = max(hueco.split(only_watertight=False), key=lambda p: abs(p.volume))

    # Recortar en z=0 y tapar: nada por debajo de la base.
    hueco = trimesh.intersections.slice_mesh_plane(hueco, [0, 0, 1], [0, 0, 0], cap=True)
    if hueco.volume < 0:
        hueco.invert()
    if liso:
        _taubin_con_tapa_fija(hueco)
    return hueco


def _taubin_con_tapa_fija(malla: trimesh.Trimesh, iteraciones: int = 10) -> None:
    """Taubin (no encoge) sin mover la tapa de z=0: si se suaviza antes del
    corte quedan pliegues y la tapa no cierra."""
    fijos = np.abs(malla.vertices[:, 2]) < 1e-6
    lap = trimesh.smoothing.laplacian_calculation(malla, equal_weight=True)
    v = malla.vertices.copy()
    for i in range(2 * iteraciones):
        paso = 0.5 if i % 2 == 0 else -0.53
        nuevo = v + paso * (lap.dot(v) - v)
        v[~fijos] = nuevo[~fijos]
    malla.vertices = v


def vaciar(
    malla: trimesh.Trimesh, espesor: float = 2.0, paso: float = 0.2, liso: bool = True
) -> trimesh.Trimesh:
    """Modelo + su cavidad invertida, concatenados (sin booleanas)."""
    from .base import pieza_principal

    solido = pieza_principal(malla)
    if not solido.is_watertight:
        solido = solido.copy()
        solido.merge_vertices()
        solido.fill_holes()
    hueco = cavidad(solido, espesor, paso, liso)
    hueco.invert()  # Mesh Flip: volumen negativo = vacío para el slicer
    return trimesh.util.concatenate([malla, hueco])
