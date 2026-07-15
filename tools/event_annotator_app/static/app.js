"use strict";

const state = {
  session: null,
  current: 0,
  metadata: null,
  loading: false,
  playing: false,
  playTimer: null,
  selectionStart: null,
  selectionEnd: null,
  events: [],
  zoom: 1,
};

const $ = (id) => document.getElementById(id);
const annotationControls = () => document.querySelectorAll("[data-preset], #markStart, #markEnd, #clearSelection, #undoButton, #exportButton");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = response.headers.get("content-type")?.includes("json") ? await response.json() : null;
  if (!response.ok) throw new Error(payload?.error || `Error ${response.status}`);
  return payload;
}

function formatTimestamp(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const whole = Math.floor(seconds % 60);
  const micros = Math.round((seconds - Math.floor(seconds)) * 1_000_000);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(whole).padStart(2, "0")}.${String(micros).padStart(6, "0")}`;
}

function frameUrl(frameId) { return `/api/frames/${frameId}`; }
function metadataUrl(frameId) { return `/api/frames/${frameId}/metadata`; }
function clamp(frameId) { return Math.max(0, Math.min(state.session.last_frame_id, frameId)); }

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`No se pudo cargar ${url}`));
    image.src = url;
  });
}

async function navigate(frameId) {
  if (state.loading || !state.session) return false;
  const target = clamp(Number(frameId));
  if (!Number.isInteger(target)) return false;
  state.loading = true;
  setNavigationDisabled(true);
  try {
    const [metadata, image] = await Promise.all([api(metadataUrl(target)), loadImage(frameUrl(target))]);
    state.current = target;
    state.metadata = metadata;
    $("frameImage").src = image.src;
    renderFrameState();
    preloadNearby();
    return true;
  } catch (error) {
    showMessage(error.message, true);
    stopPlayback();
    return false;
  } finally {
    state.loading = false;
    setNavigationDisabled(false);
  }
}

function setNavigationDisabled(disabled) {
  document.querySelectorAll("[data-nav], #jumpButton, #frameSlider, #playPause").forEach((element) => {
    element.disabled = disabled || !state.session?.ready;
  });
}

function preloadNearby() {
  for (let offset = -10; offset <= 10; offset += 1) {
    const frameId = state.current + offset;
    if (frameId >= 0 && frameId <= state.session.last_frame_id) new Image().src = frameUrl(frameId);
  }
}

function renderFrameState() {
  const record = state.metadata;
  $("frameCounter").textContent = `FRAME ${String(state.current).padStart(3, "0")} / ${state.session.last_frame_id}`;
  $("timestamp").textContent = formatTimestamp(record.timestamp_seconds);
  $("duration").textContent = `${(record.duration_seconds * 1000).toFixed(3)} ms`;
  $("frameSlider").value = state.current;
  $("jumpFrame").value = state.current;
  renderStrip();
  renderSelection();
  renderTracking();
  if ($("compareToggle").checked) renderComparison();
  if ($("trackingToggle").checked) renderBallInspector();
}

function selectedRange() {
  if (state.selectionStart === null && state.selectionEnd === null) return null;
  if (state.selectionStart === null || state.selectionEnd === null) return "incomplete";
  return [Math.min(state.selectionStart, state.selectionEnd), Math.max(state.selectionStart, state.selectionEnd)];
}

function renderStrip() {
  const strip = $("frameStrip");
  strip.replaceChildren();
  const range = selectedRange();
  for (let offset = -3; offset <= 3; offset += 1) {
    const frameId = state.current + offset;
    if (frameId < 0 || frameId > state.session.last_frame_id) {
      strip.append(document.createElement("div"));
      continue;
    }
    const button = document.createElement("button");
    button.className = "thumb";
    if (frameId === state.current) button.classList.add("current");
    if (Array.isArray(range) && frameId >= range[0] && frameId <= range[1]) button.classList.add("selected");
    const image = document.createElement("img");
    image.src = frameUrl(frameId);
    image.alt = `Frame ${frameId}`;
    const label = document.createElement("span");
    label.textContent = `FRAME ${String(frameId).padStart(3, "0")}`;
    button.append(image, label);
    button.addEventListener("click", () => navigate(frameId));
    strip.append(button);
  }
}

function renderSelection() {
  const summary = $("selectionSummary");
  const range = selectedRange();
  if (range === null) {
    summary.textContent = "Sin selección: el evento usará el frame actual.";
  } else if (range === "incomplete") {
    const frame = state.selectionStart ?? state.selectionEnd;
    summary.textContent = `Selección incompleta · frame ${frame}. Marca el otro extremo.`;
  } else {
    const start = state.session.frame_timestamps?.[range[0]];
    const end = state.session.frame_timestamps?.[range[1]];
    const times = start !== undefined && end !== undefined ? ` · Tiempo: ${start.toFixed(6)}–${end.toFixed(6)} s` : "";
    summary.textContent = `Selección: frames ${range[0]}–${range[1]}${times} · Duración: ${range[1] - range[0] + 1} frames`;
  }
  renderStrip();
}

function renderTracking() {
  const marker = $("ballMarker");
  const tracking = state.metadata?.tracking;
  const visible = $("trackingToggle").checked && tracking && tracking.x !== null && tracking.y !== null;
  marker.hidden = !visible;
  if (visible) {
    marker.style.left = `${(tracking.x / state.session.width) * 100}%`;
    marker.style.top = `${(tracking.y / state.session.height) * 100}%`;
  }
  $("ballInspector").hidden = !$("trackingToggle").checked || !state.session.tracking_available;
}

async function renderComparison() {
  const container = $("comparisonFrames");
  container.replaceChildren();
  for (const frameId of [clamp(state.current - 1), state.current, clamp(state.current + 1)]) {
    const panel = document.createElement("div");
    panel.className = "comparison-panel";
    const image = document.createElement("img");
    image.src = frameUrl(frameId);
    image.alt = `Frame ${frameId}`;
    const label = document.createElement("strong");
    label.textContent = `FRAME ${String(frameId).padStart(3, "0")}`;
    panel.append(image, label);
    container.append(panel);
  }
}

async function renderBallInspector() {
  if (!state.session.tracking_available || !$("trackingToggle").checked) return;
  const container = $("ballFrames");
  container.replaceChildren();
  for (const frameId of [clamp(state.current - 1), state.current, clamp(state.current + 1)]) {
    const [metadata, image] = await Promise.all([api(metadataUrl(frameId)), loadImage(frameUrl(frameId))]);
    const panel = document.createElement("div");
    panel.className = "comparison-panel";
    const canvas = document.createElement("canvas");
    canvas.width = 420; canvas.height = 260;
    const context = canvas.getContext("2d");
    const tracking = metadata.tracking;
    if (tracking?.x !== null && tracking?.y !== null) {
      const sourceWidth = 600; const sourceHeight = 370;
      const sourceX = Math.max(0, Math.min(image.naturalWidth - sourceWidth, tracking.x - sourceWidth / 2));
      const sourceY = Math.max(0, Math.min(image.naturalHeight - sourceHeight, tracking.y - sourceHeight / 2));
      context.drawImage(image, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, canvas.width, canvas.height);
      context.strokeStyle = "#00f5ff"; context.lineWidth = 4;
      context.beginPath(); context.arc(canvas.width / 2, canvas.height / 2, 13, 0, Math.PI * 2); context.stroke();
    } else {
      context.drawImage(image, 0, 0, image.naturalWidth, image.naturalHeight, 0, 0, canvas.width, canvas.height);
    }
    const label = document.createElement("strong");
    label.textContent = `FRAME ${String(frameId).padStart(3, "0")}`;
    panel.append(canvas, label); container.append(panel);
  }
}

function showMessage(text, error = false) {
  $("message").textContent = text;
  $("message").style.color = error ? "#ff9c9c" : "#ffd078";
}

async function createEvent(preset) {
  const range = selectedRange();
  if (range === "incomplete") return showMessage("Marca inicio y fin, o limpia la selección.", true);
  const [frameStart, frameEnd] = range || [state.current, state.current];
  try {
    await api("/api/events", { method: "POST", body: JSON.stringify({ preset, frame_start: frameStart, frame_end: frameEnd }) });
    state.selectionStart = null; state.selectionEnd = null;
    await refreshEvents();
    $("saveStatus").textContent = "Guardado automáticamente";
    showMessage(`Evento guardado en frames ${frameStart}–${frameEnd}.`);
    renderSelection();
  } catch (error) { showMessage(error.message, true); }
}

async function refreshEvents() {
  const payload = await api("/api/events");
  state.events = payload.events;
  const rows = $("eventRows"); rows.replaceChildren();
  state.events.forEach((event, index) => {
    const row = document.createElement("tr");
    const values = [index + 1, event.type, `${event.player}/${event.side}`, `${event.frame_start}–${event.frame_end}`, event.frame_end - event.frame_start + 1, `${event.time_start_seconds.toFixed(6)}–${event.time_end_seconds.toFixed(6)} s`];
    values.forEach((value) => { const cell = document.createElement("td"); cell.textContent = value; row.append(cell); });
    const actions = document.createElement("td");
    const edit = document.createElement("button"); edit.textContent = "Editar"; edit.addEventListener("click", () => openEdit(event));
    const remove = document.createElement("button"); remove.textContent = "Eliminar"; remove.addEventListener("click", () => deleteEvent(event.id));
    actions.append(edit, remove); row.append(actions); rows.append(row);
  });
}

function openEdit(event) {
  $("editId").value = event.id; $("editType").value = event.type; $("editPlayer").value = event.player;
  $("editSide").value = event.side; $("editShot").value = event.shot_type; $("editZone").value = event.court_zone;
  $("editStart").value = event.frame_start; $("editEnd").value = event.frame_end; $("editNotes").value = event.notes;
  $("editDialog").showModal();
}

async function deleteEvent(eventId) {
  try { await api(`/api/events/${eventId}`, { method: "DELETE" }); await refreshEvents(); $("saveStatus").textContent = "Guardado automáticamente"; }
  catch (error) { showMessage(error.message, true); }
}

function stopPlayback() {
  state.playing = false; clearTimeout(state.playTimer); state.playTimer = null; $("playPause").textContent = "Play";
}

async function playbackStep() {
  if (!state.playing) return;
  if (state.current >= state.session.last_frame_id) return stopPlayback();
  const duration = state.metadata.duration_seconds;
  state.playTimer = setTimeout(async () => { const moved = await navigate(state.current + 1); if (moved) playbackStep(); }, duration * 1000);
}

function togglePlayback() {
  if (state.playing) return stopPlayback();
  state.playing = true; $("playPause").textContent = "Pausa"; playbackStep();
}

function bindControls() {
  document.querySelectorAll("[data-nav]").forEach((button) => button.addEventListener("click", () => navigate(state.current + Number(button.dataset.nav))));
  document.querySelectorAll("[data-zoom]").forEach((button) => button.addEventListener("click", () => { state.zoom = Number(button.dataset.zoom); $("zoomContent").style.width = `${state.zoom * 100}%`; }));
  document.querySelectorAll("[data-preset]").forEach((button) => button.addEventListener("click", () => createEvent(button.dataset.preset)));
  $("playPause").addEventListener("click", togglePlayback);
  $("frameSlider").addEventListener("input", (event) => navigate(Number(event.target.value)));
  $("jumpButton").addEventListener("click", () => navigate(Number($("jumpFrame").value)));
  $("markStart").addEventListener("click", () => { state.selectionStart = state.current; renderSelection(); });
  $("markEnd").addEventListener("click", () => { state.selectionEnd = state.current; renderSelection(); });
  $("clearSelection").addEventListener("click", () => { state.selectionStart = null; state.selectionEnd = null; renderSelection(); });
  $("trackingToggle").addEventListener("change", () => { renderTracking(); renderBallInspector(); });
  $("compareToggle").addEventListener("change", () => { $("comparison").hidden = !$("compareToggle").checked; if ($("compareToggle").checked) renderComparison(); });
  $("undoButton").addEventListener("click", async () => { try { await api("/api/events/undo", { method: "POST", body: "{}" }); await refreshEvents(); $("saveStatus").textContent = "Guardado automáticamente"; } catch (error) { showMessage(error.message, true); } });
  $("exportButton").addEventListener("click", async () => { try { await api("/api/export", { method: "POST", body: "{}" }); showMessage("Anotación final guardada correctamente."); } catch (error) { showMessage(error.message, true); } });
  $("cancelEdit").addEventListener("click", () => $("editDialog").close());
  $("editForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = { type: $("editType").value, player: $("editPlayer").value, side: $("editSide").value, shot_type: $("editShot").value, court_zone: $("editZone").value, notes: $("editNotes").value, frame_start: Number($("editStart").value), frame_end: Number($("editEnd").value) };
    try { await api(`/api/events/${$("editId").value}`, { method: "PATCH", body: JSON.stringify(body) }); $("editDialog").close(); await refreshEvents(); $("saveStatus").textContent = "Guardado automáticamente"; }
    catch (error) { showMessage(error.message, true); }
  });
  document.addEventListener("keydown", (event) => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") { event.preventDefault(); $("undoButton").click(); return; }
    const step = event.shiftKey ? 10 : 1;
    if (event.key === "ArrowLeft") { event.preventDefault(); navigate(state.current - step); }
    if (event.key === "ArrowRight") { event.preventDefault(); navigate(state.current + step); }
    if (event.code === "Space") { event.preventDefault(); togglePlayback(); }
    if (event.key.toLowerCase() === "i") { state.selectionStart = state.current; renderSelection(); }
    if (event.key.toLowerCase() === "o") { state.selectionEnd = state.current; renderSelection(); }
    if (event.key === "Escape") { state.selectionStart = null; state.selectionEnd = null; renderSelection(); }
  });
}

async function initialize() {
  bindControls();
  try {
    state.session = await api("/api/session");
    const selfTest = await api("/api/self-test");
    const ready = state.session.ready && selfTest.passed_count === 30;
    $("status").textContent = ready ? `Video preparado · ${state.session.frame_count} frames` : "Herramienta no lista";
    annotationControls().forEach((element) => { element.disabled = !ready; });
    if (!ready) {
      const failures = selfTest.criteria.filter((criterion) => !criterion.passed).map((criterion) => `${criterion.id}. ${criterion.name}: ${criterion.detail}`);
      showMessage(`Herramienta no lista · ${failures.join(" · ")}`, true);
    }
    $("trackingToggle").disabled = !state.session.tracking_available;
    await navigate(0);
    await refreshEvents();
  } catch (error) {
    $("status").textContent = "Herramienta no lista";
    showMessage(error.message, true);
    annotationControls().forEach((element) => { element.disabled = true; });
  }
}

initialize();
