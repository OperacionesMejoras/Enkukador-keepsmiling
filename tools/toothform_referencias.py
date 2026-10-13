"""Mide la base que agrega ToothFORM (agujeros del robot, llave, placa, QR).

    python tools/toothform_referencias.py SALIDA.stl [--entrada ENTRADA.stl] [--json]
    python tools/toothform_referencias.py --pares carpeta_entradas carpeta_salidas > medidas.jsonl

Con un par entrada/salida además registra la entrada contra la salida
(triángulos idénticos: ToothFORM no los toca fuera de lo que recorta) y
calcula los candidatos para deducir dónde pone el origen, así se pueden juntar
muchos casos y ver cuál se mantiene. Ver docs/TOOTHFORM_REFERENCIAS.md.

Para leer el QR hacen falta `zxing-cpp` (decodificar) y `segno` (confirmar
modo, versión y máscara regenerándolo); sin ellos imprime la matriz de módulos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _circulo(p: np.ndarray) -> tuple[float, float, float, float]:
    """Ajuste de círculo por mínimos cuadrados: (cx, cy, r, error máximo)."""
    a = np.c_[2 * p[:, 0], 2 * p[:, 1], np.ones(len(p))]
    c = np.linalg.lstsq(a, (p**2).sum(1), rcond=None)[0]
    r = float(np.sqrt(c[2] + c[0] ** 2 + c[1] ** 2))
    return float(c[0]), float(c[1]), r, float(np.abs(np.linalg.norm(p - c[:2], axis=1) - r).max())


def agujeros(malla: trimesh.Trimesh, z: float) -> list[dict]:
    """Anillos circulares chicos del corte a altura z (Ø < 8 mm)."""
    s = malla.section([0, 0, 1], [0, 0, z])
    out = []
    for e in [] if s is None else s.discrete:
        cx, cy, r, err = _circulo(e[:, :2])
        if err < 0.03 and r < 4:
            out.append({"centro": [round(cx, 3), round(cy, 3)], "diametro": round(2 * r, 3)})
    return out


def niveles(malla: trimesh.Trimesh, minimo: float = 1.0) -> list[dict]:
    """Planos horizontales (z, área, hacia arriba/abajo) de más de `minimo` mm²."""
    h = np.abs(malla.face_normals[:, 2]) > 0.999
    z = np.round(malla.triangles_center[h, 2], 3)
    s = np.sign(malla.face_normals[h, 2])
    out = []
    for zz in np.unique(z):
        for sg in (-1, 1):
            sel = (z == zz) & (s == sg)
            a = float(malla.area_faces[h][sel].sum())
            if a > minimo:
                out.append({"z": float(zz), "area": round(a, 1), "mira": "arriba" if sg > 0 else "abajo"})
    return out


def alturas(malla: trimesh.Trimesh, xy: np.ndarray, desde: float = 50.0) -> np.ndarray:
    """z del primer impacto bajando desde `desde` en cada punto (nan si no hay)."""
    o = np.c_[xy, np.full(len(xy), desde)]
    loc, ir, _ = malla.ray.intersects_location(
        o, np.tile([0, 0, -1.0], (len(o), 1)), multiple_hits=True
    )
    z = np.full(len(o), -np.inf)
    if len(ir):
        np.maximum.at(z, ir, np.asarray(loc).reshape(-1, 3)[:, 2])
    z[np.isinf(z)] = np.nan
    return z


def qr(malla: trimesh.Trimesh, centro=(0.0, 0.0), busca: float = 12.0) -> dict | None:
    """Matriz del QR en relieve alrededor de `centro` y, si se puede, su contenido.

    El relieve es lo que sobresale del plano de la placa. Se mide la caja de lo
    que sobresale y se prueba con 21, 25, 29 y 33 módulos.
    """
    paso = 0.05
    xs = np.arange(-busca, busca, paso)
    gx, gy = np.meshgrid(xs + centro[0], xs + centro[1])
    z = alturas(malla, np.c_[gx.ravel(), gy.ravel()], desde=8.0).reshape(gx.shape)
    validos = z[np.isfinite(z)]
    if validos.size == 0:
        return None
    vals, cuenta = np.unique(np.round(validos, 2), return_counts=True)
    dos = vals[np.argsort(cuenta)[-2:]]
    placa, relieve = float(dos.min()), float(dos.max())
    # El QR está centrado en el agujero: su borde es donde, alejándose del
    # centro, el relieve se corta por más de medio milímetro (la placa que lo
    # rodea). Más allá puede haber otras superficies a la misma altura.
    alto = np.isfinite(z) & (np.abs(z - relieve) < 0.02)
    cheb = np.maximum(np.abs(gx - centro[0]), np.abs(gy - centro[1]))[alto]
    if cheb.size == 0:
        return None
    hay = np.bincount((cheb / paso).astype(int), minlength=int(busca / paso) + 1) > 0
    primero = int(np.argmax(hay))  # el centro es el agujero: arrancar desde el relieve
    medio = busca
    for k in np.flatnonzero(~hay[primero:]) + primero:
        if not hay[k : k + int(0.5 / paso)].any():
            medio = k * paso
            break
    x0, x1 = centro[0] - medio, centro[0] + medio
    y0, y1 = centro[1] - medio, centro[1] + medio
    lado = float(max(x1 - x0, y1 - y0))
    res = {
        "placa_z": placa,
        "relieve_z": relieve,
        "caja": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
        "lado": round(lado, 3),
    }
    try:
        import zxingcpp
        from PIL import Image
    except ImportError:
        zxingcpp = None
    for n in (21, 25, 29, 33):
        m = lado / n
        c = (np.arange(n) + 0.5) * m
        cx, cy = np.meshgrid(x0 + c, (y0 + c)[::-1])  # fila 0 arriba, visto desde +Z
        zz = alturas(malla, np.c_[cx.ravel(), cy.ravel()], desde=8.0).reshape(n, n)
        modulos = np.isfinite(zz) & (zz > (placa + relieve) / 2)
        agujero = ~np.isfinite(zz) | (zz < placa - 0.1)
        texto = None
        if zxingcpp is not None:
            img = np.kron(np.pad(~modulos, 4, constant_values=True), np.ones((10, 10)))
            r = zxingcpp.read_barcodes(Image.fromarray((img * 255).astype(np.uint8)))
            texto = r[0].text if r else None
        if texto or zxingcpp is None and n == 25:
            res.update(modulos=n, modulo_mm=round(m, 4), texto=texto)
            res["matriz"] = [
                "".join("o" if h else ("#" if v else ".") for v, h in zip(f, fh))
                for f, fh in zip(modulos, agujero)
            ]
            if texto:
                res.update(_como_se_genero(texto, n, modulos, agujero))
            return res
    return res


def _como_se_genero(texto: str, n: int, modulos: np.ndarray, agujero: np.ndarray) -> dict:
    """Regenera el QR con segno y busca modo, corrección, máscara y orientación."""
    try:
        import segno
    except ImportError:
        return {}
    version = (n - 17) // 4
    mejor = None
    for modo in ("numeric", "alphanumeric", "byte"):
        for err in "lmqh":
            for mask in range(8):
                try:
                    q = segno.make_qr(
                        texto, error=err, version=version, mode=modo, mask=mask, boost_error=False
                    )
                except Exception:  # noqa: BLE001 - modo que no admite el texto
                    continue
                g = np.array(q.matrix, bool)
                for rot in range(4):
                    for espejo in (False, True):
                        h = np.rot90(g, rot)
                        h = np.fliplr(h) if espejo else h
                        dif = int(((h != modulos) & ~agujero).sum())
                        if mejor is None or dif < mejor[0]:
                            mejor = (dif, modo, err.upper(), mask, rot * 90, espejo)
    dif, modo, err, mask, rot, espejo = mejor
    return {
        "version": version,
        "modo": modo,
        "correccion": err,
        "mascara": mask,
        "giro_vs_estandar": rot,
        "espejado_desde_arriba": espejo,
        "modulos_distintos": dif,
    }


def registrar(entrada: trimesh.Trimesh, salida: trimesh.Trimesh) -> np.ndarray:
    """Matriz entrada -> salida a partir de los triángulos que quedaron iguales."""
    def lados(m):
        t = m.triangles
        return np.round(
            np.stack([np.linalg.norm(t[:, i] - t[:, (i + 1) % 3], axis=1) for i in range(3)], 1),
            4,
        )

    vistos: dict[tuple, list[int]] = {}
    for i, k in enumerate(map(tuple, lados(entrada))):
        vistos.setdefault(k, []).append(i)
    pa, pb = [], []
    for j, k in enumerate(map(tuple, lados(salida))):
        if len(vistos.get(k, ())) == 1:
            pa.append(entrada.triangles[vistos[k][0]])
            pb.append(salida.triangles[j])
    if len(pa) < 10:
        raise ValueError("no hay triángulos en común: ¿es el par correcto?")
    pa, pb = np.concatenate(pa), np.concatenate(pb)
    mat, _, _ = trimesh.registration.procrustes(pa, pb, reflection=False, scale=False)
    ok = np.linalg.norm(trimesh.transform_points(pa, mat) - pb, axis=1) < 0.01
    mat, _, _ = trimesh.registration.procrustes(pa[ok], pb[ok], reflection=False, scale=False)
    return mat


def candidatos(entrada_en_salida: trimesh.Trimesh, corte: float) -> dict:
    """Con la entrada ya en el marco de salida: qué criterios dan eje X y origen."""
    from enkukador import arco
    from enkukador.base import pieza_principal

    m = entrada_en_salida.copy()
    m.apply_translation([0, 0, corte])  # base original en z=0 para el contorno
    encia = pieza_principal(m)
    poli = arco.contorno_base(encia, corte)
    rect = np.array(poli.minimum_rotated_rectangle.exterior.coords)[:2]
    lado = np.diff(rect, axis=0)[0]
    curva = arco.curva_central(poli)
    giro, residuo = arco.giro_simetria(np.c_[-curva[:, 1], curva[:, 0]])
    cruce = None
    for k in np.where(np.diff(np.sign(curva[:, 1])) != 0)[0]:
        t = curva[k, 1] / (curva[k, 1] - curva[k + 1, 1])
        cruce = float(curva[k, 0] + t * (curva[k + 1, 0] - curva[k, 0]))
    dientes = [p.centroid for p in m.split(only_watertight=False) if p.area < encia.area]
    e = np.array(poli.exterior.coords)
    b = poli.bounds
    return {
        "rect_minimo_angulo": round(float((np.degrees(np.arctan2(lado[1], lado[0])) + 45) % 90 - 45), 4),
        "rect_minimo_caja": [round(v, 3) for v in b],
        "eje_simetria_grados": round(giro, 3),
        "eje_simetria_residuo": round(residuo, 3),
        "curva_central_cruza_y0_en_x": None if cruce is None else round(cruce, 3),
        "punto_mas_anterior": [round(v, 3) for v in e[np.argmax(e[:, 0])]],
        "dientes": len(dientes),
        "dientes_media": np.round(np.mean(dientes, axis=0)[:2], 3).tolist() if dientes else None,
        "dientes_centro_caja": np.round(np.ptp(dientes, axis=0)[:2] / 2 + np.min(dientes, axis=0)[:2], 3).tolist()
        if dientes
        else None,
        "centroide_contorno": np.round(np.array(poli.centroid.coords[0]), 3).tolist(),
    }


def medir(salida: Path, entrada: Path | None = None) -> dict:
    tf = trimesh.load(salida, force="mesh")
    res: dict = {"salida": salida.name, "caja": np.round(tf.bounds, 3).tolist()}
    res["niveles"] = niveles(tf)
    res["agujeros_z1.5"] = agujeros(tf, 1.5)
    res["agujeros_z0.05"] = agujeros(tf, 0.05)
    res["qr"] = qr(tf)
    if entrada is not None:
        ent = trimesh.load(entrada, force="mesh")
        mat = registrar(ent, tf)
        res["matriz_entrada_a_salida"] = np.round(mat, 6).tolist()
        res["giro_z"] = round(float(np.degrees(np.arctan2(mat[1, 0], mat[0, 0]))), 4)
        ent.apply_transform(mat)
        corte = -float(ent.bounds[0][2])  # cuánto quedó la base original debajo de z=0
        res["recorte_base"] = round(corte, 3)
        res["candidatos"] = candidatos(ent, corte)
    return res


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("salida", type=Path, nargs="?", help="STL exportado por ToothFORM")
    p.add_argument("--entrada", type=Path, help="STL que se le dio a ToothFORM")
    p.add_argument("--pares", nargs=2, type=Path, metavar=("ENTRADAS", "SALIDAS"),
                   help="dos carpetas con los mismos nombres de archivo: una línea JSON por par")
    p.add_argument("--json", action="store_true", help="salida en JSON")
    a = p.parse_args(argv)
    if a.pares:
        for ent in sorted(a.pares[0].glob("*.stl")):
            sal = a.pares[1] / ent.name
            if not sal.exists():
                continue
            try:
                print(json.dumps(medir(sal, ent), ensure_ascii=False), flush=True)
            except Exception as e:  # noqa: BLE001 - un par roto no frena el lote
                print(json.dumps({"salida": ent.name, "error": str(e)}, ensure_ascii=False))
        return 0
    if a.salida is None:
        p.error("falta el STL de salida")
    res = medir(a.salida, a.entrada)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    matriz = res.get("qr", {}) and res["qr"].pop("matriz", None)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if matriz:
        print("\nQR visto desde arriba (# relieve, o agujero):")
        print("\n".join(matriz))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
