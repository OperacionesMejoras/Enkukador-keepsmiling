# Análisis de *Modelos planos V5.06.02 PRUEBA.gh*

Fuente: el backup de programas de Grasshopper del laboratorio (`PROGRAMAS 11-10-23`).
De las versiones de *Modelos planos* ahí, la V5.06.02 PRUEBA es la más nueva:
archivo de octubre de 2023 (con su acceso directo, la que se usaba) y la única
con las dos revisiones del 18/05/2023. La V5.07.01 BETA tiene número más alto
pero es de antes (15/05/2023) y no tiene esas revisiones.

Se leyó con `tools/gh_a_xml.py`: 873 objetos en el lienzo, 5032 contando los de
adentro de los clusters (45 definiciones, algunas anidadas).

## Revisiones registradas en el archivo

| Fecha | Cambio |
|---|---|
| 05/12/2022 | La ranura pasa a ser una cavidad para los extractores; el ID va a la zona central inferior. |
| 15/12/2022 | Offset de la ranura del ID y movimiento de 0,8 a 1,5 mm (primeras capas de las Anycubic). |
| 19/01/2023 | Filtro que decide si el modelo lleva ranura. |
| 14/02/2023 | Orientación de la curva del ID para que siempre se lea al derecho desde abajo. |
| 18/05/2023 | **orientador 3.1**: si la curva central se cruza a sí misma, se rehace con puntos ordenados en círculo e interpolación. |
| 18/05/2023 | Discriminador de ranuras: cruces calculados por separado para evitar el autocruce. |

## Qué parte se reimplementó

Solo la orientación. Es el cluster **«orientador 3.1»** más el cluster de
Kangaroo que lo sigue (uno para inf y otro para sup). Quedó afuera: búsqueda de
carpetas, ranuras (*Ranuras V3*, *Modelos con ranuras V2*), ID, ahuecado
(*Modelos huecos*), interfaz (Human UI) y exportación a la CNC.

### orientador 3.1 (por modelo, dentro de un bucle de Anemone)

Entradas: `Modelos inf`, `Modelos sup`, `Modelos bot/pasivos`; un contador
elige cuál procesar.

1. `Disjoint Mesh` → `Mesh Area` → `Sort List` (salida invertida) → ítem 0:
   la pieza de mayor área. Para botones/pasivos se usa la malla entera.
2. `Deconstruct Mesh` → `3D ConvexHull` de los vértices.
3. `Face to Face Angles` (script VB) con dominio [0; 0,01°] → `Sift Pattern`:
   caras del casco coplanares con todas sus vecinas → `WeldMesh` →
   `Disjoint Mesh` → ítem 0 → `Plane Fit` de sus vértices.
4. Origen: `Volume` (centroide del casco) → `Plane Closest Point` sobre ese plano.
5. `Plane Normal` con esa normal; si `Mesh | Plane` a +3 mm no da curvas, se
   usa la normal invertida → «Plano normal» (Z hacia adentro del modelo).
6. `Plane Offset` 0,5 mm → `Mesh | Plane` → la curva más larga → `Project` al
   plano → `Divide Curve` (20) → `Interpolate` periódico → `Divide Curve` (100)
   → `Voronoi` (radio 8,5) → segmentos que no cortan el contorno → limpieza de
   duplicados y ramas → `Join Curves` → `Smooth Polyline`: la **curva central**.
7. `Point On Curve` (0,5) → `Vector 2Pt` hacia el origen → `Angle` contra el eje
   Y del plano → dominios `-45 a 45`, `45 a 135`, `135 a 225`, `225 a 315` →
   giro `180`, `90`, `0`, `270` → `Rotate` del plano (en grados).
8. `Orient` del plano girado al plano XY del mundo. Botones/pasivos usan el
   plano sin girar.

### Ajuste con Kangaroo (después del orientador)

Puntos fijos (cluster de sliders): adelante (±14; 17,5), atrás (±22; −0,5).
Objetivos: `OnCurve` (los 4 puntos sobre la curva central, fuerza 1),
`RigidBody` (fuerza 10), `Direction` (línea de los puntos de adelante paralela
a X, fuerza 1), `Length(Line)` (fuerza 100), `Grab`. El `Solver` mueve los
puntos; se arma un plano con los dos primeros antes y después, y el modelo se
lleva con `Orient` del plano resuelto al inicial.

## Lo que se cambió y por qué

- **Curva central**: en vez de recortar las celdas de Voronoi contra el
  contorno y podar ramas a mano, se toma el esqueleto interior y su camino más
  largo. El suavizado a 20 puntos del GH se probó y se descartó: depende de
  dónde arranca el muestreo y movía el resultado ~1 mm entre corridas.
- **Distancia a la curva** en el ajuste: se mide por equidistancia a las dos
  orillas de la U (definición del eje medial) y no contra la polilínea, cuyas
  puntas se abren en horquilla hacia las esquinas del corte.
- **Kangaroo**: se minimiza directamente la energía equivalente,
  `Σ d(Pᵢ)² + L²·sin²θ / 2`, con varios arranques de ángulo.
- **Botones/pasivos**: el GH usaba ahí el plano anterior a la corrección de la
  normal (podía dejar el modelo boca abajo); acá se usa el corregido.
- **Botones por defecto apagado**: en BN595 el `Sup 00` se orientó como arcada.

## Mallas agregadas

Las ranuras, la cavidad del ID y los movimientos se hacían como BRep,
`Mesh Brep` → `Mesh Join` → `Mesh Flip` (las que son vacío) y se unían al
modelo con `Mesh Join`. Un solo `Export STL` binario por modelo, con sufijo
` CNC2` (o ` CID`) en la carpeta `MODELOS KUKA`. Ninguna operación booleana.

## Evolución entre versiones

Contando componentes en cada `.gh` del backup:

| Versión | Voronoi | Kangaroo (Solver/OnCurve) | Orientador |
|---|---|---|---|
| V3.01.00 (01/06/2022) | no | no | solo base (casco convexo + Orient) |
| V3.02.00, V4.02.00 | sí | no | orientador 2.0 |
| V5.03.00 | sí | sí | orientador 3.0 |
| V5.06.02 PRUEBA | sí | sí | orientador 3.1 |

Por eso las salidas del GH no coinciden todas entre sí: cada versión dejaba la
arcada en un lugar algo distinto. Las del caso 0044 (junio de 2022, V3.01.00)
coinciden en giro con el modo "solo base" de este programa en ≤ 0,014°.
