"""Exportación como en el GH: mallas concatenadas en un solo STL, sin booleanas.

El GH no restaba ni sumaba sólidos. Juntaba las mallas con Mesh Join y exportaba
un único STL binario. Lo que tenía que ser un vacío (ranura, cavidad del ID) se
agregaba con las normales invertidas (Mesh Flip): queda una cáscara cerrada de
volumen negativo dentro del modelo, y el slicer la interpreta como hueco. Lo que
suma (el relieve del ID) va con sus normales normales.
"""

from __future__ import annotations

from pathlib import Path

import trimesh


def concatenar(modelo: trimesh.Trimesh, agregados=(), cavidades=()) -> trimesh.Trimesh:
    """Mesh Join de `modelo` + `agregados` + `cavidades` (estas invertidas)."""
    partes = [modelo, *agregados]
    for c in cavidades:
        inv = c.copy()
        inv.invert()  # Mesh Flip
        partes.append(inv)
    if len(partes) == 1:
        return modelo
    # concatenate no fusiona vértices: cada malla queda como cuerpo propio, igual que Mesh Join.
    return trimesh.util.concatenate(partes)


def exportar_stl(malla: trimesh.Trimesh, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    malla.export(destino, file_type="stl")  # binario
    return destino


# --- formato de salida del GH y archivo .aligned ---

CARPETA_GH = "MODELOS KUKA"
CARPETA_BACKUP = "Backup originales"
SUFIJOS = {"alineado": "", "cnc2": " CNC2", "cnc3": " CNC3"}


def destino_gh(
    original: Path, producto: str, salida: Path | None = None, sufijo: str | None = None
) -> Path:
    """Ruta de salida como la armaba el GH.

    `<caso> stl/MODELOS KUKA/<nombre original> CNC2.stl`. Si los originales
    están dentro de `Backup originales`, la carpeta del caso es la de arriba.
    Con `salida` se usa esa carpeta, con el mismo nombre de archivo.
    """
    original = Path(original)
    if salida is None:
        caso = original.parent
        if caso.name.lower() == CARPETA_BACKUP.lower():
            caso = caso.parent
        salida = caso / (CARPETA_GH if producto != "alineado" else "planos")
    sufijo = SUFIJOS.get(producto, "") if sufijo in (None, "") else sufijo
    return Path(salida) / f"{original.stem}{sufijo}.stl"


def guardar_aligned(destino: Path, original: Path, matriz, **datos) -> Path:
    """Escribe `<destino>.aligned`: JSON con la matriz para volver al original.

    En vez de guardar una copia de los originales (la carpeta «Backup
    originales» del GH), se guarda cómo se movieron: como no hay booleanas, el
    modelo dentro del STL de salida tiene los mismos vértices que el original,
    solo transformados, y aplicando la inversa vuelve exacto a su lugar.
    """
    import datetime
    import json

    import numpy as np

    m = np.asarray(matriz, dtype=float)
    contenido = {
        "formato": "enkukador/aligned",
        "version": 1,
        "original": str(Path(original).resolve()),
        "salida": Path(destino).name,
        "matriz": m.tolist(),  # original -> alineado (fila mayor, 4x4)
        "inversa": np.linalg.inv(m).tolist(),  # alineado -> original
        "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
        **datos,
    }
    ruta = Path(destino).with_suffix(".aligned")
    ruta.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def desalinear(
    stl: Path, aligned: Path | None = None, solo_modelo: bool = False
) -> trimesh.Trimesh:
    """Lleva una salida (alineada, CNC2...) de vuelta a la posición del escáner."""
    import json

    import numpy as np

    stl = Path(stl)
    datos = json.loads(Path(aligned or stl.with_suffix(".aligned")).read_text(encoding="utf-8"))
    malla = trimesh.load(stl, force="mesh")
    if solo_modelo:
        malla = max(malla.split(only_watertight=False), key=lambda p: abs(p.volume))
    malla.apply_transform(np.asarray(datos["inversa"]))
    return malla
