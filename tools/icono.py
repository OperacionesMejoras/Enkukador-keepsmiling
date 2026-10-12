"""Dibuja el ícono del Enkukador: una arcada vista desde arriba, con la chapa
entre las ramas y la base plana abajo.

    python tools/icono.py

Deja enkukador/ui/estatico/icono.ico (varios tamaños: instalador, accesos
directos, bandeja y pestaña) e icono.png (256 px). Necesita Pillow; el resultado
se commitea, así el instalador no lo dibuja.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).resolve().parents[1] / "enkukador" / "ui" / "estatico"
L = 1024  # se dibuja grande y se achica: bordes suaves
FONDO, DIENTE, SOMBRA, CHAPA, BASE = "#2b2d31", "#f2efe9", "#cfc9bf", "#e0a33a", "#3b82c4"


def arco(radio: float, centro=(512, 560), desde=200, hasta=-20, n=200) -> list[tuple[float, float]]:
    """Puntos de una U abierta hacia abajo (grados, 90 = arriba)."""
    cx, cy = centro
    pts = []
    for i in range(n + 1):
        a = math.radians(desde + (hasta - desde) * i / n)
        pts.append((cx + radio * math.cos(a), cy - radio * 1.05 * math.sin(a)))
    return pts


def dibujar() -> Image.Image:
    im = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((24, 24, L - 24, L - 24), radius=200, fill=FONDO)

    # base plana
    d.rounded_rectangle((150, 820, L - 150, 870), radius=25, fill=BASE)

    # arcada: banda entre dos U concéntricas, con dientes como lóbulos
    exterior, interior = arco(330), arco(190)
    banda = exterior + interior[::-1]
    d.polygon([(x + 12, y + 16) for x, y in banda], fill="#1c1d20")  # sombra
    d.polygon(banda, fill=DIENTE)
    for i in range(14):
        a = math.radians(200 - 220 * (i + 0.5) / 14)
        r = 300
        x, y = 512 + r * math.cos(a), 560 - r * 1.05 * math.sin(a)
        d.ellipse((x - 42, y - 42, x + 42, y + 42), fill=DIENTE, outline=SOMBRA, width=10)

    # chapa entre las ramas, con dos rayitas de "texto"
    d.rounded_rectangle((372, 520, 652, 640), radius=24, fill=CHAPA)
    d.rounded_rectangle((452, 450, 572, 530), radius=20, fill=CHAPA)
    for y in (560, 600):
        d.rounded_rectangle((410, y, 614, y + 16), radius=8, fill=FONDO)
    return im


def main() -> None:
    im = dibujar()
    im.resize((256, 256), Image.LANCZOS).save(DESTINO / "icono.png")
    im.save(
        DESTINO / "icono.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"{DESTINO / 'icono.ico'} y icono.png")


if __name__ == "__main__":
    main()
