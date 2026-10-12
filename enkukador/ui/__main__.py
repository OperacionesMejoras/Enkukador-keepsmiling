import argparse

from .servidor import servir

p = argparse.ArgumentParser(prog="enkukador.ui", description="Interfaz del Enkukador")
p.add_argument("carpeta", nargs="?", help="carpeta del caso a abrir")
p.add_argument("--salida", help="carpeta donde guardar los alineados")
p.add_argument("--puerto", type=int, default=8765)
p.add_argument("--sin-navegador", action="store_true", help="no abrir el navegador")
a = p.parse_args()
servir(a.carpeta, a.puerto, abrir=not a.sin_navegador, salida=a.salida)
