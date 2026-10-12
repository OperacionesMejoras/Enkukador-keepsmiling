# Enkukador

<img src="enkukador/ui/estatico/icono.png" width="96" align="right" alt="">

Prepara los modelos de arcadas dentales (STL) para la CNC del laboratorio:
**apoya la base plana en z=0, orienta el arco** (incisivos hacia +Y, arcada
centrada) y, si se pide, arma la salida **CNC2**: la chapa con el ID del caso y
el número de movimiento, las ranuras de los extractores y la marca, todo en un
mismo STL y sin operaciones booleanas. Opcionalmente vacía el modelo (cascarón).

Reemplaza la parte de orientación de *Modelos planos V5.06.02* (Grasshopper) sin
Rhino. Proyecto: Enkukador-keepsmiling, de Operaciones Mejoras (KeepSmiling).

## Instalar (Windows)

Bajar `EnkukadorSetup-<versión>.exe` de la página de
[releases](https://github.com/OperacionesMejoras/Enkukador-keepsmiling/releases)
y ejecutarlo. Se instala para el usuario (sin permisos de administrador), deja
accesos en el menú Inicio y, si se elige, en el escritorio. Al abrirlo levanta un
servidor local y abre la interfaz en el navegador; un ícono en la bandeja del
sistema permite volver a la pestaña o cerrarlo. Si se cierra la pestaña, se
apaga solo a los pocos minutos. Las actualizaciones se instalan desde el botón ⟳
de la interfaz.

## Desarrollo (Linux)

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python lanzador.py                  # la interfaz, como en Windows
.venv/bin/python -m enkukador "Caso 1.0 stl" --producto cnc2   # por consola
.venv/bin/python -m pytest -q
```

Para publicar una versión: crear un release en GitHub con su etiqueta (`v0.2.0`);
el workflow `release` corre las pruebas, arma el instalador con NSIS desde Linux
(`packaging/build_win.sh`) y lo cuelga del release.

> En discos NTFS montados en Linux los ejecutables de `.venv/bin/` no tienen
> permiso de ejecución: usar `.venv/bin/python -m ...`.

Tarda ~1 s por modelo. Por cada uno imprime qué encontró y los avisos:

```
BN595 Apellido Nombre 2.0 Sup 08.stl [sup] -> planos/BN595 Apellido Nombre 2.0 Sup 08.stl
   base 2428 mm² (3.2x la siguiente, planitud 0.010 mm) | cuadrante 90° | plantilla giro -0.12° tras
   (-0.01, +4.40) dist máx 1.08 mm | eje de simetría +0.60° (residuo 0.60 mm) | z -0.001..20.47
```

En modo `gh`, «eje de simetría» es cuánto quedó girada la arcada respecto de
su propio eje: sirve de control, no se corrige.

## Interfaz

```bash
.venv/bin/python lanzador.py        # o: .venv/bin/python -m enkukador.ui ["carpeta"]
```

Abre el navegador con una interfaz local (HTML + JavaScript vanilla, visor
WebGL propio, sin internet ni dependencias nuevas), al estilo de la que tenía
el GH con Human UI:

- **Izquierda** (se agranda arrastrando el borde): «Importar carpetas…» abre un
  explorador para armar el lote (una o varias carpetas de casos), producto
  (solo alineado, CNC2, CNC3), opciones y botones
  para alinear los marcados o todos; registro con avisos.
- **Centro**: visor 3D del modelo elegido, original o alineado, con el piso
  z=0, los ejes, la curva central (naranja) y los 4 puntos de la plantilla
  (verde). Arrastrar gira, botón derecho o shift mueve, la rueda hace zoom, F
  encuadra.
- **Etapas**: con un modelo alineado, una barra abajo del visor recorre las
  etapas alineadas del mismo maxilar con un fundido entre una y la siguiente
  (la sólida en beige, la otra translúcida en celeste); ▶ las recorre solas. Si
  todas quedaron en el mismo marco, base y contorno no se mueven.
- **Derecha** (también se agranda): árbol de modelos por inferiores/superiores
  con su estado (pendiente, ok, aviso, error) y el detalle del elegido.

Escucha solo en 127.0.0.1. Recuerda la última carpeta, las opciones y el ancho
de los paneles.

## Opciones

| Opción | Qué hace |
|---|---|
| `--producto alineado\|cnc2\|cnc3` | `cnc2` agrega la chapa (2 mm, ID y movimiento calados, Liberation Sans Bold = Arial Bold, 2,3 mm), las ranuras de los extractores (invertidas) y la marca de orientación, todo concatenado sin booleanas, con sufijo ` CNC2`. Medido contra salidas reales (AP962): mismas piezas, chapa a ±0,3 mm. `cnc3` todavía no hace nada (exporta el alineado y avisa). |
| `--vaciado MM` | Vacía el modelo dejando esa pared (ej. 2), abierto por la base. Sin booleanas: la cavidad va invertida en el mismo STL, como «Modelos huecos» del GH. Medido en BN595: pared de 2,00 mm (mediana), 49% menos material, ~3,5 s por modelo. |
| `--encuadre maxilar` *(por defecto)* | Los originales de un maxilar vienen superpuestos en la misma ubicación: se alinea la primera etapa (00 o la más baja) y esa misma matriz se aplica al resto, por separado para inf y sup. Igual al modo único (≤ 0,09 mm en BN595) y todas las etapas quedan en el mismo marco. Si alguna no comparte la ubicación (su base no cae en z=0), avisa. |
| `--encuadre unico` | Cada modelo se alinea por separado. |
| `--modo gh` *(por defecto)* | Réplica del GH. El giro fino lo amortigua el objetivo *Direction* de Kangaroo (ver abajo). |
| `--modo simetria` | El giro sale del eje de simetría de la curva central: corrige cualquier orientación de entrada. Para modelos que no vienen derechos del escáner. |
| `--tipo inf\|sup\|bot` | Fuerza el tipo. Por defecto se deduce del nombre (`... inf 03.stl`). |
| `--botones` | Las etapas `0`, `00`, `00b` van como botones/pasivos: solo se apoya la base, sin orientar el arco (el interruptor «Botones» del GH). |
| `--sin-plantilla` | No centra con la plantilla de 4 puntos. |
| `--altura-corte` | Altura del corte del contorno sobre la base (0,5 mm). |
| `--agregar STL` / `--cavidad STL` | Concatena otras mallas en el mismo STL, sin booleanas (ver abajo). Repetibles. |

## Qué hace, paso por paso

Todo sale de leer el `.gh` (cluster «orientador 3.1» y el cluster de Kangaroo
que lo sigue). Ver [docs/ANALISIS_GH.md](docs/ANALISIS_GH.md).

1. **Pieza principal**: si el STL trae varias piezas sueltas, se calcula con la
   de mayor área y el resto viaja con ella.
2. **Base plana**: casco convexo → región coplanar de mayor área → plano
   ajustado a sus vértices. El origen es el centroide del casco proyectado
   sobre ese plano y la Z apunta hacia adentro del modelo. Los ejes X/Y son los
   que arma Rhino a partir de una normal (`ON_Plane::CreateFromNormal`,
   replicado tal cual).
3. **Curva central**: corte a 0,5 mm de la base (ahí no hay dientes, es una U
   limpia) y su eje medial por Voronoi.
4. **Giro por cuadrantes**: vector del medio de la curva al origen; según en qué
   cuadrante cae respecto de Y, el plano se gira 180°, 90°, 0° o 270°. Hace
   falta porque el eje X de Rhino depende del ruido de la normal: con una
   normal (−1e-5, 3e-5, 1) sale X = +Y.
5. **Plantilla**: cuatro puntos fijos, (±14; 17,5) y (±22; −0,5), se apoyan
   como cuerpo rígido sobre la curva central y el modelo se mueve en
   consecuencia. Eso fija la posición de la arcada.

### El giro fino en el GH

Kangaroo tenía, además de *OnCurve* y *RigidBody*, un objetivo *Direction* que
mantiene la línea entre los dos puntos de adelante paralela a X, con el mismo
peso que *OnCurve*. Resultado: el giro casi no se corrige (más o menos un tercio
de lo que está torcido). El GH confiaba en que el escáner entrega la arcada
derecha, y en los crudos de BN595 es así: 0,4° a 0,9°. Si un modelo llega
girado, el modo `gh` lo deja girado y **avisa** («la arcada quedó girada X°
respecto de su eje de simetría»); para esos casos está `--modo simetria`.

## Salida: formato del GH y archivo `.aligned`

Por defecto la salida va donde la ponía el GH: `<caso> stl/MODELOS KUKA/<nombre>
CNC2.stl` (si los originales están en `Backup originales`, la carpeta del caso
es la de arriba). Solo alineado va a `planos/`. Con `--salida` se elige otra.

En lugar de copiar los originales a «Backup originales», al lado de cada STL se
guarda un `<nombre> CNC2.aligned`: un JSON con la matriz aplicada, su inversa,
el original y las opciones. Como no hay booleanas, el modelo dentro del STL son
los mismos vértices que el original, solo movidos, así que se recupera exacto
(medido: 0,000002 mm):

```bash
.venv/bin/python -m enkukador.desalinear "MODELOS KUKA/Caso Inf 05 CNC2.stl" --solo-modelo
```

## Mallas agregadas sin booleanas

El GH no restaba ni sumaba sólidos: juntaba mallas (*Mesh Join*) y exportaba
un único STL binario. Lo que tenía que ser vacío (ranuras, cavidad del ID) iba
con las normales invertidas (*Mesh Flip*): una cáscara cerrada de volumen
negativo dentro del modelo, que el slicer interpreta como hueco. En una salida
real (`AW960 ... inf 04 CNC2.stl`) se ve así: el modelo (+14 006 mm³), dos
cavidades (−499 y −498 mm³) y el relieve del ID (+228 mm³), todo en un STL
estanco.

```bash
.venv/bin/python -m enkukador modelo.stl --agregar relieve.stl --cavidad ranura.stl
```

Las mallas agregadas tienen que estar ya en el marco alineado.

## Validación

- **Contra el GH, BN595** (crudos del escáner y salidas `CNC3`): la diferencia
  entre este programa y el GH es la misma en los 35 modelos (17 inf, 18 sup),
  con un desvío de **0,03° y 0,04 mm** entre modelos. La base coincide (≤ 0,04°
  de inclinación). Queda un corrimiento constante (inf 1,8° y 2,1 mm; sup 0,7°
  y 1,7 mm).
- **Contra el GH, caso 0044** (salidas `CNC2` del
  2/6/2022): esa fecha corría la V3.01.00, que no tenía Voronoi ni Kangaroo,
  solo casco convexo + Orient. Comparado con lo mismo de este programa (solo
  base, `--tipo bot`), el giro coincide en **0,005° a 0,014°** y la inclinación
  en < 0,011°; solo cambia dónde ponía el origen (2 a 3 mm). Con el modo
  completo la diferencia es 0,4°: justamente el encaje del arco que esa versión
  no hacía.
- **De dónde sale ese corrimiento**: es constante dentro de un caso, pero no
  entre casos. En otra salida `CNC3` (AN398 inf 17, sin original), el giro de
  la `CNC3` coincide con el de este programa (0,05°) y la traslación es otra
  (4,8 mm en Y contra 2,2 mm en BN595). O sea, la versión `CNC3` (posterior al
  backup, su `.gh` no está) no aplica una corrección fija: decide el giro y la
  posición en Y con algún criterio propio por caso. Con un solo caso con
  originales no alcanza para deducirlo; se probó fijarlo como constante y
  empeoraba AN398, así que se descartó. Cada versión anterior también dejaba la
  arcada en un lugar algo distinto (tabla en `docs/ANALISIS_GH.md`).
- **Idempotencia**: 182 modelos ya procesados por el GH (`PRINT LAB MODELOS`)
  vuelven a pasar y se mueven 0,22° y 0,28 mm (medianas; máx. 0,93°).
- **Estabilidad** (`--modo simetria`): esos mismos modelos rotados y volcados
  al azar vuelven al mismo lugar con 0,03 mm de mediana.
- `pytest`: arcadas sintéticas en cualquier orientación, réplica del plano de
  Rhino, plantilla, concatenación con cavidades y nombres.

Casos que conviene mirar: arcadas muy angostas o muy anchas, donde la plantilla
de tamaño fijo no apoya bien (aviso «la plantilla quedó lejos de la curva»).

## Herramientas

`tools/separar_referencia.py` separa una salida del GH (`CNC2`, `CNC3`) en
modelo, referencia y demás piezas: como el GH concatenaba en lugar de hacer
booleanas, cada cosa es un cuerpo aparte.

`tools/gh_a_xml.py` convierte un `.gh` a XML (como un `.ghx`) sin Rhino,
expandiendo los clusters. Así se leyó el programa original.
