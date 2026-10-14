"""Línea de comandos.

    python -m enkukador "caso/Paciente 1.0 stl"            # carpeta entera
    python -m enkukador *.stl --salida planos --modo gh
    python -m enkukador modelo.stl --agregar id.stl --cavidad ranura.stl
    python -m enkukador carpeta --producto toothform --salida impresion [--config config.json]

Cada modelo se alinea y se guarda como STL binario. Con --agregar / --cavidad
se concatenan otras mallas (ya en el marco alineado) en el mismo STL, sin
booleanas: las cavidades van con las normales invertidas, como hacía el GH.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import trimesh

from . import cnc2, exportar, hueco, maxilar, nombres, toothform
from .alinear import MODOS, TIPOS, Resultado, alinear

EXTENSIONES = {".stl", ".obj", ".ply", ".off"}


def _entradas(rutas: list[Path]) -> list[Path]:
    archivos = []
    for r in rutas:
        if r.is_dir():
            archivos += sorted(p for p in r.iterdir() if p.suffix.lower() in EXTENSIONES)
        else:
            archivos.append(r)
    return archivos


def _cargar(ruta: Path) -> trimesh.Trimesh:
    malla = trimesh.load(ruta, force="mesh")
    if not isinstance(malla, trimesh.Trimesh) or len(malla.faces) == 0:
        raise ValueError("no es una malla o está vacía")
    return malla


def _resumen(r: Resultado) -> str:
    b = r.base
    partes = [
        f"base {b.area:.0f} mm² ({b.dominancia:.1f}x la siguiente, planitud {b.planitud:.3f} mm)"
    ]
    if r.cuadrante:
        partes.append(f"cuadrante {r.cuadrante.giro:.0f}°")
    if r.ajuste:
        partes.append(
            f"plantilla giro {r.ajuste.giro:+.2f}° tras ({r.ajuste.traslacion[0]:+.2f}, "
            f"{r.ajuste.traslacion[1]:+.2f}) dist máx {r.ajuste.distancias.max():.2f} mm"
        )
    if r.simetria:
        partes.append(f"eje de simetría {r.simetria[0]:+.2f}° (residuo {r.simetria[1]:.2f} mm)")
    return " | ".join(partes)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="enkukador",
        description="Apoya la base plana de cada modelo en z=0 y orienta el arco "
        "(incisivos hacia +Y), como Modelos planos V5.06.02.",
    )
    p.add_argument("entradas", nargs="+", type=Path, help="archivos o carpetas")
    p.add_argument(
        "--salida",
        type=Path,
        help="carpeta de salida (por defecto como el GH: '<caso> stl/MODELOS KUKA' para CNC2/CNC3, "
        "'planos' para solo alineado)",
    )
    p.add_argument("--sufijo", default="", help="texto a agregar al nombre (ej. ' planos')")
    p.add_argument(
        "--tipo", choices=["auto", *TIPOS], default="auto", help="auto = según el nombre (inf/sup)"
    )
    p.add_argument(
        "--botones",
        action="store_true",
        help="con --tipo auto, las etapas 0, 00 y 00b van como botones/pasivos (solo base)",
    )
    p.add_argument(
        "--modo",
        choices=MODOS,
        default="gh",
        help="gh: réplica del GH (por defecto); simetria: corrige cualquier giro de entrada",
    )
    p.add_argument(
        "--producto",
        choices=["alineado", "cnc2", "cnc3", "toothform"],
        default="alineado",
        help="alineado; cnc2: + chapa con ID y movimiento, ranuras y marca; cnc3: todavía no; "
        "toothform: pieza hueca con referencias del robot y QR, -gum.stl y -tooth.ply, en el "
        "marco y con los nombres de ToothFORM",
    )
    p.add_argument(
        "--config",
        type=Path,
        help="con --producto toothform: el config.json de ToothFORM (usa ParameterSettings)",
    )
    p.add_argument(
        "--vaciado",
        type=float,
        default=0.0,
        metavar="MM",
        help="vaciar el modelo dejando esa pared (ej. 2), abierto por la base; 0 = macizo",
    )
    p.add_argument(
        "--encuadre",
        choices=["maxilar", "unico"],
        default="maxilar",
        help="maxilar: alinea la primera etapa y aplica esa matriz al resto del maxilar "
        "(los originales vienen superpuestos); unico: cada modelo por separado",
    )
    p.add_argument(
        "--sin-plantilla", action="store_true", help="no centrar con la plantilla de 4 puntos"
    )
    p.add_argument(
        "--altura-corte", type=float, default=0.5, help="mm sobre la base para el contorno"
    )
    p.add_argument(
        "--agregar",
        type=Path,
        action="append",
        default=[],
        metavar="STL",
        help="malla a concatenar tal cual (repetible)",
    )
    p.add_argument(
        "--cavidad",
        type=Path,
        action="append",
        default=[],
        metavar="STL",
        help="malla a concatenar invertida, como vacío (repetible)",
    )
    args = p.parse_args(argv)

    archivos = _entradas(args.entradas)
    if not archivos:
        p.error("no hay modelos para procesar")
    if args.producto == "toothform":
        return _toothform(archivos, args)
    agregados = [_cargar(a) for a in args.agregar]
    cavidades = [_cargar(c) for c in args.cavidad]

    def alinear_ruta(ruta: Path, tipo: str):
        return alinear(
            _cargar(ruta),
            tipo,
            modo=args.modo,
            altura_corte=args.altura_corte,
            con_plantilla=not args.sin_plantilla,
        )

    referencias: dict[tuple, tuple[Path, object]] = {}  # maxilar -> (ruta, Resultado)
    fallas = 0
    for ruta in archivos:
        try:
            tipo = nombres.tipo_por_nombre(ruta, args.botones) if args.tipo == "auto" else args.tipo
            if tipo is None:
                raise ValueError("no se pudo deducir inf/sup del nombre; usar --tipo")
            if args.encuadre == "maxilar":
                k = maxilar.clave(ruta, tipo)
                if k not in referencias:
                    hermanos = [x for x in archivos if maxilar.clave(x, tipo) == k]
                    ref = maxilar.referencia(hermanos, tipo, args.botones) or ruta
                    referencias[k] = (ref, alinear_ruta(ref, tipo))
                ref, r = referencias[k]
                malla, avisos = maxilar.aplicar(_cargar(ruta), r.matriz)
                resumen = _resumen(r) if ref == ruta else f"encuadre del maxilar ({ref.name})"
                avisos = (r.avisos if ref == ruta else []) + avisos
            else:
                r = alinear_ruta(ruta, tipo)
                malla, resumen, avisos = r.malla, _resumen(r), r.avisos
            matriz = r.matriz
            if args.vaciado > 0:
                malla = hueco.vaciar(malla, args.vaciado)
            if args.producto == "cnc2":
                malla = cnc2.generar(malla, *cnc2.partes_de_nombre(ruta))
            elif args.producto == "cnc3":
                avisos = [*avisos, "CNC3 todavía no está hecho: se exportó solo el alineado"]
            final = exportar.concatenar(malla, agregados, cavidades)
            destino = exportar.destino_gh(ruta, args.producto, args.salida, args.sufijo)
            exportar.exportar_stl(final, destino)
            exportar.guardar_aligned(
                destino,
                ruta,
                matriz,
                tipo=tipo,
                modo=args.modo,
                producto=args.producto,
                encuadre=args.encuadre,
                vaciado=args.vaciado,
            )
        except Exception as e:  # noqa: BLE001 - un modelo roto no frena el lote
            fallas += 1
            print(f"ERROR {ruta.name}: {e}", file=sys.stderr)
            continue
        z = malla.bounds[:, 2]
        print(f"{ruta.name} [{tipo}] -> {destino}")
        print(f"   {resumen} | z {z[0]:.3f}..{z[1]:.2f}")
        for aviso in avisos:
            print(f"   AVISO: {aviso}")

    print(f"\n{len(archivos) - fallas}/{len(archivos)} modelos alineados")
    return 1 if fallas else 0


if __name__ == "__main__":
    raise SystemExit(main())


def _toothform(archivos: list[Path], args) -> int:
    """Como Toothform.exe por línea de comandos: <salida>/<ID>/<modelo>.stl,
    -gum.stl y -tooth.ply, y un <fecha>.<hora>.log con el mismo formato."""
    import json
    import time

    params = toothform.Parametros()
    if args.config:
        ajustes = json.loads(args.config.read_text(encoding="utf-8")).get("ParameterSettings", {})
        for k in vars(params):
            if k in ajustes:
                setattr(params, k, float(ajustes[k]))
    salida = args.salida or archivos[0].parent / "toothform"
    lineas, ok = [], 0
    for ruta in archivos:
        caso, _, modelo = ruta.stem.partition("-")
        try:
            r = toothform.generar(_cargar(ruta), caso, modelo or ruta.stem, params)
            toothform.exportar(r, salida / caso, ruta.stem)
            estado = r.estado
        except Exception as e:  # noqa: BLE001 - un modelo roto no frena el lote
            estado = "Failed to hollow"
            print(f"ERROR {ruta.name}: {e}", file=sys.stderr)
        ok += estado == "Export successfully"
        lineas.append(f"{ruta.stem}    {estado}")
        print(lineas[-1])
    lineas += ["", f"Total {len(archivos)} models, of which {ok} succeeded and "
               f"{len(archivos) - ok} failed"]
    salida.mkdir(parents=True, exist_ok=True)
    (salida / time.strftime("%Y%m%d.%H%M%S.log")).write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(lineas[-1])
    return 0 if ok == len(archivos) else 1
