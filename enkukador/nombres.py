"""Tipo de modelo a partir del nombre de archivo, con las reglas del GH.

Los archivos vienen como ``<caso> <paciente> <versión> <inf|sup> <etapa>.stl``,
por ejemplo ``0044 Apellido Nombre 1.0 sup 01.stl``. El GH partía el nombre por
espacios y, con el interruptor «Botones» prendido, si la última palabra era
``0``, ``00`` u ``00b`` el modelo iba como botones/pasivos (solo base, sin
orientar el arco). Con el interruptor apagado, o si no, ``inf`` o ``sup``.
En las salidas reales del GH (caso BN595) el ``Sup 00`` se orientó como
arcada, así que acá también viene apagado por defecto.

También se aceptan los nombres de ToothFORM, ``<ID>-<L|U><etapa>-<letra>``
(``BZ254-U05-A.stl``): L es inferior y U superior; la etapa 00 cuenta como
botones si el interruptor está prendido.
"""

from __future__ import annotations

import re
from pathlib import Path

ETAPAS_BOTONES = {"0", "00", "00b"}
TOOTHFORM = re.compile(r"^[^-\s]+-([LU])(\d+)-", re.IGNORECASE)


def tipo_por_nombre(ruta: str | Path, botones: bool = False) -> str | None:
    palabras = Path(ruta).stem.lower().split()
    if not palabras:
        return None
    if botones and palabras[-1] in ETAPAS_BOTONES:
        return "bot"
    if "inf" in palabras:
        return "inf"
    if "sup" in palabras:
        return "sup"
    tf = TOOTHFORM.match(Path(ruta).stem)
    if tf:
        if botones and int(tf.group(2)) == 0:
            return "bot"
        return "inf" if tf.group(1).upper() == "L" else "sup"
    return None
