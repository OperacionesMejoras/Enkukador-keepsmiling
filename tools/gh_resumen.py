"""Listado legible de un .gh: componentes, cables, valores, scripts y clusters.

    python tools/gh_resumen.py "programa.gh" [--cluster "nombre"]

Usa tools/gh_a_xml.py para leer el binario. Cada componente sale como
[Nombre «apodo»#id] con sus entradas (de dónde viene cada cable, o el valor
fijo si no tiene cable), ordenado de izquierda a derecha como en el lienzo.
"""

from __future__ import annotations

import argparse
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gh_a_xml import gh_a_xml


def _items(ch):
    d = {}
    for i in ch.findall("item"):
        d.setdefault(i.get("name"), []).append(i)
    return d


def _objetos(doc):
    for c in doc.iter("chunk"):
        if c.get("name") == "DefinitionObjects":
            return [o for o in c.findall("chunk") if o.get("name") == "Object"]
    return []


def _nombre(o):
    return next(i.text for i in o.findall("item") if i.get("name") == "Name")


def _pivote(c):
    for a in c.findall("chunk"):
        if a.get("name") == "Attributes":
            for i in a.findall("item"):
                if i.get("name") in ("Pivot", "Bounds"):
                    return struct.unpack("<2f", bytes.fromhex(i.text)[:8])
    return (0.0, 0.0)


def describir(doc, titulo, solo=None, out=print):
    objs = _objetos(doc)
    duenio, filas, clusters = {}, [], []
    for o in objs:
        cs = [x for x in o if x.get("name") == "Container"]
        if not cs:
            continue
        c, n = cs[0], _nombre(o)
        d = _items(c)
        if n in ("Group", "Scribble"):
            if n == "Scribble":
                txt = [i.text for i in c.iter("item") if i.get("name") == "Text"]
                filas.append((_pivote(c), f"## NOTA: {txt}"))
            continue
        iid = d["InstanceGuid"][0].text
        apodo = d["NickName"][0].text if d.get("NickName") else ""
        lab = n + (f" «{apodo}»" if apodo and apodo != n else "") + f"#{iid[:4]}"
        for sl in c.findall("chunk"):
            if sl.get("name") == "Slider":
                v = next(i.text for i in sl.findall("item") if i.get("name") == "Value")
                lab = f"Slider«{apodo}»={v}#{iid[:4]}"
        duenio[iid] = lab
        entradas = []
        for p in c.iter("chunk"):
            if p.get("name") in ("param_input", "InputParam"):
                entradas.append(p)
            if p.get("name") in ("param_output", "OutputParam"):
                g = [i.text for i in p.findall("item") if i.get("name") == "InstanceGuid"]
                nn = [i.text for i in p.findall("item") if i.get("name") == "NickName"]
                if g:
                    duenio[g[0]] = f"{lab}.{nn[0] if nn else '?'}"
        for it in c.findall("item"):
            if it.get("name") == "ClusterDocument" and len(it):
                clusters.append((apodo or n, it))
        filas.append((_pivote(c), (c, n, lab, entradas, d)))

    if solo is None or solo == titulo:
        out("#" * 70 + f"\n# {titulo}\n" + "#" * 70)
        for _, f in sorted(filas, key=lambda r: r[0]):
            if isinstance(f, str):
                out(f)
                continue
            c, n, lab, entradas, d = f
            fuentes = [
                duenio.get(i.text, i.text[:6])
                for i in c.findall("item")
                if i.get("name") == "Source"
            ]
            texto = d.get("UserText", [None])[0]
            linea = f"[{lab}]"
            if fuentes:
                linea += " <- " + ", ".join(fuentes)
            elif texto is not None and texto.text:
                linea += f" texto={texto.text[:200]!r}"
            out(linea)
            for p in entradas:
                pd = {i.get("name"): i.text for i in p.findall("item")}
                s = [
                    duenio.get(i.text, i.text[:6])
                    for i in p.findall("item")
                    if i.get("name") == "Source"
                ]
                vals = [
                    f"{i.get('name')}={(i.text or '')[:60]}"
                    for ch in p.iter("chunk")
                    if ch.get("name") == "PersistentData"
                    for i in ch.iter("item")
                    if i.get("name") not in ("Count",)
                ]
                extra = "" if s or not vals else f"  {vals[:4]}"
                out(f"    .{pd.get('NickName')} <- {', '.join(s) if s else '-'}{extra}")
            for e in c.iter("item"):
                if e.get("name") == "Expression":
                    out(f"    EXPR: {e.text}")
                if e.get("name") in ("CodeInput", "ScriptSource", "Code", "Script") and e.text:
                    out("    CODE:\n" + "\n".join("      | " + li for li in e.text.splitlines()))
    for apodo, it in clusters:
        describir(it, f"CLUSTER «{apodo}»", solo, out)


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("gh", type=Path)
    p.add_argument("--cluster", help="mostrar solo ese cluster (apodo exacto)")
    a = p.parse_args()
    raiz = ET.fromstring(gh_a_xml(str(a.gh)))
    describir(raiz, "PRINCIPAL", f"CLUSTER «{a.cluster}»" if a.cluster else None)
