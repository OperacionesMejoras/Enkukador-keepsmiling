"""Orquestación: base plana -> cuadrante -> plantilla, para un modelo.

Tipos de modelo, como los separaba el GH:

- ``inf`` / ``sup``: se usa la pieza más grande para calcular (el resto viaja
  con ella), giro por cuadrante y ajuste con la plantilla.
- ``bot`` (botones / pasivos, etapas 0, 00 y 00b): se usa la malla entera, solo
  se apoya la base; sin giro ni plantilla.

Modos de giro para inf/sup (después del giro por cuadrantes):

- ``gh`` (por defecto): réplica del GH, la plantilla gira y traslada con el
  objetivo Direction de Kangaroo. Ese objetivo amortigua el giro (corrige más
  o menos un tercio de lo que está torcido): el GH confiaba en que el escáner
  entrega la arcada casi derecha, y es así (en BN595, 0,4° a 0,9°). Igual se
  calcula el eje de simetría y se avisa si la arcada quedó torcida.
- ``simetria``: el giro sale del eje de simetría de la curva central y la
  plantilla solo traslada. Corrige cualquier orientación de entrada; sirve
  para modelos que no vienen del escáner (rotados a mano, de otro software).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh

from . import arco, base, plantilla

TIPOS = ("inf", "sup", "bot")
MODOS = ("gh", "simetria")
AVISO_GIRO = 5.0  # grados respecto del eje de simetría, en modo gh


@dataclass
class Resultado:
    malla: trimesh.Trimesh
    matriz: np.ndarray  # 4x4 aplicada a la malla original
    tipo: str
    base: base.Base
    cuadrante: arco.Cuadrante | None = None
    simetria: tuple[float, float] | None = None  # (giro en grados, residuo en mm)
    ajuste: plantilla.Ajuste | None = None
    curva: np.ndarray | None = None  # curva central en el marco final
    avisos: list[str] = field(default_factory=list)


def alinear(
    malla: trimesh.Trimesh,
    tipo: str,
    *,
    modo: str = "gh",
    altura_corte: float = 0.5,
    con_plantilla: bool = True,
) -> Resultado:
    if tipo not in TIPOS:
        raise ValueError(f"tipo inválido: {tipo!r} (usar {', '.join(TIPOS)})")
    if modo not in MODOS:
        raise ValueError(f"modo inválido: {modo!r} (usar {', '.join(MODOS)})")

    calculo = malla if tipo == "bot" else base.pieza_principal(malla)
    b = base.detectar_base(calculo)
    M = b.plano.a_local()
    avisos = []
    if b.dominancia < 1.3:
        avisos.append(f"base poco dominante ({b.dominancia:.1f}x la siguiente cara plana)")

    res = Resultado(malla=malla, matriz=M, tipo=tipo, base=b, avisos=avisos)
    if tipo != "bot":
        local = calculo.copy()
        local.apply_transform(M)
        contorno = arco.contorno_base(local, altura_corte)
        curva = arco.curva_central(contorno)
        orillas = arco.bordes(contorno, curva)

        cuad = arco.cuadrante(curva)
        res.cuadrante = cuad
        G = arco.rotacion_z(cuad.giro)
        if modo == "simetria":
            local_curva = curva @ G[:2, :2].T
            giro, residuo = arco.giro_simetria(local_curva)
            res.simetria = (giro, residuo)
            G = arco.rotacion_z(giro) @ G
            if residuo > 1.5:
                avisos.append(f"curva central poco simétrica (residuo {residuo:.1f} mm)")
        M = G @ M
        curva = curva @ G[:2, :2].T
        orillas = [o @ G[:2, :2].T for o in orillas]

        if con_plantilla:
            aj = plantilla.ajustar(curva, orillas, girar=(modo == "gh"))
            M = aj.matriz @ M
            curva = curva @ aj.matriz[:2, :2].T + aj.matriz[:2, 3]
            res.ajuste = aj
            if aj.distancias.max() > 2.0:
                avisos.append(
                    f"la plantilla quedó lejos de la curva ({aj.distancias.max():.1f} mm)"
                )
        res.curva = curva

        if modo == "gh":
            giro, residuo = arco.giro_simetria(curva)
            res.simetria = (giro, residuo)
            if abs(giro) > AVISO_GIRO and residuo < 1.0:
                avisos.append(
                    f"la arcada quedó girada {giro:+.1f}° respecto de su eje de simetría "
                    "(¿no viene del escáner? probar --modo simetria)"
                )

    if not np.isclose(np.linalg.det(M[:3, :3]), 1.0):
        raise ValueError("la transformación espejaría el modelo")

    salida = malla.copy()
    salida.apply_transform(M)
    res.malla = salida
    res.matriz = M
    return res
