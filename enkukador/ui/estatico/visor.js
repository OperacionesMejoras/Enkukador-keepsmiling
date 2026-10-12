// Visor 3D mínimo en WebGL, sin librerías. Z hacia arriba, como Rhino.
"use strict";

const M4 = {
  perspectiva(fovy, aspecto, cerca, lejos) {
    const f = 1 / Math.tan(fovy / 2), nf = 1 / (cerca - lejos);
    return [f / aspecto, 0, 0, 0, 0, f, 0, 0, 0, 0, (lejos + cerca) * nf, -1, 0, 0, 2 * lejos * cerca * nf, 0];
  },
  mirar(ojo, centro, arriba) {
    const z = norm(resta(ojo, centro)), x = norm(cruz(arriba, z)), y = cruz(z, x);
    return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0,
      -punto(x, ojo), -punto(y, ojo), -punto(z, ojo), 1];
  },
  por(a, b) {
    const r = new Array(16);
    for (let i = 0; i < 4; i++)
      for (let j = 0; j < 4; j++) {
        let s = 0;
        for (let k = 0; k < 4; k++) s += a[k * 4 + j] * b[i * 4 + k];
        r[i * 4 + j] = s;
      }
    return r;
  },
};
function resta(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function cruz(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function punto(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function norm(a) { const l = Math.hypot(...a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }

const VS_MALLA = `
attribute vec3 p; attribute vec3 n;
uniform mat4 mvp; uniform mat4 vista;
varying vec3 nv;
void main() { nv = mat3(vista) * n; gl_Position = mvp * vec4(p, 1.0); }`;
const FS_MALLA = `
precision mediump float;
varying vec3 nv; uniform vec3 color; uniform float alfa;
void main() {
  vec3 n = normalize(nv);
  if (!gl_FrontFacing) n = -n;
  float luz = 0.25 + 0.6 * max(dot(n, normalize(vec3(0.3, 0.5, 1.0))), 0.0)
            + 0.25 * max(dot(n, normalize(vec3(-0.6, -0.2, 0.4))), 0.0);
  gl_FragColor = vec4(color * luz, alfa);
}`;
const VS_LINEA = `
attribute vec3 p; attribute vec3 c; uniform mat4 mvp; varying vec3 cv;
void main() { cv = c; gl_Position = mvp * vec4(p, 1.0); gl_PointSize = 9.0; }`;
const FS_LINEA = `
precision mediump float; varying vec3 cv;
void main() { gl_FragColor = vec4(cv, 1.0); }`;

class Visor {
  constructor(canvas) {
    this.canvas = canvas;
    const gl = canvas.getContext("webgl", { antialias: true });
    if (!gl) throw new Error("WebGL no disponible");
    this.gl = gl;
    this.progMalla = this._programa(VS_MALLA, FS_MALLA);
    this.progLinea = this._programa(VS_LINEA, FS_LINEA);
    this.malla = null;
    this.lineas = null;
    this.puntos = null;
    this.cam = { centro: [0, 0, 5], dist: 120, azim: -Math.PI / 2, elev: 0.6 };
    this._piso(40);
    this._controles();
    new ResizeObserver(() => this.dibujar()).observe(canvas);
  }

  _programa(vs, fs) {
    const gl = this.gl, p = gl.createProgram();
    for (const [tipo, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
      const s = gl.createShader(tipo);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      gl.attachShader(p, s);
    }
    gl.linkProgram(p);
    return p;
  }

  _buffer(datos) {
    const gl = this.gl, b = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, datos, gl.STATIC_DRAW);
    return b;
  }

  // Grilla del plano z=0 cada 10 mm y ejes X (rojo) e Y (verde).
  _piso(r) {
    const v = [], c = [], gris = [0.32, 0.33, 0.36];
    for (let i = -r; i <= r; i += 10) {
      v.push(i, -r, 0, i, r, 0, -r, i, 0, r, i, 0);
      for (let k = 0; k < 4; k++) c.push(...gris);
    }
    v.push(0, 0, 0, r, 0, 0, 0, 0, 0, 0, r, 0, 0, 0, 0, 0, 0, 15);
    c.push(0.9, 0.3, 0.3, 0.9, 0.3, 0.3, 0.35, 0.8, 0.4, 0.35, 0.8, 0.4, 0.4, 0.55, 0.95, 0.4, 0.55, 0.95);
    this.piso = { pos: this._buffer(new Float32Array(v)), col: this._buffer(new Float32Array(c)), n: v.length / 3 };
  }

  // tri: Float32Array con 9 valores por triángulo. Normales planas.
  // Devuelve un objeto de GPU reutilizable con mostrar(); liberarlo con liberar().
  crearMalla(tri, color = [0.85, 0.82, 0.74]) {
    const n = new Float32Array(tri.length);
    let min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < tri.length; i += 9) {
      const a = [tri[i], tri[i + 1], tri[i + 2]], b = [tri[i + 3], tri[i + 4], tri[i + 5]],
        c = [tri[i + 6], tri[i + 7], tri[i + 8]];
      const nn = norm(cruz(resta(b, a), resta(c, a)));
      for (let k = 0; k < 3; k++) {
        n.set(nn, i + 3 * k);
        for (let e = 0; e < 3; e++) {
          const x = tri[i + 3 * k + e];
          if (x < min[e]) min[e] = x;
          if (x > max[e]) max[e] = x;
        }
      }
    }
    return { pos: this._buffer(tri), nor: this._buffer(n), n: tri.length / 3, color, min, max };
  }

  liberar(m) {
    if (!m) return;
    this.gl.deleteBuffer(m.pos);
    this.gl.deleteBuffer(m.nor);
  }

  // Una malla sola (la anterior se libera si no está en uso por otro lado).
  setMalla(tri, color) {
    if (this._propia) this.liberar(this._propia);
    this._propia = this.crearMalla(tri, color);
    this.mostrar(this._propia);
  }

  // Muestra a, o el fundido de a hacia b con f en [0, 1].
  mostrar(a, b = null, f = 0) {
    this.malla = a;
    this.mallaB = b;
    this.mezcla = b ? Math.min(1, Math.max(0, f)) : 0;
    this.dibujar();
  }

  limpiar() { this.malla = null; this.mallaB = null; this.lineas = null; this.puntos = null; this.dibujar(); }

  // polilineas: [{puntos: [[x,y,z],...], color: [r,g,b]}]; marcas: igual, dibujadas como puntos.
  setExtras(polilineas = [], marcas = []) {
    const pack = (lista, segmentos) => {
      const v = [], c = [];
      for (const { puntos, color } of lista)
        for (let i = 0; i < puntos.length - (segmentos ? 1 : 0); i++) {
          v.push(...puntos[i]); c.push(...color);
          if (segmentos) { v.push(...puntos[i + 1]); c.push(...color); }
        }
      return v.length ? { pos: this._buffer(new Float32Array(v)), col: this._buffer(new Float32Array(c)), n: v.length / 3 } : null;
    };
    this.lineas = pack(polilineas, true);
    this.puntos = pack(marcas, false);
    this.dibujar();
  }

  encuadrar() {
    if (!this.malla) return;
    const { min, max } = this.malla;
    this.cam.centro = [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2];
    this.cam.dist = 1.6 * Math.hypot(max[0] - min[0], max[1] - min[1], max[2] - min[2]);
    this.dibujar();
  }

  _matrices() {
    const { centro, dist, azim, elev } = this.cam;
    const ojo = [centro[0] + dist * Math.cos(elev) * Math.cos(azim),
      centro[1] + dist * Math.cos(elev) * Math.sin(azim), centro[2] + dist * Math.sin(elev)];
    const vista = M4.mirar(ojo, centro, [0, 0, 1]);
    const proy = M4.perspectiva(0.7, this.canvas.width / this.canvas.height, dist / 100, dist * 10);
    return { vista, mvp: M4.por(proy, vista) };
  }

  dibujar() {
    if (this._pendiente) return;
    this._pendiente = requestAnimationFrame(() => { this._pendiente = 0; this._dibujar(); });
  }

  _dibujar() {
    const gl = this.gl, c = this.canvas, dpr = window.devicePixelRatio || 1;
    const w = Math.round(c.clientWidth * dpr), h = Math.round(c.clientHeight * dpr);
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    gl.viewport(0, 0, w, h);
    gl.clearColor(0.118, 0.122, 0.133, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);
    const { vista, mvp } = this._matrices();

    if (this.malla) {
      // Fundido: la malla dominante va sólida y la otra encima, translúcida.
      const f = this.mezcla || 0;
      let [solida, fantasma, alfa] = [this.malla, this.mallaB, f];
      if (fantasma && f > 0.5) [solida, fantasma, alfa] = [this.mallaB, this.malla, 1 - f];
      this._dibujarMalla(solida, 1, mvp, vista);
      if (fantasma && alfa > 0.01) {
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.depthMask(false);
        gl.depthFunc(gl.LEQUAL);
        this._dibujarMalla(fantasma, alfa, mvp, vista, [0.45, 0.7, 1.0]);
        gl.depthMask(true);
        gl.depthFunc(gl.LESS);
        gl.disable(gl.BLEND);
      }
    }
    const p = this.progLinea;
    gl.useProgram(p);
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "mvp"), false, mvp);
    for (const [obj, modo] of [[this.piso, gl.LINES], [this.lineas, gl.LINES], [this.puntos, gl.POINTS]]) {
      if (!obj) continue;
      if (obj !== this.piso) gl.disable(gl.DEPTH_TEST); // curva y plantilla siempre visibles
      this._atributo(p, "p", obj.pos);
      this._atributo(p, "c", obj.col);
      gl.drawArrays(modo, 0, obj.n);
      gl.enable(gl.DEPTH_TEST);
    }
  }

  _dibujarMalla(m, alfa, mvp, vista, color = m.color) {
    const gl = this.gl, p = this.progMalla;
    gl.useProgram(p);
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "mvp"), false, mvp);
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "vista"), false, vista);
    gl.uniform3fv(gl.getUniformLocation(p, "color"), color);
    gl.uniform1f(gl.getUniformLocation(p, "alfa"), alfa);
    this._atributo(p, "p", m.pos);
    this._atributo(p, "n", m.nor);
    gl.drawArrays(gl.TRIANGLES, 0, m.n);
  }

  _atributo(prog, nombre, buffer) {
    const gl = this.gl, loc = gl.getAttribLocation(prog, nombre);
    if (loc < 0) return;
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 3, gl.FLOAT, false, 0, 0);
  }

  _controles() {
    const c = this.canvas;
    let previo = null, mover = false;
    c.addEventListener("contextmenu", (e) => e.preventDefault());
    c.addEventListener("pointerdown", (e) => {
      previo = [e.clientX, e.clientY];
      mover = e.button === 2 || e.button === 1 || e.shiftKey;
      c.setPointerCapture(e.pointerId);
    });
    c.addEventListener("pointerup", () => { previo = null; });
    c.addEventListener("pointermove", (e) => {
      if (!previo) return;
      const dx = e.clientX - previo[0], dy = e.clientY - previo[1];
      previo = [e.clientX, e.clientY];
      const cam = this.cam;
      if (mover) {
        const k = cam.dist / c.clientHeight;
        const der = [-Math.sin(cam.azim), Math.cos(cam.azim), 0];
        const arr = [-Math.sin(cam.elev) * Math.cos(cam.azim), -Math.sin(cam.elev) * Math.sin(cam.azim), Math.cos(cam.elev)];
        for (let i = 0; i < 3; i++) cam.centro[i] += k * (-dx * der[i] + dy * arr[i]);
      } else {
        cam.azim -= dx * 0.008;
        cam.elev = Math.max(-1.55, Math.min(1.55, cam.elev + dy * 0.008));
      }
      this.dibujar();
    });
    c.addEventListener("wheel", (e) => {
      e.preventDefault();
      this.cam.dist *= Math.exp(e.deltaY * 0.001);
      this.dibujar();
    }, { passive: false });
  }
}
