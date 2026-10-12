"""Separa un STL de salida del GH (CNC2, CNC3...) en sus piezas.

    python tools/separar_referencia.py "Paciente Inf 05 CNC3.stl" [más archivos] [--salida carpeta]

El GH no hacía booleanas: el modelo, la referencia, las ranuras y el ID van
concatenados como cuerpos separados en el mismo STL. Así que separarlos es
partir por piezas conectadas. Se guardan como:

    <nombre> modelo.stl       la pieza de mayor volumen (la arcada)
    <nombre> referencia.stl   la segunda (referencia / base del grip)
    <nombre> pieza N.stl      el resto, si hay (cavidades, letras del ID)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import trimesh


def separar(ruta: Path, salida: Path | None = None) -> list[Path]:
    malla = trimesh.load(ruta, force="mesh")
    piezas = sorted(malla.split(only_watertight=False), key=lambda p: -abs(p.volume))
    carpeta = salida or ruta.parent / "separados"
    carpeta.mkdir(parents=True, exist_ok=True)
    nombres = ["modelo", "referencia"] + [f"pieza {i}" for i in range(3, len(piezas) + 1)]
    destinos = []
    for pieza, nombre in zip(piezas, nombres):
        destino = carpeta / f"{ruta.stem} {nombre}.stl"
        pieza.export(destino)
        destinos.append(destino)
        print(f"  {nombre:<11} vol {pieza.volume:9.1f} mm³  {destino.name}")
    return destinos


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("archivos", nargs="+", type=Path)
    p.add_argument(
        "--salida", type=Path, help="carpeta de salida (por defecto 'separados/' al lado)"
    )
    a = p.parse_args()
    for f in a.archivos:
        print(f.name)
        separar(f, a.salida)
