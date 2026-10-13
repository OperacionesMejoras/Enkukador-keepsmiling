# ToothFORM: referencias del robot y QR (ingeniería inversa)

Medido sobre **un solo par**: BZ219-L05-A (entrada del escáner y salida de
ToothFORM release 20260518, Type1, con el `config.json` del informe:
`ShellThickness 1.8`, `BottomPlaneThickness 1.0`, `QrSize 15.0`,
`Radius1 2.62`, `Radius2 2.12`). Lo que depende de un solo caso está marcado
como **a confirmar**.

Herramienta: `tools/toothform_referencias.py` (ver al final).

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
- **Origen** (a confirmar): coincide con el centro del agujero R2. Lo que no
  se pudo deducir con un caso es qué lo ubica respecto de la arcada:
  - y = 0: la media de los centroides de los dientes da −0,12 mm (el mejor
    candidato). El centro del rectángulo mínimo da +4,43, así que no es ese.
  - x: R1 (x = 20) queda 6,98 mm detrás del punto más anterior del corte y
    1,4 mm lingual a la curva central (que cruza el eje en x = 21,40).

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
- **Dos puentes de 1,0 mm** (`BottomPlaneThickness`) cruzan la arcada a la
  altura de premolares y caninos. Llevan el texto **calado de lado a lado**,
  «BZ219» en uno y «L05-A» en el otro, legible desde abajo.
- **El resto del fondo queda abierto**: cuatro ventanas (dos distales y dos
  laterales anteriores) por las que se ve la cavidad. La pared de 1,8 mm apoya
  en z = 0.

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

La máscara 3 puede ser la que eligió el codificador por penalización y no un
valor fijo. **A confirmar** con otros casos (`modulos_distintos` lo dice).

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
3. **Superiores**: ¿la placa va igual, o espejada?
4. **Type2 y Type3**.
5. **Qué hace ToothFORM cuando el QR no entra** (`IsAutoCutSupportedQr`,
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
