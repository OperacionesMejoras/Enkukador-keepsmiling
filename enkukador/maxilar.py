"""Encuadre por maxilar: se alinea una etapa y la misma matriz va a las demás.

Los originales del escáner de un mismo maxilar vienen todos en la misma
ubicación (superpuestos). Entonces alcanza con alinear la primera etapa (00, o
la más baja que haya) y aplicar esa transformación al resto del maxilar: las
demás etapas quedan en el mismo marco, sin recalcular base ni curva.

Por si algún archivo no comparte la ubicación, después de moverlo se verifica
que su base haya quedado sobre z=0; si no, se avisa.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

from . import base, nombres

TOL_GRADOS = 0.5  # inclinación máxima de la base después de moverlo
TOL_MM = 0.3  # separación máxima de la base respecto de z=0


def clave(ruta: str | Path, tipo: str) -> tuple[str, str]:
    """Identifica el maxilar: misma carpeta y mismo tipo."""
    return (str(Path(ruta).parent), tipo)


def etapa(ruta: str | Path) -> str:
    """Última palabra del nombre ('00', '01', '00b'...), para ordenar."""
    palabras = Path(ruta).stem.split()
    return palabras[-1].lower() if palabras else ""


def referencia(rutas: list[Path], tipo: str, botones: bool = False) -> Path | None:
    """La primera etapa del maxilar `tipo` entre `rutas`."""
    del_tipo = [r for r in rutas if nombres.tipo_por_nombre(r, botones) == tipo]
    return min(del_tipo, key=lambda r: (etapa(r), r.name)) if del_tipo else None


def aplicar(malla: trimesh.Trimesh, matriz: np.ndarray) -> tuple[trimesh.Trimesh, list[str]]:
    """Mueve `malla` con la matriz del maxilar y verifica que la base caiga en z=0."""
    salida = malla.copy()
    salida.apply_transform(matriz)
    avisos = []
    b = base.detectar_base(base.pieza_principal(salida))
    inclinacion = float(np.degrees(np.arccos(np.clip(abs(b.plano.z[2]), -1, 1))))
    altura = float(b.plano.origen[2])
    if inclinacion > TOL_GRADOS or abs(altura) > TOL_MM:
        avisos.append(
            f"no comparte la ubicación de la etapa de referencia (base inclinada "
            f"{inclinacion:.2f}°, a {altura:+.2f} mm de z=0): alinearlo en modo único"
        )
    return salida, avisos
