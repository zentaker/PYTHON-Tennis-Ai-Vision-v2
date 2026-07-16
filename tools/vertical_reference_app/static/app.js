"use strict";

const state = { session: null, image: new Image(), points: [], zoom: 1, pan: [0, 0], dragging: false, dragStart: null, cursor: null };
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  const payload = response.headers.get("content-type")?.includes("json") ? await response.json() : null;
  if (!response.ok) throw new Error(payload?.error || `Error ${response.status}`);
  return payload;
}

function scaleAndOrigin() {
  const rect = $("viewport").getBoundingClientRect();
  const scale = Math.min(rect.width / state.session.width, rect.height / state.session.height) * state.zoom;
  return { rect, scale, left: (rect.width - state.session.width * scale) / 2 + state.pan[0], top: (rect.height - state.session.height * scale) / 2 + state.pan[1] };
}

function imagePoint(event) {
  const { rect, scale, left, top } = scaleAndOrigin();
  return [(event.clientX - rect.left - left) / scale, (event.clientY - rect.top - top) / scale];
}

function draw() {
  const canvas = $("canvas"); const rect = $("viewport").getBoundingClientRect(); const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(rect.width * dpr)); canvas.height = Math.max(1, Math.round(rect.height * dpr));
  const ctx = canvas.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.fillStyle = "#05080b"; ctx.fillRect(0, 0, rect.width, rect.height);
  const { scale, left, top } = scaleAndOrigin(); ctx.drawImage(state.image, left, top, state.session.width * scale, state.session.height * scale);
  state.points.forEach((point, index) => { const x = left + point.pixel[0] * scale; const y = top + point.pixel[1] * scale; ctx.strokeStyle = "#00e5ff"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2); ctx.stroke(); ctx.fillStyle = "#00e5ff"; ctx.font = "bold 16px sans-serif"; ctx.fillText(String(index + 1), x + 12, y - 10); });
  if (state.points.length >= 2) line(ctx, state.points[0], state.points[1], left, top, scale, "#ff4d6d");
  if (state.points.length >= 4) line(ctx, state.points[2], state.points[3], left, top, scale, "#ffd166");
  updateLoupe();
}

function line(ctx, a, b, left, top, scale, color) { ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(left + a.pixel[0] * scale, top + a.pixel[1] * scale); ctx.lineTo(left + b.pixel[0] * scale, top + b.pixel[1] * scale); ctx.stroke(); }

function updateLoupe() {
  if (!state.cursor) { $("loupe").hidden = true; return; }
  const { rect, scale, left, top } = scaleAndOrigin(); const localX = state.cursor[0] - rect.left; const localY = state.cursor[1] - rect.top;
  const loupe = $("loupe"); loupe.hidden = false; loupe.style.left = `${Math.min(rect.width - 230, Math.max(10, localX + 18))}px`; loupe.style.top = `${Math.min(rect.height - 230, Math.max(10, localY + 18))}px`;
  const ctx = loupe.getContext("2d"); ctx.clearRect(0, 0, 220, 220); const imageX = (localX - left) / scale; const imageY = (localY - top) / scale; const source = 110 / scale; ctx.drawImage(state.image, imageX - source / 2, imageY - source / 2, source, source, 0, 0, 220, 220); ctx.strokeStyle = "#00e5ff"; ctx.beginPath(); ctx.moveTo(110, 0); ctx.lineTo(110, 220); ctx.moveTo(0, 110); ctx.lineTo(220, 110); ctx.stroke();
}

function render() { $("stepCounter").textContent = `Paso ${Math.min(4, state.points.length + 1)} de 4`; $("instruction").textContent = state.session.instructions[Math.min(3, state.points.length)] || "Revisa las cuatro referencias."; $("confirmation").hidden = state.points.length !== 4; $("pointList").replaceChildren(...state.points.map((point) => { const item = document.createElement("div"); item.textContent = state.session.labels[point.id]; return item; })); draw(); }
function message(text, error = false) { $("message").textContent = text; $("message").classList.toggle("error", error); }

$("viewport").addEventListener("pointermove", (event) => { state.cursor = [event.clientX, event.clientY]; if (state.dragging) { state.pan[0] += event.clientX - state.dragStart[0]; state.pan[1] += event.clientY - state.dragStart[1]; state.dragStart = [event.clientX, event.clientY]; draw(); } else updateLoupe(); });
$("viewport").addEventListener("pointerleave", () => { state.cursor = null; updateLoupe(); });
$("viewport").addEventListener("pointerdown", (event) => { if (state.zoom > 1) { state.dragging = true; state.dragStart = [event.clientX, event.clientY]; $("canvas").setPointerCapture(event.pointerId); } });
$("viewport").addEventListener("pointerup", async (event) => { if (state.dragging) { state.dragging = false; return; } if (state.points.length >= 4) return; const pixel = imagePoint(event); try { const result = await api("/api/reference", { method: "POST", body: JSON.stringify({ pixel }) }); state.points.push(result.point); message(result.post_message || "Punto guardado."); render(); } catch (error) { message(error.message, true); } });
window.addEventListener("resize", draw);
document.querySelectorAll("[data-zoom]").forEach((button) => button.addEventListener("click", () => { state.zoom = button.dataset.zoom === "fit" ? 1 : Number(button.dataset.zoom); state.pan = [0, 0]; draw(); }));
$("undo").addEventListener("click", async () => { state.session = await api("/api/reference/undo", { method: "POST" }); state.points = state.session.points || []; render(); message("Último punto deshecho."); });
$("reset").addEventListener("click", async () => { state.session = await api("/api/reference/reset", { method: "POST" }); state.points = []; render(); message("Puedes empezar de nuevo."); });
$("correct").addEventListener("click", async () => { state.session = await api("/api/reference/reset", { method: "POST" }); state.points = []; render(); message("Marca nuevamente las referencias."); });
$("save").addEventListener("click", async () => { try { const result = await api("/api/reference/save", { method: "POST" }); message(`Referencias guardadas. Estado: ${result.readiness}`); $("save").disabled = true; } catch (error) { message(error.message, true); } });

(async function init() { try { state.session = await api("/api/session"); const test = await api("/api/self-test"); if (test.status !== "PASS") throw new Error("La herramienta no superó el self-test."); state.points = state.session.points || []; state.image.onload = () => { $("status").textContent = "Lista. Solo se guardarán cuatro clics humanos."; render(); }; state.image.src = state.session.image_url; } catch (error) { $("status").textContent = error.message; $("status").classList.add("error"); } })();
