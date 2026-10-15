"""Servidor local de la interfaz: solo librería estándar + el alineador.

    .venv/bin/python -m enkukador.ui ["carpeta del caso"]

Escucha en 127.0.0.1 (no expone nada a la red) y abre el navegador. La página
es HTML + JS vanilla, con un visor WebGL propio: no baja nada de internet.

API (JSON salvo /api/malla):
    GET  /api/explorar?ruta=...       subcarpetas (con cuántos modelos tiene cada una)
    GET  /api/listar?carpeta=...      modelos de la carpeta con su tipo deducido
    POST /api/alinear                 {ruta, modo, tipo, botones, plantilla, salida, sufijo}
    GET  /api/malla?ruta=...&vista=   triángulos como float32 (original | alineado)
    GET  /api/extras?ruta=...         curva central y plantilla, en el marco alineado
"""

from __future__ import annotations

import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import trimesh

from .. import __version__, actualizar, cnc2, exportar, hueco, maxilar, nombres, toothform
from ..alinear import alinear
from ..cli import EXTENSIONES, _cargar, _resumen
from ..plantilla import PLANTILLA

ESTATICOS = Path(__file__).parent / "estatico"
TIPOS_MIME = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}

# El servidor en marcha (para apagarlo) y el último latido de la interfaz.
_vivo = {"servidor": None, "latido": time.monotonic()}


def apagar() -> None:
    srv = _vivo["servidor"]
    if srv is not None:
        threading.Thread(target=srv.shutdown, daemon=True).start()


def vigilar(segundos: float) -> None:
    """Si la interfaz deja de latir (se cerró la pestaña), apagar al rato."""

    def bucle() -> None:
        while True:
            time.sleep(5)
            if time.monotonic() - _vivo["latido"] > segundos:
                print("sin la interfaz abierta: se apaga", flush=True)
                apagar()
                return

    threading.Thread(target=bucle, name="autocierre", daemon=True).start()


def reiniciar() -> None:
    """Relanza el programa (después de actualizar) y apaga este."""
    import subprocess

    lanzador = actualizar.APP / "lanzador.py"
    opciones = {"creationflags": 0x08000000} if sys.platform == "win32" else {}  # sin consola
    subprocess.Popen(
        [sys.executable, str(lanzador), "--reinicio"], cwd=str(actualizar.PROGRAMA), **opciones
    )
    threading.Timer(0.5, apagar).start()


# Resultados de la sesión, por ruta del archivo original.
_resultados: dict[str, dict] = {}
# Encuadre por maxilar: (carpeta, tipo, modo, plantilla) -> resultado de la etapa de referencia.
_maxilares: dict[tuple, dict] = {}
_candado = threading.Lock()


def _cuenta_modelos(c: Path) -> int:
    try:
        return sum(1 for p in c.iterdir() if p.suffix.lower() in EXTENSIONES and p.is_file())
    except OSError:
        return 0


def _unidades() -> list[dict]:
    """Unidades de Windows (C:, D:, discos de red mapeados)."""
    import string

    return [
        {"nombre": f"{u}:\\", "ruta": f"{u}:\\", "modelos": 0}
        for u in string.ascii_uppercase
        if Path(f"{u}:\\").exists()
    ]


def explorar(ruta: str | None) -> dict:
    """Para el diálogo de importar: subcarpetas de `ruta` y cuántos modelos tienen.

    Sin ruta: en Windows la lista de unidades; en Linux la carpeta personal.
    Las rutas de red (\\\\servidor\\carpeta) se pueden escribir directo.
    """
    if not ruta and sys.platform == "win32":
        return {"ruta": "", "padre": None, "modelos": 0, "carpetas": _unidades()}
    c = Path(ruta).expanduser() if ruta else Path.home()
    if not c.is_dir():
        c = Path.home()
    carpetas = []
    try:
        hijos = sorted(
            (p for p in c.iterdir() if p.is_dir() and not p.name.startswith(".")),
            key=lambda p: p.name.lower(),
        )
    except OSError as e:
        raise ValueError(f"no se puede leer {c}: {e}") from e
    for p in hijos:
        carpetas.append({"nombre": p.name, "ruta": str(p), "modelos": _cuenta_modelos(p)})
    padre = str(c.parent) if c.parent != c else ("" if sys.platform == "win32" else None)
    return {
        "ruta": str(c),
        "padre": padre,
        "modelos": _cuenta_modelos(c),
        "carpetas": carpetas,
    }


def listar(carpeta: str, botones: bool = False) -> dict:
    c = Path(carpeta).expanduser()
    if not c.is_dir():
        raise ValueError(f"no existe la carpeta: {c}")
    modelos = []
    for p in sorted(c.iterdir()):
        if p.suffix.lower() in EXTENSIONES and p.is_file():
            previo = _resultados.get(str(p))
            modelos.append(
                {
                    "ruta": str(p),
                    "nombre": p.name,
                    "tipo": nombres.tipo_por_nombre(p, botones),
                    "estado": previo["estado"] if previo else "pendiente",
                    # lo que se graba en la pieza según el producto; la interfaz
                    # lo muestra antes de alinear y deja corregirlo
                    "ident": {
                        "toothform": list(toothform.caso_y_modelo(p.stem)),
                        "cnc2": list(cnc2.partes_de_nombre(p)),
                    },
                }
            )
    return {"carpeta": str(c), "modelos": modelos}


def _ident(datos: dict) -> tuple[str, str] | None:
    """El par (caso, modelo/movimiento) corregido en la interfaz, si vino."""
    par = [str(x).strip() for x in datos.get("ident") or []]
    return (par[0], par[1]) if len(par) == 2 and all(par) else None


def _base_salida(ruta: Path, salida: str | None, subcarpeta: str | None, producto: str) -> Path:
    """Carpeta donde exportar: la elegida o, si no hay, una subcarpeta junto al caso."""
    if salida:
        return Path(salida).expanduser()
    return exportar.destino_gh(ruta, producto, subcarpeta=subcarpeta or None).parent


def toothform_uno(datos: dict) -> dict:
    """Producto toothform: arma lo de ToothFORM (pieza, -gum.stl, -tooth.ply,
    -MatA.txt), que se exporta en <salida>/<ID>/. Usa su propio marco; encuadre,
    modo y tipo no cuentan. El espesor del vaciado, si se marca, es ShellThickness."""
    ruta = Path(datos["ruta"])
    caso, modelo = _ident(datos) or toothform.caso_y_modelo(ruta.stem)
    p = toothform.Parametros()
    espesor = float(datos.get("vaciado") or 0)
    if espesor > 0:
        p.ShellThickness = espesor
    try:
        r = toothform.generar(_cargar(ruta), caso, modelo, p)
    except toothform.FallaToothform as e:
        raise ValueError(f"{e.estado}: {e.detalle}") from e
    if r.estado not in toothform.EXPORTADOS:
        raise ValueError(f"{r.estado}: {'; '.join(r.avisos)}")

    def escribir(salida: str | None, subcarpeta: str | None) -> list[Path]:
        base = _base_salida(ruta, salida, subcarpeta, "toothform")
        return toothform.exportar(r, base / caso, ruta.stem)

    avisos = list(r.avisos)
    if r.estado != toothform.EXPORTO:
        avisos.insert(0, r.estado)
    estado = "aviso" if avisos else "ok"
    with _candado:
        _resultados[str(ruta)] = {
            "estado": estado, "matriz": r.matriz, "curva": None, "plantilla": False,
            "malla": r.pieza, "escribir": escribir, "exportado": None,
        }
    holgura = "" if r.holgura_qr in (None, float("inf")) else f" | pasillo QR: {r.holgura_qr:.2f} mm"
    return {
        "ruta": str(ruta),
        "tipo": "inf" if modelo[:1].upper() == "L" else "sup",
        "estado": estado,
        "resumen": f"ToothFORM: {r.estado} | QR: «{caso}{modelo.replace('-', '')}»{holgura}",
        "avisos": avisos,
    }


def alinear_uno(datos: dict) -> dict:
    if datos.get("producto") == "toothform":
        return toothform_uno(datos)
    ruta = Path(datos["ruta"])
    tipo = datos.get("tipo") or "auto"
    if tipo == "auto":
        tipo = nombres.tipo_por_nombre(ruta, bool(datos.get("botones")))
    if tipo is None:
        raise ValueError("no se pudo deducir inf/sup del nombre: elegí el tipo")
    modo = datos.get("modo", "gh")
    plantilla = bool(datos.get("plantilla", True))

    if datos.get("encuadre") == "maxilar":
        ref = _referencia_maxilar(ruta, tipo, modo, plantilla, bool(datos.get("botones")))
        malla, avisos = maxilar.aplicar(_cargar(ruta), ref["matriz"])
        info = {**ref, "avisos": avisos}
        resumen = f"encuadre del maxilar, tomado de {Path(ref['ruta']).name}"
        if Path(ref["ruta"]) == ruta:
            resumen = ref["resumen"] + " | referencia del maxilar"
            info["avisos"] = ref["avisos"] + avisos
    else:
        r = alinear(_cargar(ruta), tipo, modo=modo, con_plantilla=plantilla)
        malla, resumen = r.malla, _resumen(r)
        info = {
            "matriz": r.matriz,
            "curva": None if r.curva is None else r.curva.tolist(),
            "plantilla": r.ajuste is not None,
            "avisos": r.avisos,
        }

    producto = datos.get("producto", "alineado")
    espesor = float(datos.get("vaciado") or 0)
    if espesor > 0:
        malla = hueco.vaciar(malla, espesor)
        resumen += f" | vaciado {espesor:g} mm"
    if producto == "cnc2":
        id_caso, movimiento = _ident(datos) or cnc2.partes_de_nombre(ruta)
        malla = cnc2.generar(malla, id_caso, movimiento)
        resumen += f" | CNC2: chapa con «{id_caso}» y «{movimiento}», ranuras y marca"
    elif producto == "cnc3":
        info["avisos"] = [
            *info["avisos"],
            "CNC3 todavía no está hecho: se exportó solo el alineado",
        ]

    sufijo = datos.get("sufijo")
    encuadre = datos.get("encuadre", "unico")

    def escribir(salida: str | None, subcarpeta: str | None) -> list[Path]:
        base = _base_salida(ruta, salida, subcarpeta, producto)
        destino = exportar.destino_gh(ruta, producto, base, sufijo)
        exportar.exportar_stl(malla, destino)
        aligned = exportar.guardar_aligned(
            destino, ruta, info["matriz"], tipo=tipo, modo=modo, producto=producto,
            encuadre=encuadre, vaciado=espesor,
        )
        return [destino, aligned]

    estado = "aviso" if info["avisos"] else "ok"
    with _candado:
        _resultados[str(ruta)] = {
            "estado": estado,
            "matriz": info["matriz"],
            "curva": info["curva"],
            "plantilla": info["plantilla"],
            "malla": malla, "escribir": escribir, "exportado": None,
        }
    return {
        "ruta": str(ruta),
        "tipo": tipo,
        "estado": estado,
        "resumen": resumen,
        "avisos": info["avisos"],
    }


def exportar_uno(datos: dict) -> dict:
    """Escribe lo que dejó el último alineado de `ruta` (sin volver a calcular)."""
    ruta = str(Path(datos["ruta"]))
    previo = _resultados.get(ruta)
    if previo is None or "escribir" not in previo:
        raise ValueError("ese modelo todavía no se alineó")
    rutas = previo["escribir"](datos.get("salida") or None, datos.get("subcarpeta") or None)
    with _candado:
        previo["exportado"] = str(rutas[0])
    return {"ruta": ruta, "destino": str(rutas[0]), "archivos": [str(r) for r in rutas]}


def _referencia_maxilar(ruta: Path, tipo: str, modo: str, plantilla: bool, botones: bool) -> dict:
    """Alinea (una sola vez por sesión) la primera etapa del maxilar de `ruta`."""
    k = (*maxilar.clave(ruta, tipo), modo, plantilla)
    with _candado:
        if k in _maxilares:
            return _maxilares[k]
    hermanos = [p for p in ruta.parent.iterdir() if p.suffix.lower() in EXTENSIONES]
    ref = maxilar.referencia(hermanos, tipo, botones) or ruta
    r = alinear(_cargar(ref), tipo, modo=modo, con_plantilla=plantilla)
    resultado = {
        "ruta": str(ref),
        "matriz": r.matriz,
        "curva": None if r.curva is None else r.curva.tolist(),
        "plantilla": r.ajuste is not None,
        "resumen": _resumen(r),
        "avisos": r.avisos,
    }
    with _candado:
        _maxilares[k] = resultado
    return resultado


def triangulos(ruta: str, vista: str) -> bytes:
    """Triángulos (n, 3, 3) en float32, centrados si es la vista original."""
    m = trimesh.load(ruta, force="mesh")
    if vista == "alineado":
        previo = _resultados.get(ruta)
        if previo is None:
            raise ValueError("ese modelo todavía no se alineó")
        m = previo["malla"]  # lo que se va a exportar (CNC2, toothform, vaciado)
    else:
        m.apply_translation(-m.bounds.mean(axis=0))
    return np.ascontiguousarray(m.triangles, dtype="<f4").tobytes()


def extras(ruta: str) -> dict:
    previo = _resultados.get(ruta)
    if previo is None:
        return {"curva": None, "plantilla": None}
    return {
        "curva": previo["curva"],
        "plantilla": PLANTILLA.tolist() if previo["plantilla"] else None,
    }


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silencio en la consola
        pass

    def _responder(self, cuerpo: bytes, tipo: str, codigo: int = 200) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, obj, codigo: int = 200) -> None:
        self._responder(json.dumps(obj, ensure_ascii=False).encode(), "application/json", codigo)

    def _error(self, e: Exception) -> None:
        self._json({"error": str(e)}, 400)

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path == "/api/version":
                return self._json({"nombre": "enkukador", "version": __version__})
            if url.path == "/api/latido":
                _vivo["latido"] = time.monotonic()
                return self._json({"ok": True})
            if url.path == "/api/actualizacion":
                return self._json(
                    {**actualizar.estado(q.get("buscar") == "1"), "version": __version__}
                )
            if url.path == "/api/explorar":
                return self._json(explorar(q.get("ruta")))
            if url.path == "/api/listar":
                return self._json(listar(q.get("carpeta", ""), q.get("botones") == "1"))
            if url.path == "/api/malla":
                datos = triangulos(q["ruta"], q.get("vista", "original"))
                return self._responder(datos, "application/octet-stream")
            if url.path == "/api/extras":
                return self._json(extras(q["ruta"]))
            nombre = "index.html" if url.path in ("/", "") else url.path.lstrip("/")
            archivo = (ESTATICOS / nombre).resolve()
            if ESTATICOS.resolve() not in archivo.parents or not archivo.is_file():
                return self._responder(b"no encontrado", "text/plain", 404)
            tipo = TIPOS_MIME.get(archivo.suffix, "application/octet-stream")
            return self._responder(archivo.read_bytes(), f"{tipo}; charset=utf-8")
        except Exception as e:  # noqa: BLE001 - el error va a la interfaz
            return self._error(e)

    def do_POST(self):
        try:
            largo = int(self.headers.get("Content-Length", 0))
            datos = json.loads(self.rfile.read(largo) or b"{}")
            ruta = urlparse(self.path).path
            if ruta == "/api/alinear":
                return self._json(alinear_uno(datos))
            if ruta == "/api/exportar":
                return self._json(exportar_uno(datos))
            if ruta == "/api/apagar":
                self._json({"ok": True})
                return apagar()
            if ruta == "/api/actualizacion/instalar":
                res = actualizar.instalar(str(datos.get("tag") or ""))
                self._json(res)
                return reiniciar()
            if ruta == "/api/actualizacion/revertir":
                res = actualizar.revertir()
                self._json(res)
                return reiniciar()
            return self._responder(b"no encontrado", "text/plain", 404)
        except Exception as e:  # noqa: BLE001
            return self._error(e)


def servir(
    carpeta: str | None = None,
    puerto: int = 8765,
    abrir: bool = True,
    salida: str | None = None,
    autocierre: float = 0,
) -> None:
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    _vivo["servidor"] = servidor
    if autocierre > 0:
        vigilar(autocierre)
    url = f"http://127.0.0.1:{servidor.server_port}/"
    if carpeta:
        from urllib.parse import quote

        url += f"?carpeta={quote(str(Path(carpeta).resolve()))}"
        if salida:
            url += f"&salida={quote(str(Path(salida).resolve()))}"
    print(f"Enkukador en {url}  (Ctrl+C para salir)")
    if abrir:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
