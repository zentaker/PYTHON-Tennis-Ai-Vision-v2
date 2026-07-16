"use strict";

const state = {
  session: null,
  image: new Image(),
  points: [],
  provisional: null,
  zoom: 1,
  pan: [0, 0],
  mode: "mark",
  spacePressed: false,
  pointerDown: null,
  dragging: false,
  cursor: null,
};
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = response.headers.get("content-type")?.includes("json")
    ? await response.json()
    : null;
  if (!response.ok) throw new Error(payload?.error || `Error ${response.status}`);
  return payload;
}

function scaleAndOrigin() {
  const rect = $("viewport").getBoundingClientRect();
  const scale = Math.min(rect.width / state.session.width, rect.height / state.session.height) * state.zoom;
  return {
    rect,
    scale,
    left: (rect.width - state.session.width * scale) / 2 + state.pan[0],
    top: (rect.height - state.session.height * scale) / 2 + state.pan[1],
  };
}

function imagePoint(event) {
  const { rect, scale, left, top } = scaleAndOrigin();
  return [(event.clientX - rect.left - left) / scale, (event.clientY - rect.top - top) / scale];
}

function drawMarker(ctx, point, left, top, scale, color, label) {
  const x = left + point.pixel[0] * scale;
  const y = top + point.pixel[1] * scale;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.arc(x, y, label === "Punto provisional" ? 15 : 10, 0, Math.PI * 2);
  ctx.stroke();
  ctx.font = "bold 17px sans-serif";
  ctx.fillText(label, x + 16, y - 12);
}

function draw() {
  const canvas = $("canvas");
  const rect = $("viewport").getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(rect.width * dpr));
  canvas.height = Math.max(1, Math.round(rect.height * dpr));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#05080b";
  ctx.fillRect(0, 0, rect.width, rect.height);
  const { scale, left, top } = scaleAndOrigin();
  ctx.drawImage(state.image, left, top, state.session.width * scale, state.session.height * scale);
  state.points.forEach((point, index) => drawMarker(ctx, point, left, top, scale, "#00e5ff", `${index + 1} · ${state.session.labels[point.id]}`));
  if (state.points.length >= 2) drawLine(ctx, state.points[0], state.points[1], left, top, scale, "#ff4d6d");
  if (state.points.length >= 4) drawLine(ctx, state.points[2], state.points[3], left, top, scale, "#ffd166");
  if (state.provisional) drawMarker(ctx, state.provisional, left, top, scale, "#ffd166", "Punto provisional");
  updateLoupe();
}

function drawLine(ctx, first, second, left, top, scale, color) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(left + first.pixel[0] * scale, top + first.pixel[1] * scale);
  ctx.lineTo(left + second.pixel[0] * scale, top + second.pixel[1] * scale);
  ctx.stroke();
}

function updateLoupe() {
  if (!state.cursor) {
    $("loupe").hidden = true;
    return;
  }
  const { rect, scale, left, top } = scaleAndOrigin();
  const localX = state.cursor[0] - rect.left;
  const localY = state.cursor[1] - rect.top;
  $("crosshair").style.left = `${localX}px`;
  $("crosshair").style.top = `${localY}px`;
  const loupe = $("loupe");
  loupe.hidden = false;
  loupe.style.left = `${Math.min(rect.width - 230, Math.max(10, localX + 18))}px`;
  loupe.style.top = `${Math.min(rect.height - 230, Math.max(10, localY + 18))}px`;
  const ctx = loupe.getContext("2d");
  ctx.clearRect(0, 0, 220, 220);
  const imageX = (localX - left) / scale;
  const imageY = (localY - top) / scale;
  const source = 110 / scale;
  ctx.drawImage(state.image, imageX - source / 2, imageY - source / 2, source, source, 0, 0, 220, 220);
  ctx.strokeStyle = "#00e5ff";
  ctx.beginPath();
  ctx.moveTo(110, 0); ctx.lineTo(110, 220); ctx.moveTo(0, 110); ctx.lineTo(220, 110); ctx.stroke();
}

function renderSteps() {
  const panel = $("stepPanel");
  panel.replaceChildren(...state.session.steps.map((step, index) => {
    const item = document.createElement("div");
    item.className = "step-item";
    if (index < state.points.length) item.classList.add("complete");
    if (index === state.points.length && !state.provisional) item.classList.add("current");
    item.innerHTML = `<strong>${index + 1}. ${step.title}</strong><span>${index < state.points.length ? "Completado" : index === state.points.length ? "Actual" : "Pendiente"}</span><small>${step.description}</small>`;
    return item;
  }));
}

function render() {
  const step = Math.min(3, state.points.length);
  $("stepCounter").textContent = `Paso ${state.points.length + 1 > 4 ? 4 : state.points.length + 1} de 4`;
  $("instruction").textContent = state.provisional ? "Revisa la ampliación y confirma o corrige este punto." : state.session.steps[step].instruction;
  $("modeMark").classList.toggle("selected", state.mode === "mark");
  $("modePan").classList.toggle("selected", state.mode === "pan");
  $("viewport").classList.toggle("pan-mode", state.mode === "pan" || state.spacePressed);
  $("confirm").disabled = !state.provisional;
  $("correct").disabled = !state.provisional;
  $("undo").disabled = state.points.length === 0 || Boolean(state.provisional);
  $("confirmation").hidden = state.points.length !== 4 || Boolean(state.provisional);
  $("pointList").replaceChildren(...state.points.map((point) => { const item = document.createElement("div"); item.textContent = state.session.labels[point.id]; return item; }));
  renderSteps();
  draw();
}

function message(text, error = false) {
  $("message").textContent = text;
  $("message").classList.toggle("error", error);
}

$("modeMark").addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); state.mode = "mark"; render(); });
$("modePan").addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); state.mode = "pan"; render(); });
document.querySelectorAll("[data-zoom]").forEach((button) => button.addEventListener("click", (event) => {
  event.preventDefault();
  event.stopPropagation();
  state.zoom = button.dataset.zoom === "fit" ? 1 : Number(button.dataset.zoom);
  state.pan = [0, 0];
  render();
}));

$("viewport").addEventListener("pointermove", (event) => {
  state.cursor = [event.clientX, event.clientY];
  if (state.dragging) {
    state.pan[0] += event.clientX - state.pointerDown.lastX;
    state.pan[1] += event.clientY - state.pointerDown.lastY;
    state.pointerDown.lastX = event.clientX;
    state.pointerDown.lastY = event.clientY;
    draw();
  } else updateLoupe();
});
$("viewport").addEventListener("pointerleave", () => { state.cursor = null; updateLoupe(); });
$("viewport").addEventListener("pointerdown", (event) => {
  event.preventDefault();
  state.pointerDown = { x: event.clientX, y: event.clientY, lastX: event.clientX, lastY: event.clientY };
  state.dragging = false;
  if (state.mode === "pan" || state.spacePressed) $("canvas").setPointerCapture(event.pointerId);
});
$("viewport").addEventListener("pointerup", (event) => {
  event.preventDefault();
  if (!state.pointerDown) return;
  const distance = Math.hypot(event.clientX - state.pointerDown.x, event.clientY - state.pointerDown.y);
  const canPan = state.mode === "pan" || state.spacePressed;
  if (canPan && distance > 4) state.dragging = false;
  if (canPan || distance > 4 || state.provisional || state.points.length >= 4) { state.pointerDown = null; return; }
  const pixel = imagePoint(event);
  state.provisional = { id: state.session.steps[state.points.length].id, pixel };
  $("crosshair").hidden = false;
  message("Punto provisional colocado. Confirma o corrige.");
  state.pointerDown = null;
  render();
});

window.addEventListener("keydown", (event) => { if (event.code === "Space") { event.preventDefault(); state.spacePressed = true; render(); } });
window.addEventListener("keyup", (event) => { if (event.code === "Space") { event.preventDefault(); state.spacePressed = false; render(); } });
window.addEventListener("resize", draw);

$("confirm").addEventListener("click", async (event) => {
  event.preventDefault();
  if (!state.provisional) return;
  try {
    const result = await api("/api/reference", { method: "POST", body: JSON.stringify({ pixel: state.provisional.pixel }) });
    state.points.push(result.point);
    state.provisional = null;
    $("crosshair").hidden = true;
    message(state.points.length < 4 ? `Paso ${state.points.length} completado. Paso ${state.points.length + 1} de 4.` : "Los cuatro puntos están listos para revisión.");
    render();
  } catch (error) { message(error.message, true); }
});
$("correct").addEventListener("click", (event) => { event.preventDefault(); state.provisional = null; $("crosshair").hidden = true; message("Punto provisional eliminado. Repite el mismo paso."); render(); });
$("undo").addEventListener("click", async (event) => { event.preventDefault(); state.session = await api("/api/reference/undo", { method: "POST" }); state.points = state.session.points || []; message("Último punto confirmado deshecho."); render(); });
$("reset").addEventListener("click", async (event) => { event.preventDefault(); if (!window.confirm("¿Reiniciar los cuatro puntos?")) return; state.session = await api("/api/reference/reset", { method: "POST" }); state.points = []; state.provisional = null; message("Puedes empezar de nuevo."); render(); });
$("save").addEventListener("click", async (event) => { event.preventDefault(); try { const result = await api("/api/reference/save", { method: "POST" }); $("savedMessage").hidden = false; $("savedMessage").textContent = result.message || "Las cuatro referencias fueron guardadas correctamente."; $("evaluationMessage").hidden = false; $("evaluationMessage").textContent = result.evaluation_message || result.status; $("diagnostic").hidden = false; $("save").disabled = true; $("diagnostic").onclick = async () => { const report = await api("/api/diagnostic"); message(`Estado: ${report.status}. Fallos: ${(report.failed_criteria || []).join(', ') || 'ninguno'}`); }; } catch (error) { message(error.message, true); } });

(async function init() {
  try {
    state.session = await api("/api/session");
    const test = await api("/api/self-test");
    if (test.status !== "PASS") throw new Error("La herramienta no superó el self-test.");
    state.points = state.session.points || [];
    state.image.onload = () => { $("status").textContent = "Lista. Elige MARCAR PUNTO para comenzar."; render(); };
    state.image.src = state.session.image_url;
  } catch (error) { $("status").textContent = error.message; $("status").classList.add("error"); }
})();
