"""Lanzador del Enkukador: levanta el servidor local y abre la interfaz en el navegador.

    python lanzador.py            # si ya está corriendo, solo abre el navegador
    python lanzador.py --reinicio # lo usa el actualizador: espera a que el anterior termine

En Windows lo corre runtime\\Enkukador.exe (pythonw con otro nombre), sin
consola: la salida va a un archivo de registro y un ícono en la bandeja muestra
que está abierto y deja cerrarlo. Si se cierra la pestaña, el servidor se apaga
solo a los pocos minutos.

El puerto es el primero libre desde el 8765 (o ENKUKADOR_PORT). Queda anotado en
servidor.json, en la carpeta de datos, para que otro lanzamiento encuentre al que
ya corre y el actualizador vuelva a arrancar en el mismo puerto.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP = Path(__file__).resolve().parent
PROGRAMA = APP.parent
DESDE, HASTA = 8765, 8865
INSTALADA = APP.name == "app" and (PROGRAMA / "app-release.json").exists()


def carpeta_de_datos() -> Path:
    if os.environ.get("ENKUKADOR_HOME"):
        return Path(os.environ["ENKUKADOR_HOME"])
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Enkukador"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "enkukador"


def url(puerto: int) -> str:
    return f"http://127.0.0.1:{puerto}/"


def corriendo(puerto: int) -> bool:
    """¿Hay un Enkukador atendiendo en ese puerto?"""
    try:
        with urllib.request.urlopen(url(puerto) + "api/version", timeout=2) as r:
            return b"enkukador" in r.read()
    except OSError:
        return False


def libre(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", puerto))
        except OSError:
            return False
    return True


def anotado(datos: Path) -> int | None:
    try:
        return int(json.loads((datos / "servidor.json").read_text(encoding="utf-8"))["puerto"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def elegir_puerto(datos: Path, reinicio: bool = False) -> int:
    if os.environ.get("ENKUKADOR_PORT"):
        return int(os.environ["ENKUKADOR_PORT"])
    previo = anotado(datos)
    if reinicio and previo:
        for _ in range(60):  # el proceso anterior todavía está soltando el puerto
            if libre(previo):
                return previo
            time.sleep(0.25)
    for puerto in range(DESDE, HASTA):
        if libre(puerto):
            return puerto
    raise OSError(f"no hay ningún puerto libre entre {DESDE} y {HASTA - 1}")


def main() -> None:
    reinicio = "--reinicio" in sys.argv
    datos = carpeta_de_datos()
    datos.mkdir(parents=True, exist_ok=True)
    previo = anotado(datos)
    if not reinicio and previo and corriendo(previo):
        webbrowser.open(url(previo))
        return

    if INSTALADA or sys.stdout is None:
        registro = open(datos / "enkukador.log", "a", buffering=1, encoding="utf-8")  # noqa: SIM115
        sys.stdout = sys.stderr = registro
        # no quedarse parado en app\\: Windows no deja renombrar la carpeta de
        # trabajo de un proceso, y el actualizador renombra app\\
        os.chdir(PROGRAMA)

    puerto = elegir_puerto(datos, reinicio)
    (datos / "servidor.json").write_text(
        json.dumps({"puerto": puerto, "pid": os.getpid()}), encoding="utf-8"
    )
    print(f"Enkukador en {url(puerto)}", flush=True)

    sys.path.insert(0, str(APP))
    from enkukador.ui import bandeja, servidor

    icono = APP / "enkukador" / "ui" / "estatico" / "icono.ico"
    sacar_icono = bandeja.iniciar(url(puerto), icono, servidor.apagar)
    try:
        servidor.servir(
            None,
            puerto,
            abrir=not reinicio,
            autocierre=float(os.environ.get("ENKUKADOR_AUTOCIERRE", "180")),
        )
    finally:
        sacar_icono()


if __name__ == "__main__":  # imprescindible en Windows si algún día hay procesos hijos
    threading.current_thread().name = "principal"
    main()
