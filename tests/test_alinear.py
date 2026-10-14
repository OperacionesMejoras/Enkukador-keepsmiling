import numpy as np
import pytest
import trimesh
from shapely.geometry import Point, box
from trimesh.transformations import rotation_matrix as rm

from enkukador import alinear, base, concatenar, nombres


def arcada(radio=21.0, ancho=8.0, alto=12.0, recorte_y=-6.0, extra=0.0):
    """U extruida: anillo cortado por debajo de y=recorte_y, incisivos hacia +Y.

    `extra` alarga una de las ramas, para tener un recorte asimétrico como en
    los modelos reales.
    """
    anillo = (
        Point(0, 0)
        .buffer(radio + ancho / 2, 256)
        .difference(Point(0, 0).buffer(radio - ancho / 2, 256))
    )
    u = anillo.intersection(box(-50, recorte_y, 50, 50))
    if extra:
        u = u.union(anillo.intersection(box(0, recorte_y - extra, 50, recorte_y)))
    malla = trimesh.creation.extrude_polygon(u.simplify(0.05), alto)
    malla = malla.subdivide_to_size(1.5)
    # "dientes": la tapa ondulada, para que no sea otra cara plana como la base
    v = malla.vertices.copy()
    arriba = v[:, 2] > alto - 1e-6
    ang = np.arctan2(v[arriba, 1], v[arriba, 0])
    v[arriba, 2] += 2.0 + 1.5 * np.sin(14 * ang)
    malla.vertices = v
    return malla


def mover(malla, giro, volcar=False, inclinar=7.0, semilla=0):
    rng = np.random.default_rng(semilla)
    T = rm(np.radians(giro), [0, 0, 1])
    if volcar:
        T = rm(np.pi, [1, 0, 0]) @ T
    T = rm(np.radians(inclinar), [1, 0.4, 0]) @ T
    T[:3, 3] = rng.uniform(-40, 40, 3)
    m = malla.copy()
    m.apply_transform(T)
    return m


def test_plano_rhino_replica_opennurbs():
    p = base.plano_rhino([0, 0, 0], [0, 0, 1])
    assert np.allclose(p.x, [1, 0, 0]) and np.allclose(p.y, [0, 1, 0])
    p = base.plano_rhino([0, 0, 0], [0, 0, -1])
    assert np.allclose(p.x, [-1, 0, 0]) and np.allclose(p.y, [0, 1, 0])
    # Ruido de 1e-5 en la normal cambia la rama de PerpendicularTo: X pasa a +Y.
    # Por eso el GH necesitaba el giro por cuadrantes después.
    p = base.plano_rhino([0, 0, 0], [-1e-5, 3e-5, 1])
    assert np.allclose(p.x, [0, 1, 0], atol=1e-4)


@pytest.mark.parametrize("volcar", [False, True])
@pytest.mark.parametrize("giro", [0, 33, 100, -150])
def test_apoya_la_base_y_orienta_el_arco(giro, volcar):
    original = arcada(extra=4.0)
    r = alinear(mover(original, giro, volcar), "inf", modo="simetria")
    m = r.malla

    assert abs(m.bounds[0][2]) < 1e-6, "la base tiene que quedar en z=0"
    assert m.bounds[1][2] == pytest.approx(original.bounds[1][2], abs=1e-3), "y del lado correcto"
    assert np.isclose(m.volume, original.volume), "transformación rígida"

    # Incisivos hacia +Y: el punto más alto en Y está sobre el eje.
    apice = m.vertices[np.argmax(m.vertices[:, 1])]
    assert abs(apice[0]) < 1.0
    # Simétrica en X pese a la rama más larga.
    assert m.bounds[0][0] == pytest.approx(-m.bounds[1][0], abs=0.3)
    assert r.simetria[1] < 0.5


def test_plantilla_ubica_el_arco_igual_que_el_gh():
    """Los 4 puntos (±14; 17,5) y (±22; -0,5) caen sobre un círculo de radio
    22,02 con centro en (0; 0,5): una arcada así tiene que terminar ahí."""
    original = arcada(radio=22.02)
    T = rm(np.radians(70), [0, 0, 1])
    T[:3, 3] = [5, -8, 3]
    m = original.copy()
    m.apply_transform(T)
    r = alinear(m, "sup", modo="simetria")
    assert r.ajuste.distancias.max() < 0.2
    centro = trimesh.transform_points([[0, 0, 0]], r.matriz @ T)[0]
    assert centro[:2] == pytest.approx([0.0, 0.5], abs=0.15)


def test_modo_gh_amortigua_el_giro():
    """Con el objetivo Direction de Kangaroo el giro fino casi no se corrige."""
    m = mover(arcada(), 12, inclinar=0)
    sim = alinear(m, "inf", modo="simetria")
    gh = alinear(m, "inf", modo="gh")
    eje = lambda r: np.degrees(np.arctan2(r.matriz[1, 0], r.matriz[0, 0]))
    assert eje(sim) == pytest.approx(-12, abs=0.5)
    assert abs(eje(gh)) < 12 - 5, "el GH solo corrige una parte"
    assert any("girada" in a for a in gh.avisos), "y lo avisa"
    assert not any("girada" in a for a in sim.avisos)


def test_botones_solo_apoyan_la_base():
    r = alinear(mover(arcada(), 40, volcar=True), "bot")
    assert r.cuadrante is None and r.ajuste is None
    assert abs(r.malla.bounds[0][2]) < 1e-6


def test_concatenar_cavidad_resta_volumen_sin_booleana():
    modelo = trimesh.creation.box([20, 20, 10])
    cavidad = trimesh.creation.box([4, 4, 4])
    junto = concatenar(modelo, cavidades=[cavidad])
    assert len(junto.faces) == len(modelo.faces) + len(cavidad.faces)
    assert junto.volume == pytest.approx(modelo.volume - cavidad.volume)


@pytest.mark.parametrize(
    "nombre, tipo",
    [
        ("0044 Apellido Nombre 1.0 sup 01.stl", "sup"),
        ("BN595 Apellido Nombre 2.0 Inf 17.stl", "inf"),
        ("AT144 inf 00.stl", "inf"),
        ("otra cosa.stl", None),
    ],
)
def test_tipo_por_nombre(nombre, tipo):
    assert nombres.tipo_por_nombre(nombre) == tipo


def test_botones_solo_con_el_interruptor():
    assert nombres.tipo_por_nombre("AT144 inf 00.stl", botones=True) == "bot"
    assert nombres.tipo_por_nombre("caso Sup 00b.stl", botones=True) == "bot"
    assert nombres.tipo_por_nombre("caso Sup 01.stl", botones=True) == "sup"


def test_encuadre_por_maxilar(tmp_path):
    """Etapas superpuestas: la matriz de la primera sirve para todas; si una
    etapa no comparte la ubicación, se avisa."""
    from enkukador import maxilar

    rutas = []
    for i in range(3):
        m = arcada(alto=12 + i)  # cambia la etapa, no la ubicación
        m.apply_transform(rm(np.pi, [1, 0, 0]))
        m.apply_transform(rm(np.radians(7), [1, 0.4, 0]))
        ruta = tmp_path / f"Caso sup 0{i}.stl"
        m.export(ruta)
        rutas.append(ruta)
    assert maxilar.referencia(rutas, "sup").name == "Caso sup 00.stl"

    ref = alinear(trimesh.load(rutas[0]), "sup")
    for r in rutas[1:]:
        movido, avisos = maxilar.aplicar(trimesh.load(r), ref.matriz)
        assert not avisos
        assert abs(movido.bounds[0][2]) < 1e-3

    corrido = trimesh.load(rutas[2])
    corrido.apply_transform(rm(np.radians(5), [0, 1, 0]))
    _, avisos = maxilar.aplicar(corrido, ref.matriz)
    assert avisos and "no comparte" in avisos[0]


def test_cnc2_chapa_ranuras_y_marca():
    from enkukador import cnc2

    r = alinear(mover(arcada(radio=22.0), 25), "inf", modo="simetria")
    final = cnc2.generar(r.malla, "AB123", "07")
    piezas = sorted(final.split(only_watertight=False), key=lambda p: -abs(p.volume))
    vols = [p.volume for p in piezas]
    assert len(piezas) == 5, "modelo, 2 ranuras, chapa y marca"
    assert all(p.is_watertight for p in piezas)
    assert vols[1] < 0 and vols[2] < 0, "las ranuras van invertidas (vacío)"
    chapa = next(p for p in piezas if 50 < p.volume < 400)
    assert chapa.bounds[0][2] == pytest.approx(0) and chapa.bounds[1][2] == pytest.approx(2.0)
    corte = chapa.section([0, 0, 1], [0, 0, 1]).to_2D(to_2D=np.eye(4))[0]
    assert len(max(corte.polygons_full, key=lambda p: p.area).interiors) == len("AB123") + len("07")


def test_partes_de_nombre():
    from enkukador import cnc2

    assert cnc2.partes_de_nombre("AP962 Apellido Nombre 1.0 Inf 05.stl") == ("AP962", "05")


def test_destino_formato_gh():
    from pathlib import Path

    from enkukador.exportar import destino_gh

    caso = Path("/x/Caso 1.0 stl")
    assert (
        destino_gh(caso / "Caso inf 03.stl", "cnc2")
        == caso / "MODELOS KUKA" / "Caso inf 03 CNC2.stl"
    )
    # desde los originales respaldados va a la carpeta del caso, no adentro del backup
    assert destino_gh(caso / "Backup originales" / "Caso inf 03.stl", "cnc2") == (
        caso / "MODELOS KUKA" / "Caso inf 03 CNC2.stl"
    )
    assert destino_gh(caso / "a.stl", "cnc2", Path("/o")) == Path("/o/a CNC2.stl")


def test_aligned_vuelve_al_original_exacto(tmp_path):
    from enkukador import cnc2
    from enkukador.exportar import desalinear, exportar_stl, guardar_aligned

    original = mover(arcada(radio=22.0), 40, volcar=True)
    ruta = tmp_path / "AB1 inf 02.stl"
    original.export(ruta)
    r = alinear(trimesh.load(ruta), "inf")
    destino = exportar_stl(cnc2.generar(r.malla, "AB1", "02"), tmp_path / "AB1 inf 02 CNC2.stl")
    aligned = guardar_aligned(destino, ruta, r.matriz, tipo="inf")
    assert aligned.suffix == ".aligned"

    vuelto = desalinear(destino, solo_modelo=True)
    orig = trimesh.load(ruta)
    assert len(vuelto.vertices) == len(orig.vertices)
    assert np.abs(np.sort(vuelto.vertices, 0) - np.sort(orig.vertices, 0)).max() < 1e-3


def test_vaciado_cosido():
    from enkukador import hueco

    m = alinear(mover(arcada(radio=22.0, ancho=10, alto=14), 0), "inf").malla
    solido = hueco.unir(m)
    v = hueco.coser(solido, hueco.cavidad(solido, 2.0, paso=0.4))  # sin el plan B
    assert v.is_watertight and v.body_count == 1, "una sola malla cerrada"
    assert 0 < v.volume < 0.6 * m.volume
    assert v.bounds[0][2] > -1e-6, "nada por debajo de la cama"
    piso = v.area_faces[(v.face_normals[:, 2] < -0.99) & (v.triangles_center[:, 2] < 1e-3)].sum()
    base = m.area_faces[(m.face_normals[:, 2] < -0.99) & (m.triangles_center[:, 2] < 1e-3)].sum()
    assert piso < 0.6 * base, "abierto por la base"
    # la superficie exterior no se toca: todos sus vértices fuera de la base siguen ahí
    from scipy.spatial import cKDTree

    arriba = m.vertices[m.vertices[:, 2] > 1e-3]
    assert cKDTree(v.vertices).query(arriba)[0].max() < 1e-9


def test_vaciado_liso_pared_pareja():
    from enkukador import hueco

    m = alinear(mover(arcada(radio=22.0, ancho=10, alto=14), 0), "inf").malla
    c = hueco.cavidad(m, 2.0, paso=0.25)
    assert c.is_watertight
    pts = c.vertices[c.vertices[:, 2] > 0.5]
    d = hueco._distancia_exacta(m, pts)
    assert np.percentile(d, 1) > 1.85 and np.percentile(d, 99) < 2.1, "sin escalones de vóxel"


def test_vaciado_une_las_piezas(tmp_path):
    """Una «raíz» suelta dentro de la encía se une antes de vaciar: no queda maciza."""
    from enkukador import hueco

    m = alinear(mover(arcada(radio=22.0, ancho=10, alto=14), 0), "inf").malla
    frente = m.vertices[np.argmax(m.vertices[:, 1])]  # incisivos: el punto más adelante
    raiz = trimesh.creation.cylinder(radius=2.0, height=10.0)
    raiz.apply_translation([frente[0], frente[1] - 5.0, 8.0])  # en medio de la pared
    v = hueco.vaciar(trimesh.util.concatenate([m, raiz]), 2.0)
    assert v.body_count == 1, "sin la raíz aparte"
    hueco_solo = hueco.vaciar(m, 2.0)
    assert v.volume == pytest.approx(hueco_solo.volume, rel=0.02), "la raíz no queda maciza"
    # Releído del STL (float32) sigue siendo una malla cerrada, sin astillas.
    v.export(tmp_path / "v.stl")
    releido = trimesh.load(tmp_path / "v.stl")
    assert releido.body_count == 1 and releido.is_watertight


def _arcada_con_dientes():
    m = mover(arcada(radio=22.0, ancho=10, alto=14), 0)
    r = alinear(m, "inf").malla
    dientes = []
    for ang in np.radians(np.linspace(20, 160, 8)):
        d = trimesh.creation.cylinder(radius=2.5, height=8.0, sections=24)
        d.apply_translation([0, 0, 13.0])
        dientes.append(d)
    # poner los dientes sobre la cresta, en el marco alineado (incisivos hacia +Y)
    curva = None
    from enkukador import arco

    poli = arco.contorno_base(r, 0.5)
    curva = arco.remuestrear_curva(arco.curva_central(poli), 0.5)
    idx = np.linspace(len(curva) * 0.1, len(curva) * 0.9, len(dientes)).astype(int)
    for d, i in zip(dientes, idx):
        d.apply_translation([curva[i, 0], curva[i, 1], 0])
    return trimesh.util.concatenate([r, *dientes])


def test_toothform_pieza_encia_dientes(tmp_path):
    from enkukador import toothform

    m = _arcada_con_dientes()
    r = toothform.generar(m, "AB123", "L05-A")
    assert r.estado == "Export successfully"
    p = r.pieza
    assert p.is_watertight and p.body_count == 1
    assert p.bounds[0][2] == pytest.approx(0, abs=1e-6)
    # agujeros del robot: R2 en el origen y R1 en (20, 0), con los radios del config
    corte = p.section([0, 0, 1], [0, 0, 1.5])
    radios = {}
    for e in corte.discrete:
        c = e[:, :2].mean(axis=0)
        r_med = np.linalg.norm(e[:, :2] - c, axis=1)
        if r_med.std() < 0.05:
            radios[tuple(np.round(c))] = r_med.mean()
    assert radios.get((0.0, 0.0)) == pytest.approx(2.12, abs=0.02)
    assert radios.get((20.0, 0.0)) == pytest.approx(2.62, abs=0.02)
    # QR en relieve: lo más alto de la lengüeta está a 3,2
    lengueta = p.vertices[(np.abs(p.vertices[:, 0]) < 7) & (np.abs(p.vertices[:, 1]) < 7)]
    assert lengueta[:, 2].max() == pytest.approx(3.2, abs=1e-3)
    # encía: tapada en z=0, abierta solo donde apoyan los dientes; dientes cerrados
    assert r.encia.bounds[0][2] == pytest.approx(0, abs=1e-6) and not r.encia.is_watertight
    assert r.dientes.body_count == 8 and r.dientes.is_watertight
    rutas = toothform.exportar(r, tmp_path / "AB123", "AB123-L05-A")
    assert [x.name for x in rutas] == ["AB123-L05-A.stl", "AB123-L05-A-gum.stl", "AB123-L05-A-tooth.ply"]
    assert trimesh.load(rutas[2]).body_count == 8


def test_toothform_limite_de_altura():
    from enkukador import toothform

    r = toothform.generar(_arcada_con_dientes(), "AB123", "L05-A", toothform.Parametros(LimitH=10))
    assert r.estado == "Height limit exceeded"


def test_toothform_qr_como_toothform():
    """El QR que arma ToothFORM para BZ219-L05-A (leído de su STL), módulo a módulo."""
    from enkukador import toothform

    q = toothform._qr_modulos("BZ219L05A", 15.0)
    # primera fila vista desde arriba (# = módulo en relieve), medida en la salida real
    fila = "#######...##.##.#....#..#"
    centros = [(-7.5 + 0.3 + 0.6 * j, 7.5 - 0.3) for j in range(25)]
    from shapely.geometry import Point

    assert "".join("#" if q.contains(Point(c)) else "." for c in centros) == fila
