"""API de la interfaz, contra un servidor de verdad en un hilo."""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import quote

import numpy as np
import pytest
from test_alinear import arcada, mover

from enkukador.ui.servidor import Manejador


@pytest.fixture
def servidor():
    s = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}"
    s.shutdown()


def get(url):
    with urllib.request.urlopen(url) as r:
        return r.read()


def post(url, datos):
    req = urllib.request.Request(
        url, json.dumps(datos).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def test_listar_alinear_y_ver(servidor, tmp_path):
    caso = tmp_path / "Prueba 1.0 stl"
    caso.mkdir()
    mover(arcada(), 30, volcar=True).export(caso / "0001 Prueba 1.0 sup 01.stl")
    (caso / "notas.txt").write_text("no es un modelo")

    lista = json.loads(get(f"{servidor}/api/listar?carpeta={quote(str(caso))}"))
    assert [m["tipo"] for m in lista["modelos"]] == ["sup"]
    ruta = lista["modelos"][0]["ruta"]

    r = post(
        f"{servidor}/api/alinear",
        {"ruta": ruta, "modo": "simetria", "salida": str(tmp_path / "out")},
    )
    assert r["estado"] in ("ok", "aviso")
    assert (tmp_path / "out" / "0001 Prueba 1.0 sup 01.stl").exists()

    tri = np.frombuffer(get(f"{servidor}/api/malla?ruta={quote(ruta)}&vista=alineado"), "<f4")
    assert tri.size % 9 == 0
    assert tri.reshape(-1, 3)[:, 2].min() == pytest.approx(0, abs=1e-4), "base en z=0"

    ex = json.loads(get(f"{servidor}/api/extras?ruta={quote(ruta)}"))
    assert len(ex["plantilla"]) == 4 and len(ex["curva"]) > 10


def test_pagina_y_errores(servidor):
    assert b"Enkukador" in get(f"{servidor}/")
    assert b"class Visor" in get(f"{servidor}/visor.js")
    with pytest.raises(urllib.error.HTTPError) as e:
        get(f"{servidor}/../servidor.py")
    assert e.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as e:
        get(f"{servidor}/api/listar?carpeta=/no/existe")
    assert e.value.code == 400


def test_explorar_y_cnc2(servidor, tmp_path):
    caso = tmp_path / "Caso stl"
    caso.mkdir()
    mover(arcada(radio=22.0), 10).export(caso / "XY001 Caso 1.0 inf 03.stl")
    ex = json.loads(get(f"{servidor}/api/explorar?ruta={quote(str(tmp_path))}"))
    assert [(c["nombre"], c["modelos"]) for c in ex["carpetas"]] == [("Caso stl", 1)]

    ruta = str(caso / "XY001 Caso 1.0 inf 03.stl")
    r = post(
        f"{servidor}/api/alinear", {"ruta": ruta, "producto": "cnc2", "salida": str(tmp_path / "o")}
    )
    assert r["destino"].endswith("XY001 Caso 1.0 inf 03 CNC2.stl")
    tri = np.frombuffer(get(f"{servidor}/api/malla?ruta={quote(ruta)}&vista=alineado"), "<f4")
    assert tri.size > 0

    r3 = post(
        f"{servidor}/api/alinear", {"ruta": ruta, "producto": "cnc3", "salida": str(tmp_path / "o")}
    )
    assert any("CNC3" in a for a in r3["avisos"])
