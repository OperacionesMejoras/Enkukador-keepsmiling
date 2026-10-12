"""Alineación de modelos de arcadas: base plana en z=0 y arco orientado.

Reemplazo en Python de la parte de orientación de "Modelos planos V5.06.02"
(Grasshopper). Ver README.md.
"""

__version__ = "0.1.1"

from .alinear import MODOS, TIPOS, Resultado, alinear
from .exportar import concatenar, exportar_stl

__all__ = ["MODOS", "TIPOS", "Resultado", "__version__", "alinear", "concatenar", "exportar_stl"]
