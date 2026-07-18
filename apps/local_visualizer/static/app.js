const TANK_KEYS = ["tower", "treated", "raw"];
const SENSOR_JUMP_THRESHOLD = 300;
const API_BASE = "http://127.0.0.1:8000";

const state = {
  runs: [],
  rows: [],
  index: 0,
  playing: false,
  timer: null,
  tankRanges: {},
};

const els = {
  runSelect: document.getElementById("runSelect"),
  playButton: document.getElementById("playButton"),
  speedSelect: document.getElementById("speedSelect"),
  timeSlider: document.getElementById("timeSlider"),
  systemState: document.getElementById("systemState"),
  timeValue: document.getElementById("timeValue"),
  pump1Value: document.getElementById("pump1Value"),
  pump2Value: document.getElementById("pump2Value"),
  dataQualityValue: document.getElementById("dataQualityValue"),
  valve1Value: document.getElementById("valve1Value"),
  valve2Value: document.getElementById("valve2Value"),
  valve3Value: document.getElementById("valve3Value"),
  valve4Value: document.getElementById("valve4Value"),
  flowP1Value: document.getElementById("flowP1Value"),
  flowP2Value: document.getElementById("flowP2Value"),
  flowValve1Value: document.getElementById("flowValve1Value"),
  flowOutletValue: document.getElementById("flowOutletValue"),
  towerValue: document.getElementById("towerValue"),
  treatedValue: document.getElementById("treatedValue"),
  rawValue: document.getElementById("rawValue"),
  jumpValue: document.getElementById("jumpValue"),
  towerFill: document.getElementById("towerFill"),
  treatedFill: document.getElementById("treatedFill"),
  rawFill: document.getElementById("rawFill"),
  pump1Icon: document.getElementById("pump1Icon"),
  pump2Icon: document.getElementById("pump2Icon"),
  valve1Icon: document.getElementById("valve1Icon"),
  valve2Icon: document.getElementById("valve2Icon"),
  valve3Icon: document.getElementById("valve3Icon"),
  valve4Icon: document.getElementById("valve4Icon"),
  rawToPump1Pipe: document.getElementById("rawToPump1Pipe"),
  pump1ToTreatedPipe: document.getElementById("pump1ToTreatedPipe"),
  treatedToPump2Pipe: document.getElementById("treatedToPump2Pipe"),
  pump2ToTowerPipe: document.getElementById("pump2ToTowerPipe"),
  towerDropPipe: document.getElementById("towerDropPipe"),
  branch2Pipe: document.getElementById("branch2Pipe"),
  branch3Pipe: document.getElementById("branch3Pipe"),
  branch4Pipe: document.getElementById("branch4Pipe"),
  pump1FlowDot: document.getElementById("pump1FlowDot"),
  pump2FlowDot: document.getElementById("pump2FlowDot"),
  branch2FlowDot: document.getElementById("branch2FlowDot"),
  branch3FlowDot: document.getElementById("branch3FlowDot"),
  branch4FlowDot: document.getElementById("branch4FlowDot"),
  sparkline: document.getElementById("sparkline"),
};

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return response.json();
}

function normalizeRun(run) {
  return {
    run_name: run.run_name || run.run_id,
    rows: run.rows,
    duration_seconds: run.duration_seconds,
    has_timeseries: run.has_timeseries,
  };
}

async function withFastApiRowCount(run) {
  if (!run.run_name || run.has_timeseries === false || Number.isInteger(run.rows)) {
    return run;
  }

  try {
    const payload = await fetchJson(`${API_BASE}/runs/${encodeURIComponent(run.run_name)}/timeseries?limit=1`);
    return {
      ...run,
      rows: payload.total_matching_rows,
    };
  } catch (error) {
    console.warn(`Unable to load row count for ${run.run_name}.`, error);
    return run;
  }
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function fmt(value, digits = 1) {
  return finiteNumber(value) ? value.toFixed(digits) : "--";
}

function isOn(value) {
  return finiteNumber(value) && value > 0.5;
}

function setActive(element, active) {
  if (element) element.classList.toggle("active", Boolean(active));
}

function setQuality(ok, text) {
  els.dataQualityValue.textContent = text;
  els.dataQualityValue.classList.toggle("ok", ok);
  els.dataQualityValue.classList.toggle("warn", !ok);
  els.jumpValue.textContent = text;
  els.jumpValue.classList.toggle("ok", ok);
  els.jumpValue.classList.toggle("warn", !ok);
}

function computeTankRanges() {
  state.tankRanges = {};
  for (const key of TANK_KEYS) {
    const values = state.rows.map(row => row[key]).filter(finiteNumber);
    if (!values.length) {
      state.tankRanges[key] = { min: 0, max: 1 };
      continue;
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    state.tankRanges[key] = { min, max: max === min ? min + 1 : max };
  }
}

function tankScale(key, value) {
  const range = state.tankRanges[key];
  if (!range || !finiteNumber(value)) return 0.05;
  const normalized = (value - range.min) / (range.max - range.min);
  return Math.max(0.04, Math.min(1, normalized));
}

function updateTank(key, value, fillElement, valueElement) {
  const height = 186 * tankScale(key, value);
  fillElement.setAttribute("height", height.toFixed(1));
  fillElement.setAttribute("y", (230 - height).toFixed(1));
  valueElement.textContent = fmt(value, 0);
}

function currentJumpWarning() {
  if (state.index === 0 || !state.rows.length) return null;
  const current = state.rows[state.index];
  const previous = state.rows[state.index - 1];

  for (const key of TANK_KEYS) {
    const delta = current[key] - previous[key];
    if (finiteNumber(delta) && Math.abs(delta) > SENSOR_JUMP_THRESHOLD) {
      return `${key} ${delta > 0 ? "+" : ""}${delta.toFixed(0)}`;
    }
  }
  return null;
}

function updateFlowMarkers(row) {
  const pump1Active = isOn(row.pump1_pwm);
  const pump2Active = isOn(row.pump2_pwm);
  const valve2Active = isOn(row.valve2);
  const valve3Active = isOn(row.valve3);
  const valve4Active = isOn(row.valve4);

  setActive(els.rawToPump1Pipe, pump1Active);
  setActive(els.pump1ToTreatedPipe, pump1Active || isOn(row.valve1));
  setActive(els.treatedToPump2Pipe, pump2Active);
  setActive(els.pump2ToTowerPipe, pump2Active);
  setActive(els.towerDropPipe, valve2Active || valve3Active || valve4Active);
  setActive(els.branch2Pipe, valve2Active);
  setActive(els.branch3Pipe, valve3Active);
  setActive(els.branch4Pipe, valve4Active);

  setActive(els.pump1FlowDot, pump1Active);
  setActive(els.pump2FlowDot, pump2Active);
  setActive(els.branch2FlowDot, valve2Active);
  setActive(els.branch3FlowDot, valve3Active);
  setActive(els.branch4FlowDot, valve4Active);

  positionMarker(els.pump1FlowDot, els.rawToPump1Pipe, state.index * 0.04);
  positionMarker(els.pump2FlowDot, els.pump2ToTowerPipe, state.index * 0.04);
  positionMarker(els.branch2FlowDot, els.branch2Pipe, state.index * 0.05);
  positionMarker(els.branch3FlowDot, els.branch3Pipe, state.index * 0.05);
  positionMarker(els.branch4FlowDot, els.branch4Pipe, state.index * 0.05);
}

function positionMarker(marker, path, phase) {
  if (!marker || !path || !marker.classList.contains("active")) return;
  const length = path.getTotalLength();
  const point = path.getPointAtLength((phase % 1) * length);
  marker.setAttribute("transform", `translate(${point.x.toFixed(1)} ${point.y.toFixed(1)})`);
}

function updateRow() {
  if (!state.rows.length) return;
  const row = state.rows[state.index];

  const running = isOn(row.pump1_pwm) || isOn(row.pump2_pwm) ||
    isOn(row.valve1) || isOn(row.valve2) || isOn(row.valve3) || isOn(row.valve4);

  els.systemState.textContent = running ? "Running" : "Idle";
  els.systemState.style.color = running ? "var(--green)" : "var(--muted)";
  els.timeValue.textContent = `${fmt(row.t_seconds, 0)} s`;
  els.pump1Value.textContent = `${fmt(row.pump1_pwm, 0)} PWM`;
  els.pump2Value.textContent = `${fmt(row.pump2_pwm, 0)} PWM`;

  for (let i = 1; i <= 4; i += 1) {
    const valveValue = row[`valve${i}`];
    els[`valve${i}Value`].textContent = isOn(valveValue) ? "Open" : "Closed";
    setActive(els[`valve${i}Icon`], isOn(valveValue));
  }

  setActive(els.pump1Icon, isOn(row.pump1_pwm));
  setActive(els.pump2Icon, isOn(row.pump2_pwm));
  updateFlowMarkers(row);

  els.flowP1Value.textContent = fmt(row.flow_p1);
  els.flowP2Value.textContent = fmt(row.flow_p2);
  els.flowValve1Value.textContent = fmt(row.flow_valve1);
  els.flowOutletValue.textContent = fmt(row.flow_outlet);

  updateTank("tower", row.tower, els.towerFill, els.towerValue);
  updateTank("treated", row.treated, els.treatedFill, els.treatedValue);
  updateTank("raw", row.raw, els.rawFill, els.rawValue);

  const warning = currentJumpWarning();
  setQuality(!warning, warning || "Normal");

  els.timeSlider.value = String(state.index);
  drawSparkline();
}

function drawSparkline() {
  const canvas = els.sparkline;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, "#fffefa");
  gradient.addColorStop(1, "#edf7f5");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(83,112,108,0.22)";
  ctx.lineWidth = 1;
  for (let y = 30; y < height; y += 36) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  const keys = [
    ["tower", "#126b84"],
    ["treated", "#c46c2c"],
    ["raw", "#2f8f5b"],
  ];

  for (const [key, color] of keys) {
    const values = state.rows.map(row => row[key]).filter(finiteNumber);
    if (!values.length) continue;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    state.rows.forEach((row, i) => {
      if (!finiteNumber(row[key])) return;
      const x = (i / Math.max(1, state.rows.length - 1)) * width;
      const y = height - 20 - ((row[key] - min) / span) * (height - 42);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  const cursorX = (state.index / Math.max(1, state.rows.length - 1)) * width;
  ctx.strokeStyle = "#14201f";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cursorX, 0);
  ctx.lineTo(cursorX, height);
  ctx.stroke();
}

async function loadRuns() {
  let payload;
  try {
    payload = await fetchJson(`${API_BASE}/runs`);
  } catch (apiError) {
    console.warn("FastAPI run list unavailable; falling back to local CSV server.", apiError);
    try {
      payload = await fetchJson("/api/runs");
    } catch (fallbackError) {
      throw new Error(`Unable to load runs from FastAPI or local fallback: ${fallbackError.message}`);
    }
  }

  const runs = (payload.runs || [])
    .map(normalizeRun)
    .filter(run => run.run_name && run.has_timeseries !== false);

  state.runs = await Promise.all(runs.map(withFastApiRowCount));

  if (!state.runs.length) {
    throw new Error("No replayable runs were returned by FastAPI or the local fallback.");
  }

  els.runSelect.innerHTML = "";
  for (const run of state.runs) {
    const option = document.createElement("option");
    option.value = run.run_name;
    const rowText = Number.isInteger(run.rows) ? `${run.rows} rows` : "timeseries";
    option.textContent = `${run.run_name} (${rowText})`;
    els.runSelect.appendChild(option);
  }
  const preferred = state.runs.find(run => run.run_name === "full_cycle_run_004");
  if (preferred) els.runSelect.value = preferred.run_name;
  await loadRun(els.runSelect.value);
}

async function loadRun(runName) {
  stop();
  let payload;
  try {
    payload = await fetchJson(`${API_BASE}/runs/${encodeURIComponent(runName)}/timeseries`);
  } catch (apiError) {
    console.warn(`FastAPI timeseries unavailable for ${runName}; falling back to local CSV server.`, apiError);
    try {
      payload = await fetchJson(`/api/run?name=${encodeURIComponent(runName)}`);
    } catch (fallbackError) {
      throw new Error(`Unable to load ${runName} from FastAPI or local fallback: ${fallbackError.message}`);
    }
  }

  state.rows = payload.rows || [];
  if (!state.rows.length) {
    throw new Error(`No replay rows returned for ${runName}.`);
  }

  state.index = 0;
  els.timeSlider.max = String(Math.max(0, state.rows.length - 1));
  computeTankRanges();
  updateRow();
}

function tick() {
  const speed = Number(els.speedSelect.value);
  state.index = Math.min(state.rows.length - 1, state.index + speed);
  if (state.index >= state.rows.length - 1) {
    stop();
  }
  updateRow();
}

function play() {
  if (!state.rows.length || state.playing) return;
  state.playing = true;
  els.playButton.textContent = "Pause";
  state.timer = window.setInterval(tick, 250);
}

function stop() {
  state.playing = false;
  els.playButton.textContent = "Play";
  if (state.timer) {
    window.clearInterval(state.timer);
    state.timer = null;
  }
}

els.playButton.addEventListener("click", () => {
  if (state.playing) stop();
  else play();
});

els.runSelect.addEventListener("change", event => loadRun(event.target.value));
els.timeSlider.addEventListener("input", event => {
  state.index = Number(event.target.value);
  updateRow();
});

loadRuns().catch(error => {
  console.error(error);
  els.runSelect.innerHTML = "";
  const option = document.createElement("option");
  option.textContent = "Data sources unavailable";
  els.runSelect.appendChild(option);
  els.playButton.disabled = true;
  els.systemState.textContent = "Load error";
  els.systemState.style.color = "var(--red)";
  setQuality(false, "Data load failed");
});
