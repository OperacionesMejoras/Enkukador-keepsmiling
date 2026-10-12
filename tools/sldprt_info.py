"""Lee lo que se puede de un .SLDPRT (SolidWorks 2015+) sin SolidWorks.

    python tools/sldprt_info.py "referencia nueva.SLDPRT"

El formato nuevo guarda secciones con la firma 14 00 06 00 08 00 y los datos
comprimidos en deflate crudo. Descomprimiéndolas aparecen, en texto: las
configuraciones, las ecuaciones globales, el árbol de operaciones con sus cotas
(un XML interno) y las propiedades. La geometría (Parasolid) también está, pero
en binario: para la geometría usar las exportaciones STEP.

Las configuraciones y las ecuaciones salen tal cual. La asignación de cada cota
a su operación es aproximada (se lee de un XML interno a medias).
"""

from __future__ import annotations

import re
import sys
import zlib

FIRMA = b"\x14\x00\x06\x00\x08\x00"


def secciones(datos: bytes):
    for m in re.finditer(re.escape(FIRMA), datos):
        for desfase in range(18, 400):  # el encabezado tiene largo variable
            d = zlib.decompressobj(-15)
            try:
                salida = d.decompress(datos[m.start() + desfase : m.start() + desfase + 4_000_000])
            except zlib.error:
                continue
            if d.eof and len(salida) > 32:
                yield salida
                break


def textos(datos: bytes) -> list[str]:
    vistos, out = set(), []
    for s in secciones(datos):
        candidatos = [
            x.decode("utf-8", "replace") for x in re.findall(rb"[\x20-\x7e\x80-\xff]{5,}", s)
        ]
        candidatos += [x.decode("utf-16le") for x in re.findall(rb"(?:[\x20-\x7e]\x00){5,}", s)]
        for t in candidatos:
            if t not in vistos:
                vistos.add(t)
                out.append(t)
    return out


def main(ruta: str) -> None:
    with open(ruta, "rb") as f:
        tx = textos(f.read())
    todo = "\n".join(tx)

    configs = sorted(
        set(re.findall(r'<Configuration id="(\d+)" Name="([^"]+)"', todo)), key=lambda c: int(c[0])
    )
    print("CONFIGURACIONES:")
    for i, n in configs:
        print(f"  {i:>3}  {n}")

    print("\nECUACIONES:")
    for t in tx:
        if re.match(r'^"[^"]+"\s*=', t):
            print("  " + t)

    print("\nOPERACIONES (con cotas):")
    for m in re.finditer(
        r'<(Feature|Extrusion|Sketch|HoleWizard)[^>]*Name="([^"]*)"[^>]*Type="?([^"]*)"?[^>]*>(.*?)</\1>',
        todo,
        re.DOTALL,
    ):
        cotas = re.findall(r'<Dimension Name="([^"]+)">([^<]+)</Dimension>', m.group(4))
        if cotas:
            print(f"  {m.group(2)}: " + ", ".join(f"{n}={v.strip()}" for n, v in cotas))
    nombres = [
        t
        for t in tx
        if re.fullmatch(r"[\w\- <>áéíóúñÁÉÍÓÚ]+", t)
        and re.search(
            r"Croquis|Sketch|Extru|Saliente|Cortar|Cut|Redondeo|Fillet|Chafl|Revol|Matriz|Cono|pin|label",
            t,
        )
    ]
    print("\nÁRBOL (nombres):\n  " + ", ".join(dict.fromkeys(nombres)))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
