/* ═══════════════════════════════════════════════════════════
   Wumpus World — Frontend Controller
   ═══════════════════════════════════════════════════════════ */

const API = "";

// DOM refs
const gridContainer = document.getElementById("grid-container");
const statusMsg     = document.getElementById("status-message");
const statusIcon    = document.getElementById("status-icon");
const btnNewGame    = document.getElementById("btn-new-game");
const btnStep       = document.getElementById("btn-step");
const btnAuto       = document.getElementById("btn-auto");
const speedSlider   = document.getElementById("speed-slider");
const speedValue    = document.getElementById("speed-value");
const logEntries    = document.getElementById("log-entries");
const inputRows     = document.getElementById("input-rows");
const inputCols     = document.getElementById("input-cols");

// Metric elements
const metricInference = document.getElementById("metric-inference");
const metricKB        = document.getElementById("metric-kb");
const metricExplored  = document.getElementById("metric-explored");
const metricTotal     = document.getElementById("metric-total");

// Percept elements
const perceptBreeze = document.getElementById("percept-breeze");
const perceptStench = document.getElementById("percept-stench");

// State
let autoRunning = false;
let autoTimer   = null;
let currentState = null;

// Icons for cell content
const ICONS = {
  agent:   "🤖",
  pit:     "🕳️",
  wumpus:  "👹",
  breeze:  "💨",
  stench:  "💀",
  safe:    "✓",
  skull:   "☠️",
};

/* ─── Speed Slider ─── */
speedSlider.addEventListener("input", () => {
  speedValue.textContent = speedSlider.value + "ms";
  if (autoRunning) {
    clearInterval(autoTimer);
    autoTimer = setInterval(doStep, parseInt(speedSlider.value));
  }
});

/* ─── New Game ─── */
btnNewGame.addEventListener("click", async () => {
  stopAuto();
  const r = parseInt(inputRows.value) || 4;
  const c = parseInt(inputCols.value) || 4;

  try {
    const res = await fetch(API + "/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows: r, cols: c }),
    });
    const data = await res.json();
    currentState = data;
    buildGrid(data.rows, data.cols);
    renderState(data);
    btnStep.disabled = false;
    btnAuto.disabled = false;
    clearLog();
    addLog(data.message, "system");
  } catch (err) {
    setStatus("❌", "Failed to connect to server. Is Flask running?");
  }
});

/* ─── Step ─── */
btnStep.addEventListener("click", () => doStep());

async function doStep() {
  try {
    const res = await fetch(API + "/step", { method: "POST" });
    const data = await res.json();
    currentState = data;
    renderState(data);

    // Classify log entry
    let logType = "";
    if (!data.alive) logType = "danger";
    else if (data.game_over) logType = "success";
    addLog(data.message, logType);

    if (data.game_over) {
      stopAuto();
      btnStep.disabled = true;
      btnAuto.disabled = true;
    }
  } catch (err) {
    setStatus("❌", "Connection lost.");
    stopAuto();
  }
}

/* ─── Auto Run ─── */
btnAuto.addEventListener("click", () => {
  if (autoRunning) {
    stopAuto();
  } else {
    startAuto();
  }
});

function startAuto() {
  autoRunning = true;
  btnAuto.innerHTML = "<span>⏸</span> Pause";
  btnAuto.classList.add("active");
  btnStep.disabled = true;
  autoTimer = setInterval(doStep, parseInt(speedSlider.value));
}

function stopAuto() {
  autoRunning = false;
  clearInterval(autoTimer);
  autoTimer = null;
  btnAuto.innerHTML = "<span>▶</span> Auto Run";
  btnAuto.classList.remove("active");
  if (currentState && !currentState.game_over) {
    btnStep.disabled = false;
  }
}

/* ─── Grid Building ─── */
function buildGrid(rows, cols) {
  gridContainer.innerHTML = "";
  gridContainer.style.gridTemplateColumns = `repeat(${cols}, 70px)`;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cell = document.createElement("div");
      cell.className = "cell unknown";
      cell.id = `cell-${r}-${c}`;
      cell.innerHTML = `<span class="cell-icon"></span>
        <span class="cell-percept"></span>
        <span class="cell-coord">${r},${c}</span>`;
      gridContainer.appendChild(cell);
    }
  }
}

/* ─── Render State ─── */
function renderState(data) {
  if (!data) return;

  // Update grid cells
  for (const [key, status] of Object.entries(data.grid)) {
    const [r, c] = key.split(",");
    const cell = document.getElementById(`cell-${r}-${c}`);
    if (!cell) continue;

    const iconEl    = cell.querySelector(".cell-icon");
    const perceptEl = cell.querySelector(".cell-percept");

    // Reset classes
    cell.className = "cell";

    // Determine cell class and icon
    let icon = "";
    let percepts = "";

    if (status === "agent") {
      cell.classList.add(data.alive ? "agent" : "dead");
      icon = data.alive ? ICONS.agent : ICONS.skull;
    } else if (status === "visited") {
      cell.classList.add("visited");
      icon = ICONS.safe;
    } else if (status === "safe") {
      cell.classList.add("safe");
      icon = "🟢";
    } else if (status === "danger") {
      cell.classList.add("danger");
      icon = "⚠️";
    } else {
      cell.classList.add("unknown");
      icon = "";
    }

    // Show percepts on visited cells
    const cellPercepts = data.percept_map && data.percept_map[key];
    if (cellPercepts && cellPercepts.length > 0) {
      const pIcons = cellPercepts.map(p =>
        p === "breeze" ? ICONS.breeze : ICONS.stench
      );
      percepts = pIcons.join("");
    }

    iconEl.textContent = icon;
    perceptEl.textContent = percepts;
  }

  // Reveal hazards on game over
  if (data.game_over && data.hazards) {
    for (const [key, types] of Object.entries(data.hazards)) {
      const [r, c] = key.split(",");
      const cell = document.getElementById(`cell-${r}-${c}`);
      if (!cell) continue;
      const iconEl = cell.querySelector(".cell-icon");

      if (key === `${data.agent[0]},${data.agent[1]}`) continue; // skip agent cell

      cell.className = "cell";
      if (types.includes("wumpus")) {
        cell.classList.add("reveal-wumpus");
        iconEl.textContent = ICONS.wumpus;
      } else if (types.includes("pit")) {
        cell.classList.add("reveal-pit");
        iconEl.textContent = ICONS.pit;
      }
    }
  }

  // Update metrics with animation
  animateValue(metricInference, data.inference_steps);
  animateValue(metricKB, data.kb_size);
  animateValue(metricExplored, data.visited_count);
  animateValue(metricTotal, data.total_cells);

  // Update percept indicators
  perceptBreeze.className = "percept-badge" +
    (data.percepts.breeze ? " active-breeze" : "");
  perceptStench.className = "percept-badge" +
    (data.percepts.stench ? " active-stench" : "");

  // Status bar
  if (!data.alive) {
    setStatus("💀", data.message);
  } else if (data.game_over) {
    setStatus("🏆", data.message);
  } else {
    setStatus("🤖", data.message);
  }
}

/* ─── Helpers ─── */
function setStatus(icon, msg) {
  statusIcon.textContent = icon;
  statusMsg.textContent = msg;
}

function animateValue(el, target) {
  const current = parseInt(el.textContent) || 0;
  if (current === target) return;
  el.textContent = target;
  el.style.color = "var(--cyan)";
  setTimeout(() => { el.style.color = ""; }, 400);
}

function addLog(msg, type) {
  const entry = document.createElement("div");
  entry.className = "log-entry" + (type ? ` log-${type}` : "");
  entry.textContent = msg;
  logEntries.prepend(entry);

  // Keep max 50 entries
  while (logEntries.children.length > 50) {
    logEntries.removeChild(logEntries.lastChild);
  }
}

function clearLog() {
  logEntries.innerHTML = "";
}
