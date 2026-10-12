"""Paso 3: ajuste fino del arco con la plantilla de 4 puntos (lo que hacía Kangaroo).

En el GH, después del orientador, un cluster ponía cuatro puntos fijos:

    adelante (±14; 17,5)    atrás (±22; -0,5)

los ataba como cuerpo rígido (RigidBody) y los dejaba deslizar hasta apoyarse
sobre la curva central del modelo (OnCurve). Un objetivo Direction mantenía la
línea entre los dos puntos de adelante paralela a X, con el mismo peso que
OnCurve, así que el giro que se corrige queda amortiguado. Después se aplicaba
al modelo la transformación inversa (Orient de plano resuelto a plano inicial):
el modelo se mueve para que su curva central caiga sobre la plantilla.

Kangaroo llega al equilibrio de esos objetivos, que con pesos 1 es el mínimo de

    E(θ, t) = Σ d(Pᵢ, curva)² + L²·sin²θ / 2

con L = 28 mm (la línea de adelante): el término Direction mueve cada extremo
la mitad de la componente perpendicular de la línea. Acá se minimiza eso
directamente.

La distancia a la curva central se mide por su definición y no contra la
polilínea: un punto está sobre el eje medial cuando equidista de las dos
orillas de la U, así que d(P, curva) ≈ (d(P, labial) − d(P, lingual)) / 2.
Medir contra la polilínea hacía depender el resultado de cómo terminaban sus
puntas (en cada extremo se abren en horquilla hacia las esquinas del corte):
varios mm de diferencia según la orientación de partida. La equidistancia vale
dentro del material; afuera (sobre el paladar, entre los dos brazos) también
hay puntos equidistantes que serían mínimos falsos, así que ahí se usa la
distancia a la polilínea.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from shapely import contains_xy
from shapely.geometry import Polygon

ADELANTE = np.array([[14.0, 17.5], [-14.0, 17.5]])
ATRAS = np.array([[22.0, -0.5], [-22.0, -0.5]])
PLANTILLA = np.vstack([ADELANTE, ATRAS])


@dataclass
class Ajuste:
    giro: float  # grados que gira el modelo (antihorario)
    traslacion: np.ndarray  # mm en XY
    distancias: np.ndarray  # de cada punto de la plantilla a la curva, ya ajustada
    matriz: np.ndarray  # 4x4 a aplicar al modelo


def _densificar(curva: np.ndarray, paso: float = 0.05) -> np.ndarray:
    out = [curva[:1]]
    for a, b in pairwise(curva):
        n = max(1, int(np.ceil(np.linalg.norm(b - a) / paso)))
        t = np.linspace(0, 1, n + 1)[1:, None]
        out.append(a + t * (b - a))
    return np.vstack(out)


def _rot(t: float) -> np.ndarray:
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, -s], [s, c]])


def ajustar(
    curva: np.ndarray,
    orillas: tuple[np.ndarray, np.ndarray],
    peso_direccion: float = 1.0,
    girar: bool = True,
    puntos: np.ndarray = PLANTILLA,
) -> Ajuste:
    """Movimiento rígido en XY que apoya la curva central sobre la plantilla.

    `orillas` son las dos mitades del contorno de la U (ver `arco.bordes`).
    `peso_direccion` = 1 reproduce el GH. Con `girar=False` solo se traslada
    (el giro ya lo resolvió otro método).
    """
    a, b = (np.asarray(o, float) for o in orillas)
    arbol_a, arbol_b = cKDTree(_densificar(a)), cKDTree(_densificar(b))
    arbol_c = cKDTree(_densificar(np.asarray(curva, float)))
    material = Polygon(np.vstack([a, b[1:]]))
    puntos = np.asarray(puntos, float)
    largo = float(np.linalg.norm(puntos[1] - puntos[0]))

    # Se mueve la plantilla (como en Kangaroo) y al modelo se le aplica la inversa.
    def residuos(x):
        t, tx, ty = x if girar else (0.0, *x)
        P = puntos @ _rot(t).T + [tx, ty]
        d = np.where(
            contains_xy(material, P[:, 0], P[:, 1]),
            (arbol_a.query(P)[0] - arbol_b.query(P)[0]) / 2.0,
            arbol_c.query(P)[0],
        )
        return np.append(d, np.sqrt(peso_direccion / 2.0) * largo * np.sin(t))

    # Tras el giro por cuadrantes puede quedar hasta ±45°, y desde θ=0 el ajuste
    # local cae en mínimos falsos a partir de ~30°. Kangaroo tampoco garantizaba
    # nada ahí; se arranca desde varios ángulos y se queda el de menor energía.
    if girar:
        sols = [
            least_squares(residuos, x0=[np.radians(a), 0.0, 0.0], x_scale=[0.1, 1.0, 1.0])
            for a in range(-40, 41, 10)
        ]
        sol = min(sols, key=lambda s: s.cost)
        t, tx, ty = sol.x
    else:
        sol = least_squares(residuos, x0=[0.0, 0.0])
        t, (tx, ty) = 0.0, sol.x

    # Plantilla: p -> R p + τ. Modelo: q -> Rᵀ (q - τ).
    R = _rot(t)
    m = np.eye(4)
    m[:2, :2] = R.T
    m[:2, 3] = -R.T @ [tx, ty]
    return Ajuste(
        giro=float(np.degrees(-t)),
        traslacion=m[:2, 3].copy(),
        distancias=np.abs(residuos(sol.x)[:4]),
        matriz=m,
    )
