"""Devuelve una salida a la posición original del escáner usando su .aligned.

    python -m enkukador.desalinear "MODELOS KUKA/Caso Inf 05 CNC2.stl" [--solo-modelo] [--salida carpeta]

Con --solo-modelo se queda únicamente con la arcada (sin chapa, ranuras ni
cavidad), que es exactamente el archivo original.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .exportar import desalinear


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("archivos", nargs="+", type=Path)
    p.add_argument(
        "--solo-modelo", action="store_true", help="solo la arcada: recupera el original"
    )
    p.add_argument("--salida", type=Path, help="carpeta (por defecto 'desalineados/' al lado)")
    a = p.parse_args(argv)
    for f in a.archivos:
        m = desalinear(f, solo_modelo=a.solo_modelo)
        carpeta = a.salida or f.parent / "desalineados"
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"{f.stem} original.stl"
        m.export(destino)
        print(f"{f.name} -> {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
