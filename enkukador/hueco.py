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


def _sin_base(malla: trimesh.Trimesh) -> np.ndarray:
    """Triángulos de la superficie sin la base plana (z=0, normal -Z).

    La base no cuenta: el modelo se trata como extruido hacia abajo, así la
    cavidad llega hasta z=0.
    """
    base = (malla.face_normals[:, 2] < -0.99) & (malla.triangles_center[:, 2] < 0.05)
    return malla.triangles[~base]


def _a_la_base(puntos: np.ndarray) -> np.ndarray:
    p = puntos.copy()
    p[:, 2] = np.maximum(p[:, 2], 0.0)  # lo replicado por debajo mide como en z=0
    return p


def _distancia_aprox(
    malla: trimesh.Trimesh, puntos: np.ndarray, hasta: float, sep: float = 0.2
) -> np.ndarray:
    """Distancia a una muestra densa de la superficie (sobreestima < 0,02 mm a 1,8 mm).

    Guía para elegir dónde calcular la distancia exacta. No sirve la EDT del
    volumen binario: las ranuras finas (entre dientes, bajo las coronas) quedan
    llenas en la grilla y la EDT las ignora. Más lejos que `hasta` devuelve
    `hasta` (buscar lejos en el KD-tree es lo caro).
    """
    from scipy.spatial import cKDTree

    tris = _sin_base(malla)
    n = int(trimesh.triangles.area(tris).sum() / sep**2)
    sub = trimesh.Trimesh(tris.reshape(-1, 3), np.arange(len(tris) * 3).reshape(-1, 3), process=False)
    muestra = np.vstack([sub.sample(n, seed=0), tris.reshape(-1, 3)])
    d = cKDTree(muestra).query(_a_la_base(puntos), workers=-1, distance_upper_bound=hasta)[0]
    return np.minimum(d, hasta)


def _distancia_exacta(malla: trimesh.Trimesh, puntos: np.ndarray, vecinos: int = 16) -> np.ndarray:
    """Distancia de cada punto a la superficie sin la base: candidatos por
    KD-tree de centroides y distancia exacta punto-triángulo."""
    from scipy.spatial import cKDTree

    tris = _sin_base(malla)
    arbol = cKDTree(tris.mean(axis=1))
    p = _a_la_base(puntos)
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

    liso=True: el campo de distancia es exacto cerca de la pared (los cubos
    que cruzan el nivel) y marching cubes interpola el cruce, más un suavizado de Taubin.
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

    if liso:
        # Adentro: distancia a una muestra densa de la superficie y, cerca del
        # nivel, la distancia exacta. Afuera queda en 0.
        # Primero en una grilla del doble de paso: como la distancia cambia a lo
        # sumo lo que uno se mueve, los vóxeles a más de √3·paso por encima de
        # la banda no hace falta medirlos (más de la mitad del volumen).
        hasta = umbral + 4 * paso
        grueso = vol[::2, ::2, ::2]
        dg = np.zeros(grueso.shape, np.float32)  # afuera = 0: lo de al lado se mide
        ijk = np.argwhere(grueso)
        dg[tuple(ijk.T)] = _distancia_aprox(malla, 2 * ijk * paso + origen, hasta)
        idx = [np.minimum((np.arange(n) + 1) // 2, m - 1) for n, m in zip(vol.shape, dg.shape)]
        campo = dg[np.ix_(*idx)]
        campo[~vol] = 0.0
        medir = vol & (campo < umbral + 2 * np.sqrt(3) * paso)
        ijk = np.argwhere(medir)
        aprox = _distancia_aprox(malla, ijk * paso + origen, hasta)
        cerca = np.abs(aprox - umbral) < np.sqrt(3) * paso  # cubos que cruzan el nivel
        aprox[cerca] = _distancia_exacta(malla, ijk[cerca] * paso + origen)
        campo[tuple(ijk.T)] = aprox
        nivel = umbral
    else:
        campo = (ndimage.distance_transform_edt(vol, sampling=(paso,) * 3) > umbral).astype(
            np.float32
        )
        nivel = 0.5
    if not (campo > nivel).any():
        raise ValueError(f"con {espesor} mm de pared no queda cavidad: el modelo es más fino")
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
    # El corte deja vértices casi coincidentes en el borde de la tapa: el STL
    # (float32) los junta y quedan triángulos sin área que al releer aparecen
    # como cientos de piezas sueltas. Se redondea a float32 y se limpia acá.
    hueco.vertices = hueco.vertices.astype(np.float32).astype(np.float64)
    hueco.merge_vertices(digits_vertex=5)
    hueco.update_faces(hueco.nondegenerate_faces(height=1e-7))
    hueco.remove_unreferenced_vertices()
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


def unir(malla: trimesh.Trimesh) -> trimesh.Trimesh:
    """Une las piezas sueltas (encía, dientes, attachments) en un solo sólido.

    Hace falta antes de vaciar: si la cavidad se concatena a las piezas sueltas,
    las raíces de los dientes quedan macizas dentro del hueco (el slicer suma
    encía +1, diente +1 y cavidad -1). Unión de manifold3d: cada pieza tiene que
    ser cerrada; si alguna no lo es, se intenta repararla y si no, error.
    """
    import manifold3d as mf

    piezas = malla.split(only_watertight=False)
    if len(piezas) <= 1:
        return malla
    solidos = []
    for p in piezas:
        if not p.is_watertight:
            p = p.copy()
            p.merge_vertices()
            p.fill_holes()
        if p.volume < 0:
            p.invert()
        m = mf.Manifold(
            mf.Mesh(np.asarray(p.vertices, np.float32), np.asarray(p.faces, np.uint32))
        )
        if m.status() != mf.Error.NoError:
            raise ValueError(f"una pieza no es cerrada ({m.status()}): no se puede unir para vaciar")
        solidos.append(m)
    salida = mf.Manifold.batch_boolean(solidos, mf.OpType.Add).to_mesh()
    unida = trimesh.Trimesh(salida.vert_properties[:, :3], salida.tri_verts, process=True)
    if not unida.is_watertight:
        raise ValueError("la unión de las piezas no quedó cerrada: no se puede vaciar")
    return unida


def vaciar(
    malla: trimesh.Trimesh, espesor: float = 2.0, paso: float = 0.2, liso: bool = True
) -> trimesh.Trimesh:
    """Piezas unidas + su cavidad invertida, concatenadas (sin restar la cavidad).

    Se vacía la unión de todas las piezas, no solo la encía: así el hueco pasa
    también por las raíces de los dientes. La salida lleva la unión en lugar de
    las piezas originales.
    """
    solido = unir(malla)
    hueco = cavidad(solido, espesor, paso, liso)
    hueco.invert()  # Mesh Flip: volumen negativo = vacío para el slicer
    return trimesh.util.concatenate([solido, hueco])
