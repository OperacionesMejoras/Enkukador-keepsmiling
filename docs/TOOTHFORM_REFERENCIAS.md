# ToothFORM: referencias del robot y QR (ingeniería inversa)

Medido sobre **dos pares** entrada/salida: BZ219-L05-A (inferior) y
BZ254-U05-A (superior), con ToothFORM release 20260518, Type1, y el
`config.json` del informe (`ShellThickness 1.8`, `BottomPlaneThickness 1.0`,
`QrSize 15.0`, `Radius1 2.62`, `Radius2 2.12`). Todo lo de la base, los
agujeros, el QR y el texto dio igual en los dos. Lo que no se pudo cerrar está
marcado como **a confirmar**.

Las salidas que importan: **la pieza con referencias** se imprime en 3D;
**`-gum.stl` y `-tooth.ply`** van al proceso que calcula la curva de corte.

Herramienta para medir: `tools/toothform_referencias.py` (ver al final).
Reproducción: `enkukador/toothform.py`, `--producto toothform` (ver
«Prototipo»).

![plano](toothform/plano_referencias.png)

## Marco de salida

La entrada aparece en la salida movida por un movimiento rígido: 48 740
triángulos quedan idénticos, y con ellos la transformación se recupera con
error ~1e-13 mm.

- **Giro solo en Z** (inclinación 0,00004°): ToothFORM confía en que la base
  ya viene plana. Para BZ219-L05-A: giro −103,887°, traslación (3,407; 0,029;
  15,310).
- **Recorta 0,5 mm de abajo**: la base original queda en z = −0,5 y el modelo
  se corta en z = 0.
- **Orientación** (medido): se toma el contorno del corte (a 0,5 mm de la base
  original) y su **rectángulo de área mínima** queda alineado con X/Y (ángulo
  0,000°). El eje de simetría de la arcada queda a 2,0° y el PCA, a entre 7° y
  11°, así que no son el criterio. Los incisivos quedan hacia **+X**.
- **El superior también se da vuelta** y, si la base viene inclinada respecto
  de la Z del escáner (4,33° en BZ254), la apoya: usa el plano de la base.
- **Origen**: el centro del QR, que es el agujero R2. **A confirmar** qué lo
  ubica respecto de la arcada. El punto más anterior de la curva central cae
  en (21,45; −1,36) y (21,67; −0,64); ningún otro criterio probado (centro del
  rectángulo, media de dientes, incisivos centrales, simetría) da lo mismo en
  los dos. El prototipo usa ese punto en (21,56; −1,0): ±0,1 mm en X y ±0,4 mm
  en Y en estos dos casos.

## Referencias del robot

Las tres van sobre el eje X, en la placa central:

| | Posición | Forma |
|---|---|---|
| **R2** (`Radius2` = 2,12) | (0, 0) | Pasante, Ø 4,24. Chaflán abajo de ~0,55 mm a 45° (Ø 5,34 en z=0). Atraviesa el centro del QR. |
| **Llave en D** | x 9 → 12, y −2 → +2 | Pasante, rectángulo de 3 × 4 con la esquina (+x, −y) cortada de (10,5; −2) a (12; 0). Anti-giro. |
| **R1** (`Radius1` = 2,62) | (20, 0) | Ciego. Cilindro Ø 5,24 desde z = 0 hasta ~3,2, cono de 30° de semiángulo hasta un fondo plano en z = 5,71 (Ø ~2,3). Chaflán abajo de ~0,47 mm (Ø 6,18 en z=0). Queda bajo los incisivos, rodeado de material. |

Los radios del config son exactamente los de los agujeros (2,118 y 2,618
medidos).

## Placa, piso y texto

- **Placa central** de 2,4 mm (z 0 → 2,4): la lengüeta, de x = −8 a 8,5 e
  y ±8 (16,5 × 16), y un puente bajo los incisivos hasta la pared labial.
- **Dos puentes de 1,0 mm** (`BottomPlaneThickness`) cruzan la arcada, uno
  en cada rama, de ~14,4 mm de ancho a lo largo de la arcada. Llevan el texto
  **calado de lado a lado**.
- **El resto del fondo queda abierto**: cuatro ventanas (dos distales y dos
  laterales anteriores) por las que se ve la cavidad. La pared de 1,8 mm apoya
  en z = 0. **A confirmar** la regla exacta de los bordes de las ventanas
  (son rectas que cruzan la arcada).

### Texto

- **Qué dice**: el caso en la rama +Y («BZ219», «BZ254») y el modelo en la
  rama −Y («L05-A», «U05-A»), legibles desde abajo (vistos desde arriba están
  espejados).
- **Fuente: Verdana Bold**, cuerpo 3,44 mm (mayúsculas de 2,5 mm de alto).
  Comparada contra todas las fuentes a mano: Verdana Bold coincide con
  IoU 0,83 y los centros de cada letra a ±0,12 mm; DejaVu Sans Bold (que viene
  con matplotlib) queda segunda con 0,79.
- **Sin contadores**: la B, el 0, el 9 y la A van rellenos. Como el texto
  atraviesa el puente, el centro de esas letras quedaría suelto.
- **Dónde**: centrado sobre la curva central de la arcada (a 0,04–0,2 mm),
  siguiendo su tangente (±2–5°), al **70 % del largo de su rama** contando
  desde el frente (0,70; 0,71; 0,70; 0,73). Con eso las letras caen con
  IoU 0,79–0,84 si se alinean los centros; el corrimiento a lo largo de la
  curva es de 0,5 a 2 mm (**a confirmar** la regla exacta).

## QR

- **En relieve sobre la placa**: de z 2,4 a 3,2 (0,8 mm). Es un cuadrado de
  15,0 × 15,0 mm (`QrSize`) **centrado en R2**, sin zona de silencio propia:
  la hace la placa de alrededor, que llega a −8.
- **25 × 25 módulos de 0,6 mm.** Es la versión 2, forzada: en versión 1 el
  texto entraba con corrección H.
- **Contenido: `BZ219L05A`**, el nombre del archivo sin guiones.
  Alfanumérico, corrección **H**, **máscara 3**. Coincide módulo a módulo con
  el que genera `segno` con esos parámetros: 0 diferencias fuera del agujero.
- **El agujero R2 le borra 37 módulos del centro**. La corrección H (30%) lo
  absorbe y se lee igual.
- **Orientación**: visto desde arriba está espejado (girado 180° y espejado);
  **se lee derecho desde abajo**. Ver `toothform/qr_BZ219L05A_estandar.png`
  para el código sin agujero.

Para generarlo igual:

```python
segno.make_qr(f"{caso}{modelo}".replace("-", ""), error="h", version=2,
              mode="alphanumeric", mask=3, boost_error=False)
```

En BZ254-U05-A también fue máscara 3 (`BZ254U05A`, 0 diferencias), así que
todo indica que está fija.

**Aristas no-manifold**: las 43 que tiene la salida de ToothFORM están todas en
el QR, donde dos módulos se tocan solo por una esquina. El prototipo agranda
cada módulo 5 µm para que se solapen y la pieza sale cerrada y sin
no-manifold.

## Encía y dientes (`-gum.stl`, `-tooth.ply`)

- **`-gum.stl`**: la encía de la entrada, en el marco de salida, **sin lo que
  queda dentro de algún diente**, cortada en z = 0 y **tapada ahí**. Queda
  abierta solo donde apoyan los dientes. En BZ219-L05-A: de las caras de la
  encía que faltan, 8 266 estaban dentro de un diente y 1 950 debajo del
  corte; la tapa son 1 137 mm². El prototipo da la misma área (2 897,3 mm²) y
  las dos superficies están a 0,002 mm como mucho; solo cambia la
  triangulación.
- **`-tooth.ply`**: PLY ASCII. No hubo muestra para comparar. Según el informe
  (33 344 vértices y 66 636 caras en otro modelo): 2·V − F = 52 = 4 × 13, o
  sea 13 piezas cerradas. El prototipo escribe los dientes tal cual, cerrados,
  en el marco de salida. **A confirmar** con una muestra (encabezado,
  precisión y si están recortados).

## Prototipo

`python -m enkukador CARPETA --producto toothform --salida SALIDA [--config config.json]`
deja `SALIDA/<ID>/<modelo>.stl`, `-gum.stl` y `-tooth.ply`, y un
`<fecha>.<hora>.log` con el mismo formato que ToothFORM. Lee
`ParameterSettings` del mismo `config.json`.

- **Pieza**: unión de todas las piezas, corte en z = 0, hueco cosido
  (`hueco.py`), placa, puentes, macizo alrededor de R1, QR en relieve, y se
  restan R2, R1 con su cono, chaflanes, llave y texto. Una sola malla cerrada.
- **Límites**: `LimitH` (alto) y `LimitR` (radio desde el QR ≤ `LimitR`/2,
  **a confirmar** si es diámetro o radio) cortan con `Height limit exceeded` y
  `Radius limit exceeded`, sin exportar la pieza. El clip no está hecho.
- **Medido contra ToothFORM** con la misma herramienta (`toothform_referencias.py`):
  mismos niveles (0; 1,0; 2,4; 3,2; 5,71; 6,01), agujeros Ø 4,24 y 5,24 en
  (0, 0) y (20, 0), QR con 0 módulos distintos, mismo alto (18,41 y 18,17).
  Volumen 4 % y 2 % menor (el hueco y las ventanas no son idénticos). Giro
  igual a ToothFORM (0,000°); el origen queda a 0,36 y 0,52 mm del suyo.
- ~8–9 s por modelo.

## Lo que falta y qué datos sirven

1. **La regla del origen** (y = 0 y la distancia de R1 a la arcada). Hacen
   falta 20 a 30 pares entrada/salida, con superiores e inferiores, arcadas
   anchas y angostas y alguna asimétrica. Con eso se corre:

   ```bash
   python tools/toothform_referencias.py --pares ENTRADAS/ SALIDAS/ > medidas.jsonl
   ```

   Cada línea trae los candidatos (`candidatos`): el que dé siempre ~0 es el
   criterio.
2. **El plano del agarre del robot**, para confirmar tolerancias, el sentido
   de la llave y si R1 es un centrador cónico.
3. **Una muestra de `-tooth.ply`** de ToothFORM.
4. **Qué mide `LimitR`** (radio o diámetro, desde dónde) y **qué mide el
   clip** (`LimitX`).
5. **Type2 y Type3**.
6. **Qué hace ToothFORM cuando el QR no entra** (`IsAutoCutSupportedQr`,
   `CreateMeshWithOutQR`).

## Herramienta

```bash
python tools/toothform_referencias.py SALIDA.stl --entrada ENTRADA.stl
```

Imprime niveles horizontales, agujeros (centro y diámetro a z = 1,5 y
z = 0,05), el QR (caja, módulos, matriz y contenido) y, con la entrada, la
matriz entrada → salida, el recorte de la base y los candidatos para el
origen.

Para decodificar el QR necesita `zxing-cpp` y para confirmar los parámetros,
`segno`; sin ellos imprime la matriz. No son dependencias del programa:
instalarlos aparte (`pip install zxing-cpp segno`). Tarda ~18 s por par, casi
todo en la registración.
