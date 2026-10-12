"""Convierte un .gh de Grasshopper (binario) a XML, sin Rhino.

    python tools/gh_a_xml.py "Modelos planos V5.06.02 PRUEBA.gh" salida.xml

Un .gh es un archivo GH_IO serializado en binario y comprimido con deflate
crudo. La estructura es la misma que la de un .ghx: chunks con nombre e índice
que contienen items tipados y otros chunks. Los clusters guardan su definición
como un .gh completo dentro de un item ``ClusterDocument``; se expanden en el
lugar, así que el XML de salida incluye el contenido de todos los clusters.

Formato de cada chunk: nombre (string .NET), índice (int32, -1 = sin índice),
cantidad de items, cantidad de sub-chunks; después los items (nombre, índice,
código de tipo, valor) y los sub-chunks.
"""

from __future__ import annotations

import struct
import sys
import uuid
import zlib
from xml.sax.saxutils import escape

# Códigos de GH_Types -> (tamaño fijo en bytes o None, formateador)
_DOBLES = {50: 2, 51: 3, 52: 4, 60: 2, 61: 4, 70: 6, 71: 6, 72: 9}


class _Lector:
    def __init__(self, datos: bytes):
        self.b, self.p = datos, 0

    def bytes(self, n: int) -> bytes:
        v = self.b[self.p : self.p + n]
        self.p += n
        return v

    def i32(self) -> int:
        return struct.unpack("<i", self.bytes(4))[0]

    def texto(self) -> str:
        n = desplazamiento = 0
        while True:
            c = self.bytes(1)[0]
            n |= (c & 0x7F) << desplazamiento
            desplazamiento += 7
            if not c & 0x80:
                break
        return self.bytes(n).decode("utf-8", "replace")


def _documento(datos: bytes) -> bytes | None:
    """Descomprime si hace falta y devuelve el archivo GH_IO, o None."""
    try:
        datos = zlib.decompress(datos, -15)
    except zlib.error:
        pass
    if datos[:5] == b"\x04Root" or datos[:9] == b"\x08Document":
        return datos
    return None


def _valor(r: _Lector, tipo: int):
    if tipo == 1:
        return str(bool(r.bytes(1)[0]))
    if tipo == 2:
        return str(r.bytes(1)[0])
    if tipo == 3:
        return str(r.i32())
    if tipo in (4, 8):  # int64, fecha (ticks de .NET)
        return str(struct.unpack("<q", r.bytes(8))[0])
    if tipo == 5:
        return repr(struct.unpack("<f", r.bytes(4))[0])
    if tipo == 6:
        return repr(struct.unpack("<d", r.bytes(8))[0])
    if tipo == 7:
        return r.bytes(16).hex()
    if tipo == 9:
        return str(uuid.UUID(bytes_le=r.bytes(16)))
    if tipo == 10:
        return r.texto()
    if tipo in (20, 37):  # byte array, bitmap
        n = r.i32()
        datos = r.bytes(n)
        if tipo == 20 and (doc := _documento(datos)) is not None:
            hijos: list[str] = []
            _chunk(_Lector(doc), hijos, 0)
            return hijos
        return f"<{n} bytes>"
    if tipo == 21:
        n = r.i32()
        return " ".join(repr(x) for x in struct.unpack(f"<{n}d", r.bytes(8 * n)))
    if tipo in (30, 31, 32, 33):
        return r.bytes(8).hex()
    if tipo in (34, 35):
        return r.bytes(16).hex()
    if tipo == 36:  # color ARGB
        return r.bytes(4).hex()
    if tipo in _DOBLES:
        k = _DOBLES[tipo]
        return " ".join(repr(x) for x in struct.unpack(f"<{k}d", r.bytes(8 * k)))
    if tipo == 80:
        return ".".join(str(x) for x in struct.unpack("<3i", r.bytes(12)))
    raise ValueError(f"tipo GH_IO {tipo} desconocido en el byte {r.p}")


def _chunk(r: _Lector, out: list[str], nivel: int) -> None:
    nombre, indice = r.texto(), r.i32()
    n_items, n_chunks = r.i32(), r.i32()
    sangria = "  " * nivel
    attr = f' index="{indice}"' if indice >= 0 else ""
    out.append(f'{sangria}<chunk name="{escape(nombre)}"{attr}>')
    for _ in range(n_items):
        inombre, iindice, tipo = r.texto(), r.i32(), r.i32()
        valor = _valor(r, tipo)
        a = f' index="{iindice}"' if iindice >= 0 else ""
        cab = f'{sangria}  <item name="{escape(inombre)}"{a} type="{tipo}">'
        if isinstance(valor, list):  # cluster expandido
            out.append(cab)
            out.extend(f"{sangria}    {linea}" for linea in valor)
            out.append(f"{sangria}  </item>")
        else:
            out.append(f"{cab}{escape(valor)}</item>")
    for _ in range(n_chunks):
        _chunk(r, out, nivel + 1)
    out.append(f"{sangria}</chunk>")


def gh_a_xml(ruta: str) -> str:
    with open(ruta, "rb") as f:
        doc = _documento(f.read())
    if doc is None:
        raise ValueError(f"{ruta}: no parece un .gh")
    out: list[str] = ['<?xml version="1.0" encoding="utf-8"?>']
    _chunk(_Lector(doc), out, 0)
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(gh_a_xml(sys.argv[1]))
