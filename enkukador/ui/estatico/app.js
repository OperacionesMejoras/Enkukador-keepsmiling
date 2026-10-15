// Interfaz: panel de opciones (izquierda), visor (centro), árbol de modelos (derecha).
"use strict";

const $ = (s) => document.querySelector(s);
const visor = new Visor($("#visor"));
const estado = { lote: [], modelos: [], prefijos: {}, elegido: null, vista: "alineado", trabajando: false, subcarpetas: {} };
const GRUPOS = [["inf", "Inferiores"], ["sup", "Superiores"], ["bot", "Botones / pasivos"], [null, "Sin tipo"]];

// --- preferencias del navegador (paneles, opciones, última carpeta) ---
const guardado = (() => { try { return JSON.parse(localStorage.getItem("enkukador") || "{}"); } catch { return {}; } })();
function guardar() {
  try {
    localStorage.setItem("enkukador", JSON.stringify({
      explorador: estado.explorador, panel: $("#panel").style.width, arbol: $("#arbol-panel").style.width,
      opciones: Object.fromEntries(["producto", "encuadre", "modo", "tipo", "sufijo", "salida", "espesor", "destino"].map((k) => [k, $("#" + k).value])),
      subcarpetas: estado.subcarpetas, registroPlegado: $("#registro-panel").classList.contains("plegado"),
      avanzado: $("#avanzado").open,
      checks: Object.fromEntries(["plantilla", "botones", "vaciar"].map((k) => [k, $("#" + k).checked])),
    }));
  } catch { /* sin almacenamiento: no pasa nada */ }
}
if (guardado.panel) $("#panel").style.width = guardado.panel;
if (guardado.arbol) $("#arbol-panel").style.width = guardado.arbol;
for (const [k, v] of Object.entries(guardado.opciones || {})) $("#" + k).value = v;
for (const [k, v] of Object.entries(guardado.checks || {})) $("#" + k).checked = v;
estado.subcarpetas = guardado.subcarpetas || {};
if (guardado.avanzado) $("#avanzado").open = true;
$("#avanzado").addEventListener("toggle", () => guardar());
document.querySelectorAll("input, select").forEach((el) => el.addEventListener("change", guardar));

// --- paneles agrandables ---
document.querySelectorAll(".divisor").forEach((div) => {
  div.addEventListener("pointerdown", (e) => {
    const panel = document.getElementById(div.dataset.panel), izq = div.dataset.lado === "izq";
    const x0 = e.clientX, w0 = panel.getBoundingClientRect().width;
    div.classList.add("arrastrando");
    div.setPointerCapture(e.pointerId);
    const mover = (ev) => { panel.style.width = `${w0 + (izq ? 1 : -1) * (ev.clientX - x0)}px`; visor.dibujar(); };
    div.addEventListener("pointermove", mover);
    div.addEventListener("pointerup", () => {
      div.removeEventListener("pointermove", mover);
      div.classList.remove("arrastrando");
      guardar();
    }, { once: true });
  });
});

// --- registro (panel plegable bajo el visor) ---
const cuentas = { error: 0, aviso: 0 };
function log(texto, clase = "") {
  const d = document.createElement("div");
  const h = document.createElement("span");
  h.className = "hora";
  h.textContent = new Date().toLocaleTimeString("es-AR", { hour12: false });
  d.append(h, texto);
  if (clase) d.className = clase;
  if (clase in cuentas) { cuentas[clase]++; dibujarCuentas(); }
  $("#registro").append(d);
  $("#registro").scrollTop = 1e9;
}
function dibujarCuentas() {
  const c = $("#registro-cuentas");
  c.textContent = "";
  for (const [k, txt] of [["error", "error"], ["aviso", "aviso"]]) {
    if (!cuentas[k]) continue;
    const s = document.createElement("span");
    s.className = `insignia ${k}`;
    s.textContent = `${cuentas[k]} ${txt}${cuentas[k] > 1 ? (k === "error" ? "es" : "s") : ""}`;
    c.append(s);
  }
}
$("#limpiar-registro").onclick = () => { $("#registro").textContent = ""; cuentas.error = cuentas.aviso = 0; dibujarCuentas(); };
$("#plegar-registro").onclick = () => { $("#registro-panel").classList.toggle("plegado"); guardar(); };
if (guardado.registroPlegado) $("#registro-panel").classList.add("plegado");

// --- tarjetas y segmentados: botones que manejan un <select> oculto ---
function enlazarOpciones(contenedor) {
  const sel = document.getElementById(contenedor.dataset.select);
  const pintar = () => contenedor.querySelectorAll("[data-valor]").forEach((b) => {
    const si = b.dataset.valor === sel.value;
    b.classList.toggle("activo", si);
    b.setAttribute("aria-checked", si);
  });
  contenedor.querySelectorAll("[data-valor]").forEach((b) => (b.onclick = () => {
    if (sel.value === b.dataset.valor) return;
    sel.value = b.dataset.valor;
    sel.dispatchEvent(new Event("change"));
  }));
  sel.addEventListener("change", pintar);
  pintar();
}
document.querySelectorAll("[data-select]").forEach(enlazarOpciones);

async function api(url, cuerpo) {
  const r = await fetch(url, cuerpo ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) } : {});
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r;
}

// --- lote: carpetas importadas ---
async function agregarCarpeta(ruta) {
  if (estado.lote.includes(ruta)) return log(`Ya está en el lote: ${ruta}`, "aviso");
  try {
    const r = await (await api(`/api/listar?carpeta=${encodeURIComponent(ruta)}&botones=${$("#botones").checked ? 1 : 0}`)).json();
    if (!r.modelos.length) return log(`Sin modelos en ${r.carpeta}`, "aviso");
    estado.lote.push(r.carpeta);
    const ya = new Set(estado.modelos.map((m) => m.ruta));
    for (const m of r.modelos) if (!ya.has(m.ruta)) estado.modelos.push({ ...m, carpeta: r.carpeta, marcado: false });
    log(`+ ${r.modelos.length} modelos de ${r.carpeta}`);
    dibujarLote();
    dibujarArbol();
  } catch (e) { log(e.message, "error"); }
}

function quitarCarpeta(ruta) {
  estado.lote = estado.lote.filter((c) => c !== ruta);
  estado.modelos = estado.modelos.filter((m) => m.carpeta !== ruta);
  if (estado.elegido && estado.elegido.carpeta === ruta) {
    estado.elegido = null;
    visor.limpiar();
    titulo("Elegí un modelo en el árbol");
    $("#detalle").textContent = "";
    prepararEtapas();
  }
  dibujarLote();
  dibujarArbol();
}

function dibujarLote() {
  const ul = $("#lote");
  ul.textContent = "";
  for (const c of estado.lote) {
    const li = document.createElement("li");
    li.title = c;
    const n = document.createElement("div");
    n.className = "carpeta";
    const b = document.createElement("b");
    b.textContent = nombreCarpeta(c);
    const r = document.createElement("small");
    r.textContent = c;
    n.append(b, r);
    const k = document.createElement("span");
    k.className = "cuenta";
    k.textContent = estado.modelos.filter((m) => m.carpeta === c).length;
    k.title = "modelos";
    const x = document.createElement("button");
    x.textContent = "✕";
    x.title = "Sacar del lote";
    x.onclick = () => quitarCarpeta(c);
    li.append(n, k, x);
    ul.append(li);
  }
}

$("#vaciar-lote").onclick = () => [...estado.lote].forEach(quitarCarpeta);

// --- diálogo de importar ---
async function explorar(ruta) {
  try {
    const r = await (await api(`/api/explorar?ruta=${encodeURIComponent(ruta || "")}`)).json();
    estado.explorador = r.ruta;
    guardar();
    $("#exp-ruta").value = r.ruta;
    $("#exp-subir").disabled = !r.padre;
    $("#exp-subir").onclick = () => explorar(r.padre);
    $("#exp-info").textContent = r.modelos ? `${r.modelos} modelo${r.modelos > 1 ? "s" : ""} en esta carpeta` : "Esta carpeta no tiene modelos";
    $("#exp-agregar").disabled = estado.alElegir ? false : !r.modelos;
    const ul = $("#exp-lista");
    ul.textContent = "";
    for (const c of r.carpetas) {
      const li = document.createElement("li");
      const n = document.createElement("span");
      n.className = "nombre";
      n.textContent = "📁 " + c.nombre;
      li.append(n);
      if (c.modelos && !estado.alElegir) {
        const k = document.createElement("span");
        k.className = "cuenta";
        k.textContent = `${c.modelos} modelo${c.modelos > 1 ? "s" : ""}`;
        li.append(k);
        if (estado.lote.includes(c.ruta)) {
          const ya = document.createElement("span");
          ya.className = "ya";
          ya.textContent = "✓ en el lote";
          li.append(ya);
        } else {
          const mas = document.createElement("button");
          mas.type = "button";
          mas.textContent = "+ agregar";
          mas.onclick = async (e) => { e.stopPropagation(); await agregarCarpeta(c.ruta); explorar(r.ruta); };
          li.append(mas);
        }
      }
      li.onclick = () => explorar(c.ruta);
      ul.append(li);
    }
  } catch (e) { log(e.message, "error"); }
}
function abrirExplorador(alElegir, desde) {
  estado.alElegir = alElegir; // null: importar; función: elegir una carpeta
  $("#exp-titulo").textContent = alElegir ? "Elegir la carpeta de salida" : "Importar carpetas";
  $("#exp-agregar").textContent = alElegir ? "Usar esta carpeta" : "Agregar esta carpeta";
  $("#explorador").showModal();
  explorar(desde || estado.explorador);
}
$("#importar").onclick = () => abrirExplorador(null);
$("#explorador").addEventListener("close", () => { const f = estado.alElegir; estado.alElegir = null; f?.(null); });
$("#exp-ir").onclick = () => explorar($("#exp-ruta").value.trim());
$("#exp-ruta").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); explorar(e.target.value.trim()); } });
$("#exp-agregar").onclick = () => {
  const ruta = $("#exp-ruta").value.trim();
  if (!estado.alElegir) return agregarCarpeta(ruta);
  const f = estado.alElegir;
  estado.alElegir = null;
  $("#explorador").close();
  f(ruta);
};

// --- exportar: carpeta elegida o subcarpeta junto a cada caso ---
const SUBCARPETA = { alineado: "planos", cnc2: "MODELOS KUKA", cnc3: "MODELOS KUKA", toothform: "toothform" };
const subcarpeta = (producto) => estado.subcarpetas[producto] || SUBCARPETA[producto];
function mostrarDestino() {
  const caso = $("#destino").value === "caso";
  $("#fila-salida").hidden = caso;
  $("#fila-subcarpeta").hidden = !caso;
  $("#subcarpeta").value = subcarpeta($("#producto").value);
}
$("#destino").addEventListener("change", mostrarDestino);
$("#producto").addEventListener("change", mostrarDestino);
$("#subcarpeta").addEventListener("change", (e) => {
  const v = e.target.value.trim();
  if (v && v !== SUBCARPETA[$("#producto").value]) estado.subcarpetas[$("#producto").value] = v;
  else delete estado.subcarpetas[$("#producto").value];
  mostrarDestino();
  guardar();
});
const elegirSalida = () => new Promise((listo) => abrirExplorador((ruta) => {
  if (ruta) { $("#salida").value = ruta; guardar(); }
  listo(ruta);
}, $("#salida").value.trim() || estado.explorador));
$("#elegir-salida").onclick = elegirSalida;
mostrarDestino();

async function exportarLista() {
  if (estado.trabajando) return;
  const hechos = estado.modelos.filter(alineado);
  const marcados = hechos.filter((m) => m.marcado);
  const lista = marcados.length ? marcados : hechos;
  if (!lista.length) return log("No hay modelos alineados para exportar", "aviso");
  const opciones = { salida: "", subcarpeta: "" };
  if ($("#destino").value === "carpeta") {
    if (!$("#salida").value.trim() && !(await elegirSalida())) return log("Exportar: no se eligió carpeta", "aviso");
    opciones.salida = $("#salida").value.trim();
  }
  estado.trabajando = true;
  document.querySelectorAll(".acciones button").forEach((b) => (b.disabled = true));
  let ok = 0;
  for (const m of lista) {
    try {
      const r = await (await api("/api/exportar", {
        ruta: m.ruta, ...opciones, subcarpeta: opciones.salida ? "" : subcarpeta(m.producto || $("#producto").value),
      })).json();
      m.exportado = r.destino;
      ok++;
      log(`↓ ${r.destino}`, "ok");
    } catch (e) { log(`✗ exportar ${m.nombre}: ${e.message}`, "error"); }
    if (estado.elegido === m) mostrarDetalle(m);
  }
  dibujarArbol();
  log(`Exportados: ${ok}/${lista.length}`);
  estado.trabajando = false;
  document.querySelectorAll(".acciones button").forEach((b) => (b.disabled = false));
}
$("#exportar").onclick = exportarLista;

// --- árbol: caso (carpeta) > inferiores / superiores > etapas ---
// Prefijo común de los nombres (caso y paciente), para mostrar solo lo que cambia.
function prefijoComun(nombres) {
  if (nombres.length < 2) return "";
  let p = nombres[0];
  for (const n of nombres) while (!n.startsWith(p)) p = p.slice(0, -1);
  return p.slice(0, p.lastIndexOf(" ") + 1); // cortar en un espacio
}

// Nombre para mostrar de una carpeta: las dos últimas partes ("Caso stl / Backup originales").
const nombreCarpeta = (c) => c.split("/").filter(Boolean).slice(-2).join(" / ");

function grupo(titulo, clase) {
  const g = document.createElement("div");
  g.className = "grupo " + clase;
  const cab = document.createElement("div");
  cab.className = "cabecera";
  cab.textContent = titulo;
  cab.onclick = () => g.classList.toggle("cerrado");
  const hijos = document.createElement("div");
  hijos.className = "hijos";
  g.append(cab, hijos);
  return [g, hijos];
}

function dibujarArbol() {
  const raiz = $("#arbol");
  raiz.textContent = "";
  for (const c of estado.lote) {
    const delCaso = estado.modelos.filter((m) => m.carpeta === c);
    estado.prefijos[c] = prefijoComun(delCaso.map((m) => m.nombre));
    const [gc, hc] = grupo(`${nombreCarpeta(c)} (${delCaso.length})`, "caso");
    gc.title = c;
    for (const [tipo, titulo] of GRUPOS) {
      const lista = delCaso.filter((m) => m.tipo === tipo);
      if (!lista.length) continue;
      const [g, h] = grupo(`${titulo} (${lista.length})`, "tipo");
      for (const m of lista) h.append(hoja(m));
      hc.append(g);
    }
    raiz.append(gc);
  }
  if (!estado.lote.length) raiz.innerHTML = '<div class="vacio"><b>Sin modelos</b>Importá carpetas con «Importar carpetas…»</div>';
  const ok = estado.modelos.filter((m) => m.estado === "ok" || m.estado === "aviso").length;
  $("#contador").textContent = estado.modelos.length ? `${ok}/${estado.modelos.length} alineados` : "";
  const ley = $("#leyenda");
  ley.textContent = "";
  for (const k of ["ok", "aviso", "error"]) {
    const n = estado.modelos.filter((m) => m.estado === k).length;
    if (!n) continue;
    const s = document.createElement("span");
    const p = document.createElement("i");
    p.className = `punto ${k}`;
    s.title = k;
    s.append(p, n);
    ley.append(s);
  }
  actualizarMarcados();
}

function actualizarMarcados() {
  const n = estado.modelos.filter((m) => m.marcado).length;
  $("#marcados").textContent = n ? `${n} marcado${n > 1 ? "s" : ""}` : "";
  $("#todos").checked = n > 0 && n === estado.modelos.length;
  $("#todos").indeterminate = n > 0 && n < estado.modelos.length;
  $("#alinear-sel").textContent = n ? `Alinear marcados (${n})` : estado.elegido ? "Alinear el elegido" : "Alinear seleccionados";
}

function hoja(m) {
  const h = document.createElement("div");
  h.className = "hoja" + (estado.elegido === m ? " elegido" : "");
  const chk = document.createElement("input");
  chk.type = "checkbox";
  chk.checked = m.marcado;
  chk.onclick = (e) => { e.stopPropagation(); m.marcado = chk.checked; actualizarMarcados(); };
  const p = document.createElement("span");
  p.className = `punto ${m.estado}`;
  p.title = m.estado;
  const n = document.createElement("span");
  n.className = "nombre";
  n.textContent = corto(m);
  n.title = m.ruta;
  h.append(chk, p, n);
  h.title = m.ruta;
  if (m.exportado) {
    const x = document.createElement("span");
    x.className = "exportado";
    x.textContent = "↓";
    x.title = `exportado: ${m.exportado}`;
    h.append(x);
  }
  h.onclick = () => elegir(m);
  return h;
}

$("#todos").onchange = (e) => { estado.modelos.forEach((m) => (m.marcado = e.target.checked)); dibujarArbol(); };

// --- visor ---
async function elegir(m) {
  estado.elegido = m;
  dibujarArbol();
  mostrarDetalle(m);
  await cargarVista();
  prepararEtapas();
}

// --- etapas: recorrer el maxilar alineado con un fundido entre movimientos ---
const etapas = { lista: [], cache: new Map(), pedidos: new Map(), reproduciendo: 0 };
const alineado = (m) => m.estado === "ok" || m.estado === "aviso";
const corto = (m) => m.nombre.slice((estado.prefijos[m.carpeta] || "").length).replace(/\.[^.]+$/, "");

function prepararEtapas() {
  parar();
  const m = estado.elegido, barra = $("#etapas");
  etapas.lista = m ? estado.modelos.filter((x) => x.carpeta === m.carpeta && x.tipo === m.tipo && alineado(x)) : [];
  if (!m || !alineado(m) || estado.vista !== "alineado" || etapas.lista.length < 2) {
    barra.hidden = true;
    return;
  }
  barra.hidden = false;
  const s = $("#slider-etapa");
  s.max = etapas.lista.length - 1;
  s.value = etapas.lista.indexOf(m);
  etiquetarEtapa(+s.value);
}

function etiquetarEtapa(v) {
  const i = Math.floor(v), f = v - i, L = etapas.lista;
  $("#etiqueta-etapa").textContent = f < 0.01 || i + 1 >= L.length
    ? corto(L[Math.round(v)])
    : `${corto(L[i])} → ${corto(L[i + 1])} ${Math.round(f * 100)}%`;
}

// Malla alineada de un modelo, cacheada en la GPU (se guardan las últimas 8).
async function mallaEtapa(m) {
  if (etapas.cache.has(m.ruta)) return etapas.cache.get(m.ruta);
  if (!etapas.pedidos.has(m.ruta)) {
    etapas.pedidos.set(m.ruta, api(`/api/malla?ruta=${encodeURIComponent(m.ruta)}&vista=alineado`)
      .then((r) => r.arrayBuffer())
      .then((buf) => {
        const obj = visor.crearMalla(new Float32Array(buf));
        etapas.cache.set(m.ruta, obj);
        etapas.pedidos.delete(m.ruta);
        while (etapas.cache.size > 8) {
          const [k, viejo] = etapas.cache.entries().next().value;
          if (viejo === visor.malla || viejo === visor.mallaB) break;
          etapas.cache.delete(k);
          visor.liberar(viejo);
        }
        return obj;
      }));
  }
  return etapas.pedidos.get(m.ruta);
}

let turno = 0;
async function mostrarEtapa(v) {
  const L = etapas.lista, i = Math.min(Math.floor(v), L.length - 1), f = v - i;
  const yo = ++turno;
  etiquetarEtapa(v);
  const a = await mallaEtapa(L[i]);
  const b = f > 0.01 && L[i + 1] ? await mallaEtapa(L[i + 1]) : null;
  if (yo !== turno) return; // el slider ya se movió
  visor.mostrar(a, b, f);
  // precargar la siguiente para que el fundido no espere
  if (L[i + 2]) mallaEtapa(L[i + 2]);
}

$("#slider-etapa").addEventListener("input", (e) => mostrarEtapa(+e.target.value));

$("#reproducir").onclick = () => {
  if (etapas.reproduciendo) return parar();
  const s = $("#slider-etapa");
  if (+s.value >= +s.max) s.value = 0;
  $("#reproducir").textContent = "⏸";
  let previo = performance.now();
  const paso = (t) => {
    const v = Math.min(+s.max, +s.value + (t - previo) / 900); // ~0,9 s por etapa
    previo = t;
    s.value = v;
    mostrarEtapa(v);
    if (v >= +s.max) return parar();
    etapas.reproduciendo = requestAnimationFrame(paso);
  };
  etapas.reproduciendo = requestAnimationFrame(paso);
};
function parar() {
  cancelAnimationFrame(etapas.reproduciendo);
  etapas.reproduciendo = 0;
  $("#reproducir").textContent = "▶";
}

const ESTADOS = { ok: "alineado", aviso: "con avisos", error: "error", pendiente: "pendiente", trabajando: "procesando…" };
function titulo(texto, m = null) {
  $("#titulo-texto").textContent = texto;
  const i = $("#titulo-insignia");
  i.textContent = "";
  if (!m) return;
  const s = document.createElement("span");
  s.className = `insignia ${m.estado}`;
  s.textContent = ESTADOS[m.estado] || m.estado;
  i.append(s);
}

async function cargarVista() {
  const m = estado.elegido;
  if (!m) return;
  const alineado = m.estado === "ok" || m.estado === "aviso";
  const vista = alineado ? estado.vista : "original";
  document.querySelectorAll("[data-vista]").forEach((b) => {
    b.classList.toggle("activo", b.dataset.vista === vista);
    b.disabled = b.dataset.vista === "alineado" && !alineado;
  });
  titulo(`${m.nombre} — cargando…`, m);
  try {
    const buf = await (await api(`/api/malla?ruta=${encodeURIComponent(m.ruta)}&vista=${vista}`)).arrayBuffer();
    if (estado.elegido !== m) return; // eligieron otro mientras cargaba
    visor.setMalla(new Float32Array(buf), vista === "alineado" ? [0.85, 0.82, 0.74] : [0.62, 0.7, 0.82]);
    if (vista === "alineado") {
      const ex = await (await api(`/api/extras?ruta=${encodeURIComponent(m.ruta)}`)).json();
      const lineas = ex.curva ? [{ puntos: ex.curva.map(([x, y]) => [x, y, 0.5]), color: [0.95, 0.45, 0.25] }] : [];
      const marcas = ex.plantilla ? [{ puntos: ex.plantilla.map(([x, y]) => [x, y, 0.5]), color: [0.3, 0.9, 0.5] }] : [];
      visor.setExtras(lineas, marcas);
    } else {
      visor.setExtras();
    }
    visor.encuadrar();
    titulo(`${m.nombre} · ${vista === "alineado" ? (m.producto && m.producto !== "alineado" ? $(`#producto option[value=${m.producto}]`).text : "alineado") : "original"}`, m);
  } catch (e) {
    titulo(m.nombre, m);
    log(`${m.nombre}: ${e.message}`, "error");
  }
}

const TIPOS = { inf: "Inferior", sup: "Superior", bot: "Botones / pasivos" };
function mostrarDetalle(m) {
  const d = $("#detalle");
  d.textContent = "";
  const h = document.createElement("h3");
  h.textContent = m.nombre;
  h.title = m.ruta;
  const ins = document.createElement("div");
  ins.className = "insignias";
  for (const [clase, texto] of [[m.estado, ESTADOS[m.estado] || m.estado], ["", TIPOS[m.tipo] || "tipo ?"]]) {
    const s = document.createElement("span");
    s.className = `insignia ${clase}`;
    s.textContent = texto;
    ins.append(s);
  }
  d.append(h, ins);
  if (m.estado === "error" && m.error) {
    const c = document.createElement("div");
    c.className = "caja error";
    c.textContent = m.error;
    d.append(c);
  }
  if (m.resumen && m.estado !== "error") {
    const dl = document.createElement("dl");
    for (const parte of m.resumen.split(" | ")) {
      const k = parte.match(/^([^:]{1,24}?):\s*(.*)$/);
      const dd = document.createElement("dd");
      if (k) {
        const dt = document.createElement("dt");
        dt.textContent = k[1];
        dd.textContent = k[2];
        dl.append(dt, dd);
      } else {
        dd.className = "entero";
        dd.textContent = parte;
        dl.append(dd);
      }
    }
    d.append(dl);
  }
  if (m.avisos?.length && m.estado !== "error") {
    const c = document.createElement("div");
    c.className = "caja aviso";
    for (const a of m.avisos) { const p = document.createElement("p"); p.textContent = a; c.append(p); }
    d.append(c);
  }
  if (alineado(m)) {
    const x = document.createElement("div");
    x.className = "exportado" + (m.exportado ? " si" : "");
    x.textContent = m.exportado ? `↓ exportado en ${m.exportado}` : "Sin exportar todavía";
    d.append(x);
  }
  const e = editorIdent(m);
  if (e) d.append(e);
}

// --- lo que se graba en la pieza (ID del QR en ToothFORM, chapa en CNC2) ---
// Sale del nombre del archivo; se ve antes de alinear y se puede corregir.
const IDENT = {
  toothform: { titulo: "ID para ToothFORM", campos: ["caso", "modelo"] },
  cnc2: { titulo: "Chapa CNC2", campos: ["ID", "movimiento"] },
};
const textoQr = (par) => (par[0] + par[1]).replaceAll("-", "").toUpperCase();
const qrValido = (par) => /^[0-9A-Z $%*+\-./:]{1,16}$/.test(textoQr(par));
const identDe = (m, producto) => m.identEditado?.[producto] || m.ident?.[producto];

function problemaIdent(m, producto) {
  const par = identDe(m, producto);
  if (!IDENT[producto] || !par) return null;
  if (!par[0].trim() || !par[1].trim()) return "falta el ID";
  if (producto === "toothform" && !qrValido(par))
    return `el QR «${textoQr(par)}» no es válido: hasta 16 caracteres, solo letras, números, espacio y .-$%*+/:`;
  return null;
}

function editorIdent(m) {
  const producto = $("#producto").value, conf = IDENT[producto], par = identDe(m, producto);
  if (!conf || !par) return null;
  const caja = document.createElement("div");
  caja.className = "ident";
  const t = document.createElement("div");
  t.className = "titulo";
  t.textContent = conf.titulo;
  const nota = document.createElement("div");
  const actualizar = () => {
    const p = identDe(m, producto), mal = problemaIdent(m, producto);
    nota.className = "nota-ident" + (mal ? " error" : "");
    nota.textContent = mal || (producto === "toothform"
      ? `QR: ${textoQr(p)} · texto: ${p[0]} / ${p[1]}`
      : `chapa: ${p[0]} · movimiento: ${p[1]}`);
  };
  const entradas = conf.campos.map((nombre, i) => {
    const l = document.createElement("label");
    const inp = document.createElement("input");
    inp.type = "text";
    inp.spellcheck = false;
    inp.value = par[i];
    inp.oninput = () => {
      const nuevo = [...identDe(m, producto)];
      nuevo[i] = inp.value.trim();
      (m.identEditado ||= {})[producto] = nuevo;
      actualizar();
    };
    l.append(nombre, inp);
    return l;
  });
  const volver = document.createElement("button");
  volver.type = "button";
  volver.className = "chico";
  volver.textContent = "Del nombre";
  volver.title = "Volver a lo que sale del nombre del archivo";
  volver.onclick = () => { if (m.identEditado) delete m.identEditado[producto]; mostrarDetalle(m); };
  t.append(volver);
  const campos = document.createElement("div");
  campos.className = "campos";
  campos.append(...entradas);
  caja.append(t, campos, nota);
  actualizar();
  return caja;
}
$("#producto").addEventListener("change", () => estado.elegido && mostrarDetalle(estado.elegido));

document.querySelectorAll("[data-vista]").forEach((b) =>
  b.addEventListener("click", async () => { estado.vista = b.dataset.vista; await cargarVista(); prepararEtapas(); }));
$("#encuadrar").onclick = () => visor.encuadrar();
document.addEventListener("keydown", (e) => {
  if (e.key.toLowerCase() === "f" && !["INPUT", "SELECT"].includes(document.activeElement.tagName)) visor.encuadrar();
});

// --- alinear (de a un modelo, para ver el avance) ---
async function alinearLista(lista) {
  if (estado.trabajando || !lista.length) return;
  estado.trabajando = true;
  document.querySelectorAll(".acciones button").forEach((b) => (b.disabled = true));
  const barra = $("#progreso > div");
  const opciones = {
    producto: $("#producto").value, vaciado: $("#vaciar").checked ? +$("#espesor").value : 0, encuadre: $("#encuadre").value, modo: $("#modo").value, tipo: $("#tipo").value, botones: $("#botones").checked,
    plantilla: $("#plantilla").checked, sufijo: $("#sufijo").value,
  };
  log(`Procesando ${lista.length} modelo(s): ${$("#producto").selectedOptions[0].text}, encuadre ${opciones.encuadre}, modo ${opciones.modo}`);
  const t0 = performance.now();
  let hechos = 0;
  for (const m of lista) {
    const mal = problemaIdent(m, opciones.producto);
    if (mal) {
      Object.assign(m, { estado: "error", error: `${mal} (corregilo abajo)`, resumen: null, avisos: [] });
      log(`✗ ${m.nombre}: ${mal} (corregilo en el detalle)`, "error");
      barra.style.width = `${(100 * ++hechos) / lista.length}%`;
      dibujarArbol();
      continue;
    }
    m.estado = "trabajando";
    dibujarArbol();
    try {
      const r = await (await api("/api/alinear", { ruta: m.ruta, ident: identDe(m, opciones.producto), ...opciones })).json();
      Object.assign(m, { estado: r.estado, resumen: r.resumen, avisos: r.avisos, tipo: r.tipo, producto: opciones.producto, exportado: null, error: null });
      log(`✓ ${m.nombre}`, r.estado === "aviso" ? "aviso" : "ok");
      for (const a of r.avisos) log(`   ${a}`, "aviso");
    } catch (e) {
      Object.assign(m, { estado: "error", error: e.message, resumen: null, avisos: [] });
      log(`✗ ${m.nombre}: ${e.message}`, "error");
    }
    barra.style.width = `${(100 * ++hechos) / lista.length}%`;
    dibujarArbol();
    if (estado.elegido === m) { mostrarDetalle(m); cargarVista(); }
  }
  prepararEtapas();
  log(`Listo: ${lista.filter((m) => m.estado !== "error").length}/${lista.length} en ${((performance.now() - t0) / 1000).toFixed(1)} s`);
  estado.trabajando = false;
  document.querySelectorAll(".acciones button").forEach((b) => (b.disabled = false));
}

$("#alinear-todos").onclick = () => alinearLista(estado.modelos);
$("#alinear-sel").onclick = () => {
  const sel = estado.modelos.filter((m) => m.marcado);
  if (!sel.length && estado.elegido) sel.push(estado.elegido);
  if (!sel.length) return log("Marcá modelos en el árbol (o elegí uno)", "aviso");
  alinearLista(sel);
};

// arranque: sin carpetas precargadas; el lanzador puede pasar ?carpeta= y ?salida=
estado.explorador = guardado.explorador;
dibujarArbol();
const params = new URLSearchParams(location.search);
if (params.get("salida")) { $("#salida").value = params.get("salida"); $("#destino").value = "carpeta"; mostrarDestino(); }
if (params.get("carpeta")) {
  agregarCarpeta(params.get("carpeta")).then(() => {
    const m = estado.modelos.find((x) => x.nombre === params.get("modelo"));
    if (m) elegir(m).then(() => {
      if (params.get("etapa") && !$("#etapas").hidden) {
        $("#slider-etapa").value = params.get("etapa");
        mostrarEtapa(+params.get("etapa"));
      }
    });
  });
}

// --- versión, latido y actualizaciones ---
api("/api/version").then((r) => r.json()).then((v) => ($("#version").textContent = `v${v.version}`)).catch(() => {});
// Mientras la pestaña está abierta el servidor no se apaga solo.
setInterval(() => fetch("/api/latido").catch(() => {}), 30000);
fetch("/api/latido").catch(() => {});

async function verActualizaciones() {
  $("#actualizador").showModal();
  $("#act-estado").textContent = "Consultando GitHub…";
  $("#act-lista").textContent = "";
  try {
    const e = await (await api("/api/actualizacion?buscar=1")).json();
    const actual = e.tag || `v${e.version}`;
    $("#act-estado").textContent = e.error
      ? e.error
      : `Versión instalada: ${actual}${e.instalada ? "" : " (copia de desarrollo: se actualiza con git)"}`;
    $("#act-revertir").disabled = !e.anterior;
    $("#act-revertir").title = e.anterior ? `Volver a ${e.anterior}` : "No hay una versión anterior guardada";
    for (const r of e.releases || []) {
      const li = document.createElement("li");
      const t = document.createElement("span");
      t.className = "titulo";
      t.textContent = r.titulo + (r.prerelease ? " (prueba)" : "");
      t.title = r.notas;
      const f = document.createElement("span");
      f.className = "fecha";
      f.textContent = r.fecha;
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = r.tag === actual ? "Instalada" : "Instalar";
      b.disabled = r.tag === actual || !e.instalada;
      b.onclick = () => instalarVersion(r.tag);
      li.append(t, f, b);
      $("#act-lista").append(li);
    }
  } catch (err) { $("#act-estado").textContent = err.message; }
}

async function instalarVersion(tag) {
  $("#act-estado").textContent = `Instalando ${tag}… el programa se reinicia solo.`;
  try {
    await api("/api/actualizacion/instalar", { tag });
    esperarReinicio();
  } catch (e) { $("#act-estado").textContent = e.message; }
}

function esperarReinicio() {
  const t = setInterval(async () => {
    try { await api("/api/version"); clearInterval(t); location.reload(); } catch { /* todavía no */ }
  }, 1500);
}

$("#abrir-actualizar").onclick = verActualizaciones;
$("#act-revertir").onclick = async () => {
  $("#act-estado").textContent = "Volviendo a la versión anterior…";
  try { await api("/api/actualizacion/revertir", {}); esperarReinicio(); }
  catch (e) { $("#act-estado").textContent = e.message; }
};
