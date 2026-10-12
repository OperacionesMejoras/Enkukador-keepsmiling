// Interfaz: panel de opciones (izquierda), visor (centro), árbol de modelos (derecha).
"use strict";

const $ = (s) => document.querySelector(s);
const visor = new Visor($("#visor"));
const estado = { lote: [], modelos: [], prefijos: {}, elegido: null, vista: "alineado", trabajando: false };
const GRUPOS = [["inf", "Inferiores"], ["sup", "Superiores"], ["bot", "Botones / pasivos"], [null, "Sin tipo"]];

// --- preferencias del navegador (paneles, opciones, última carpeta) ---
const guardado = (() => { try { return JSON.parse(localStorage.getItem("enkukador") || "{}"); } catch { return {}; } })();
function guardar() {
  try {
    localStorage.setItem("enkukador", JSON.stringify({
      explorador: estado.explorador, panel: $("#panel").style.width, arbol: $("#arbol-panel").style.width,
      opciones: Object.fromEntries(["producto", "encuadre", "modo", "tipo", "sufijo", "salida", "espesor"].map((k) => [k, $("#" + k).value])),
      checks: Object.fromEntries(["plantilla", "botones", "vaciar"].map((k) => [k, $("#" + k).checked])),
    }));
  } catch { /* sin almacenamiento: no pasa nada */ }
}
if (guardado.panel) $("#panel").style.width = guardado.panel;
if (guardado.arbol) $("#arbol-panel").style.width = guardado.arbol;
for (const [k, v] of Object.entries(guardado.opciones || {})) $("#" + k).value = v;
for (const [k, v] of Object.entries(guardado.checks || {})) $("#" + k).checked = v;
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

// --- registro ---
function log(texto, clase = "") {
  const d = document.createElement("div");
  d.textContent = texto;
  if (clase) d.className = clase;
  $("#registro").append(d);
  $("#registro").scrollTop = 1e9;
}

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
    $("#titulo-visor").textContent = "Elegí un modelo en el árbol";
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
    const n = document.createElement("span");
    n.textContent = c;
    n.title = c;
    const x = document.createElement("button");
    x.textContent = "×";
    x.title = "Sacar del lote";
    x.onclick = () => quitarCarpeta(c);
    li.append(n, x);
    ul.append(li);
  }
}

$("#vaciar").onclick = () => [...estado.lote].forEach(quitarCarpeta);

// --- diálogo de importar ---
async function explorar(ruta) {
  try {
    const r = await (await api(`/api/explorar?ruta=${encodeURIComponent(ruta || "")}`)).json();
    estado.explorador = r.ruta;
    guardar();
    $("#exp-ruta").value = r.ruta;
    $("#exp-subir").disabled = !r.padre;
    $("#exp-subir").onclick = () => explorar(r.padre);
    $("#exp-info").textContent = r.modelos ? `${r.modelos} modelos en esta carpeta` : "esta carpeta no tiene modelos";
    $("#exp-agregar").disabled = !r.modelos;
    const ul = $("#exp-lista");
    ul.textContent = "";
    for (const c of r.carpetas) {
      const li = document.createElement("li");
      const n = document.createElement("span");
      n.className = "nombre";
      n.textContent = "📁 " + c.nombre;
      li.append(n);
      if (c.modelos) {
        const k = document.createElement("span");
        k.className = "cuenta";
        k.textContent = `${c.modelos} modelos`;
        const mas = document.createElement("button");
        mas.type = "button";
        mas.textContent = "+ agregar";
        mas.onclick = (e) => { e.stopPropagation(); agregarCarpeta(c.ruta); };
        li.append(k, mas);
      }
      li.onclick = () => explorar(c.ruta);
      ul.append(li);
    }
  } catch (e) { log(e.message, "error"); }
}
$("#importar").onclick = () => { $("#explorador").showModal(); explorar(estado.explorador); };
$("#exp-ir").onclick = () => explorar($("#exp-ruta").value.trim());
$("#exp-ruta").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); explorar(e.target.value.trim()); } });
$("#exp-agregar").onclick = () => agregarCarpeta($("#exp-ruta").value.trim());

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
  if (!estado.lote.length) raiz.innerHTML = '<div class="vacio">Importá carpetas con «Importar carpetas…»</div>';
  const ok = estado.modelos.filter((m) => m.estado === "ok" || m.estado === "aviso").length;
  $("#contador").textContent = estado.modelos.length ? `${ok}/${estado.modelos.length}` : "";
}

function hoja(m) {
  const h = document.createElement("div");
  h.className = "hoja" + (estado.elegido === m ? " elegido" : "");
  const chk = document.createElement("input");
  chk.type = "checkbox";
  chk.checked = m.marcado;
  chk.onclick = (e) => { e.stopPropagation(); m.marcado = chk.checked; };
  const p = document.createElement("span");
  p.className = `punto ${m.estado}`;
  p.title = m.estado;
  const n = document.createElement("span");
  n.className = "nombre";
  n.textContent = corto(m);
  n.title = m.ruta;
  h.append(chk, p, n);
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

async function cargarVista() {
  const m = estado.elegido;
  if (!m) return;
  const alineado = m.estado === "ok" || m.estado === "aviso";
  const vista = alineado ? estado.vista : "original";
  document.querySelectorAll("[data-vista]").forEach((b) => {
    b.classList.toggle("activo", b.dataset.vista === vista);
    b.disabled = b.dataset.vista === "alineado" && !alineado;
  });
  $("#titulo-visor").textContent = `${m.nombre} — cargando…`;
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
    $("#titulo-visor").textContent = `${m.nombre} — ${vista === "alineado" ? "alineado" : "original (centrado)"}`;
  } catch (e) {
    $("#titulo-visor").textContent = m.nombre;
    log(`${m.nombre}: ${e.message}`, "error");
  }
}

function mostrarDetalle(m) {
  const d = $("#detalle");
  d.textContent = "";
  const b = document.createElement("b");
  b.textContent = m.nombre;
  d.append(b, `\ntipo: ${m.tipo ?? "?"} · estado: ${m.estado}`);
  if (m.resumen) d.append(`\n\n${m.resumen.replaceAll(" | ", "\n")}`);
  if (m.avisos?.length) d.append(`\n\nAVISOS:\n${m.avisos.join("\n")}`);
  if (m.destino) d.append(`\n\n→ ${m.destino}`);
}

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
    plantilla: $("#plantilla").checked, sufijo: $("#sufijo").value, salida: $("#salida").value.trim(),
  };
  log(`Procesando ${lista.length} modelo(s): ${$("#producto").selectedOptions[0].text}, encuadre ${opciones.encuadre}, modo ${opciones.modo}`);
  const t0 = performance.now();
  let hechos = 0;
  for (const m of lista) {
    m.estado = "trabajando";
    dibujarArbol();
    try {
      const r = await (await api("/api/alinear", { ruta: m.ruta, ...opciones })).json();
      Object.assign(m, { estado: r.estado, resumen: r.resumen, avisos: r.avisos, destino: r.destino, tipo: r.tipo });
      log(`✓ ${m.nombre}`, r.estado === "aviso" ? "aviso" : "ok");
      for (const a of r.avisos) log(`   ${a}`, "aviso");
    } catch (e) {
      m.estado = "error";
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
if (params.get("salida")) $("#salida").value = params.get("salida");
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
