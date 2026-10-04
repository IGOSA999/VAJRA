let materials = null;
let currentResult = null;
let currentDesign = null;
let currentWeatherMeta = null;
let activeJobId = null;
let statusTimer = null;
let statusStartedAt = 0;
const tableState = {};
const $ = id => document.getElementById(id);

async function getJSON(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (_) {
    throw new Error("Could not reach the server.");
  }
  if (!response.ok) {
    let detail = "";
    const type = response.headers.get("content-type") || "";
    if (type.includes("application/json")) {
      const body = await response.json().catch(() => ({}));
      detail = String(body.detail || "").trim();
    }
    const wake = [502, 503, 504].includes(response.status)
      ? " The service may still be waking up. Wait a minute and try again."
      : "";
    throw new Error(`The server returned an error (HTTP ${response.status}).${detail ? ` ${detail}` : wake}`);
  }
  return response.json();
}

async function waitForHealth() {
  let warned = false;
  while (true) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 4000);
      await getJSON("/api/health", {signal: controller.signal});
      clearTimeout(timer);
      return;
    } catch (_) {
      if (!warned) { setStatus("Waking the server. This can take about a minute on the free plan."); warned = true; }
      await new Promise(resolve => setTimeout(resolve, 5000));
    }
  }
}

function selectedDays() { return Number($("period").value); }
function useColdest() { return selectedDays() === 14; }
function weatherSource() { return $("weather_source").value === "upload" ? "upload" : "bundled"; }
function setStatus(message, error = false) {
  const el = $("run-status");
  const value = String(message || "").trim() || "The server returned an unexpected empty message.";
  el.textContent = value;
  el.className = error ? "status error" : "status";
}
function startStatusClock(label) {
  stopStatusClock();
  statusStartedAt = performance.now();
  statusTimer = setInterval(() => {
    const seconds = Math.floor((performance.now() - statusStartedAt) / 1000);
    setStatus(`${label}: Running, ${seconds} s so far.`);
  }, 1000);
}
function stopStatusClock() {
  if (statusTimer) clearInterval(statusTimer);
  statusTimer = null;
}
function setBusy(busy) {
  ["run", "compare", "compare-materials", "sheet", "ansys", "upload-weather"].forEach(id => {
    const b = $(id);
    if (b) b.disabled = busy;
  });
}
function populateSelect(id, values) {
  const select = $(id);
  select.innerHTML = "";
  Object.entries(values).forEach(([key, obj]) => {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = obj.label || humanize(key);
    select.appendChild(option);
  });
}
function formatDateRange(period) {
  if (!period || period.length < 2) return "the selected period";
  const a = new Date(period[0]);
  const b = new Date(period[1]);
  const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  if (a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth()) {
    return `${a.getDate()} to ${b.getDate()} ${months[a.getMonth()]} ${a.getFullYear()}`;
  }
  return `${a.getDate()} ${months[a.getMonth()]} ${a.getFullYear()} to ${b.getDate()} ${months[b.getMonth()]} ${b.getFullYear()}`;
}
function updateProvenance(meta) {
  currentWeatherMeta = meta || {};
  const provider = meta.provider || meta.weather_source || "Weather input";
  const name = provider === "NASA POWER" ? "Leh, Ladakh" : provider === "Uploaded weather file" ? `Your file: ${meta.source}` : "Weather input";
  const lat = Number.isFinite(Number(meta.lat)) ? `${Number(meta.lat).toFixed(2)}° N` : "site coordinates not supplied";
  const lon = Number.isFinite(Number(meta.lon)) ? `${Number(meta.lon).toFixed(2)}° E` : "";
  const elev = Number.isFinite(Number(meta.elevation_m)) ? `${Number(meta.elevation_m).toLocaleString("en-IN")} m` : "";
  $("weather-line").innerHTML = `<div>${name}. ${lat}${lon ? `, ${lon}` : ""}${elev ? `, ${elev}` : ""}</div><div>${provider}${meta.year ? `, ${meta.year}` : ""}. ${Number(meta.present_hours || 0).toLocaleString()} of ${Number(meta.expected_hours || meta.present_hours || 0).toLocaleString()} hours present${meta.missing_hours ? `, ${meta.missing_hours} missing` : ""}.</div>`;
  $("site-readout").textContent = `${name}. ${lat}${lon ? `, ${lon}` : ""}${elev ? `, ${elev}` : ""}`;
  $("synthetic-banner").hidden = !meta.synthetic;
}
function setMassVisibility() {
  const type = $("mass_type").value;
  $("mass-fields").hidden = type === "none";
  $("pcm-fields").hidden = type !== "pcm";
}
function syncSource() {
  $("upload-block").hidden = $("weather_source").value !== "upload";
}
function collectDesign() {
  const lat = Number(currentWeatherMeta?.lat);
  const lon = Number(currentWeatherMeta?.lon);
  const elevation = Number(currentWeatherMeta?.elevation_m);
  if (![lat, lon, elevation].every(Number.isFinite)) {
    throw new Error("The active weather source does not provide site coordinates and elevation for the solar calculation.");
  }
  const from = Number($("vent_start").value);
  const to = Number($("vent_end").value);
  if (!(from >= 0 && from <= 23 && to >= 1 && to <= 24 && from < to)) {
    throw new Error("Ventilation hours must have a start before the end.");
  }
  const massType = $("mass_type").value;
  const interiorMass = massType === "none" ? null : {
    material: massType === "water" ? "water" : "pcm_paraffin",
    kg: Number($("mass_kg").value),
    surface_area_m2: Number($("mass_area").value),
    h_inside_w_m2k: Number($("mass_h").value),
    ...(massType === "pcm" ? {
      latent_heat_j_kg: Number($("pcm_latent").value) * 1000,
      melt_low_c: Number($("pcm_low").value),
      melt_high_c: Number($("pcm_high").value)
    } : {})
  };
  return {
    name: "user design",
    site: {lat, lon, elevation_m: elevation},
    geometry: {
      length_m: Number($("length").value),
      width_m: Number($("width").value),
      wall_height_m: Number($("height").value),
      roof: {type: $("roof_type").value, pitch_deg: Number($("pitch").value), high_side: "N"},
      azimuth_deg: Number($("azimuth").value)
    },
    constructions: {
      wall: [
        ...(Number($("insulation_mm").value) > 0 ? [{material: "mineral_wool", mm: Number($("insulation_mm").value)}] : []),
        {material: $("wall_material").value, mm: Number($("wall_mm").value)}
      ],
      roof: [{material: $("roof_material").value, mm: Number($("roof_mm").value)}],
      floor: [{material: $("floor_material").value, mm: Number($("floor_mm").value)}],
      ground: {soil_depth_m: 2}
    },
    openings: Number($("win_w").value) > 0 && Number($("win_h").value) > 0 ? [{
      facade: "main", width_m: Number($("win_w").value), height_m: Number($("win_h").value), glazing: $("glazing").value,
      night_cover: $("cover").value === "yes" ? {r_m2k_per_w: 0.8, from_hour: 17, to_hour: 9} : {}
    }] : [],
    air: {infiltration_ach: Number($("infiltration").value), vent_ach: Number($("vent").value), vent_hours: [from, to]},
    internal_gains_w: 0,
    solar_split: {floor_and_mass: 0.7},
    comfort: {low_c: Number($("comfort_low").value), high_c: Number($("comfort_high").value)},
    setpoint_c: Number($("comfort_low").value),
    ground_reflectance: 0.2,
    interior_mass: interiorMass
  };
}
function formatValue(key, value) {
  if (!Number.isFinite(value)) return "";
  if (key === "heating_kwh") return value.toFixed(0);
  if (key === "heating_kwh_per_m2") return value.toFixed(1);
  if (key === "hours_above_zero" || key === "overheat_degree_hours") return value.toFixed(0);
  if (key === "orientation_deg" || key === "insulation_mm") return value.toFixed(0);
  if (key === "t_min_c" || key === "mean_delta_c") return value.toFixed(1);
  return value.toFixed(1);
}
function makeTableRows(rows, keys, tableId) {
  const state = tableState[tableId] || {key: "heating_kwh", dir: "asc"};
  const copy = [...rows];
  copy.sort((a, b) => {
    const av = a[state.key], bv = b[state.key];
    const an = Number(av), bn = Number(bv);
    const cmp = Number.isFinite(an) && Number.isFinite(bn) ? an - bn : String(av ?? "").localeCompare(String(bv ?? ""));
    return state.dir === "asc" ? cmp : -cmp;
  });
  return copy;
}
function renderTable(id, captionId, rows, materialMode = false, period = null) {
  const keys = materialMode
    ? ["description","status","t_min_c","mean_delta_c","heating_kwh","heating_kwh_per_m2","hours_above_zero","overheat_degree_hours","insulation_mm","wall_material","glazing"]
    : ["description","status","t_min_c","mean_delta_c","heating_kwh","heating_kwh_per_m2","hours_above_zero","overheat_degree_hours","orientation_deg","insulation_mm","wall_material","glazing"];
  const sortedByEnergy = [...rows].sort((a,b) => Number(a.heating_kwh)-Number(b.heating_kwh));
  const lowest = sortedByEnergy[0]?.heating_kwh;
  const displayRows = rows.map(r => ({...r, status: `${r.is_baseline ? "Baseline" : ""}${r.is_baseline && r.heating_kwh === lowest ? " · " : ""}${r.heating_kwh === lowest ? "Lowest" : ""}`.trim() || ""}));
  const caption = materialMode
    ? `Six wall materials on the same ${formatDateRange(period || currentResult?.meta?.period)}. Ranked by heating energy.`
    : `Seven designs on the same ${formatDateRange(period || currentResult?.meta?.period)}. Ranked by heating energy.`;
  $(captionId).textContent = caption;
  const table = $(id);
  table.innerHTML = `<thead><tr>${keys.map((key, index) => `<th data-sort-key="${key}" class="${index === 0 ? "sticky-col" : "num"} sortable" scope="col">${index === 0 ? "Design" : columnLabel(key)}${tableState[id]?.key === key ? (tableState[id].dir === "asc" ? " ↑" : " ↓") : ""}</th>`).join("")}</tr></thead><tbody>${makeTableRows(displayRows, keys, id).map(r => `<tr>${keys.map((key, index) => { const value = key === "description" ? r[key] || "Design" : key === "status" ? r[key] : key === "wall_material" || key === "glazing" ? humanize(r[key]) : formatValue(key, Number(r[key])); return `<td class="${index === 0 ? "sticky-col" : "num"}">${value}</td>`; }).join("")}</tr>`).join("")}</tbody>`;
  table.querySelectorAll("th.sortable").forEach(th => th.addEventListener("click", () => {
    const key = th.dataset.sortKey;
    const current = tableState[id] || {key: key, dir: "asc"};
    tableState[id] = {key, dir: current.key === key && current.dir === "asc" ? "desc" : "asc"};
    renderTable(id, captionId, rows, materialMode, period);
  }));
}
function renderCompare(rows, period = null) { renderTable("compare-table", "compare-caption", rows, false, period); }
function renderMaterialCompare(rows, period = null) { renderTable("material-table", "material-caption", rows, true, period); }
function buildNightShapes(result) {
  const shapes = [];
  const night = result.series.is_night || [];
  const x = result.series.time_ist || result.series.time;
  let start = null;
  for (let i = 0; i < night.length; i++) {
    if (night[i] && start === null) start = x[i];
    const ends = start !== null && (!night[i + 1] || i === night.length - 1);
    if (ends) { shapes.push({type:"rect", xref:"x", x0:start, x1:x[i], yref:"paper", y0:0, y1:1, fillcolor:"#D9D4C8", opacity:0.24, line:{width:0}, layer:"below"}); start = null; }
  }
  return shapes;
}
function plotResult(result) {
  const x = result.series.time_ist || result.series.time;
  const indoor = result.series.t_air_in_c;
  const outside = result.series.t_air_out_c;
  const low = Number($("comfort_low").value), high = Number($("comfort_high").value);
  const minIdx = indoor.reduce((best, value, idx) => value < indoor[best] ? idx : best, 0);
  const shapes = [{type:"rect",xref:"paper",x0:0,x1:1,y0:low,y1:high,fillcolor:"#E4DFD2",line:{width:0},layer:"below"}, ...buildNightShapes(result)];
  const annotations = [
    {x:x[x.length-1],y:indoor[indoor.length-1],xref:"x",yref:"y",text:"Indoor",showarrow:false,xanchor:"left",xshift:8,font:{size:11}},
    {x:x[x.length-1],y:outside[outside.length-1],xref:"x",yref:"y",text:"Outside",showarrow:false,xanchor:"left",xshift:8,font:{size:11}},
    {x:x[minIdx],y:indoor[minIdx],xref:"x",yref:"y",text:`Minimum ${indoor[minIdx].toFixed(1)} °C`,showarrow:true,arrowhead:2,ax:35,ay:-35,font:{size:10}},
    {xref:"paper",x:0.01,y:high-0.7,text:`Comfort band ${low} to ${high} °C`,showarrow:false,xanchor:"left",font:{size:10}}
  ];
  Plotly.react("temp-chart", [
    {x,y:indoor,mode:"lines",name:"Indoor",line:{color:"#1E2125",width:2},hovertemplate:"%{y:.1f} °C<extra>Indoor</extra>"},
    {x,y:outside,mode:"lines",name:"Outside",line:{color:"#2E5E7E",width:1.5},hovertemplate:"%{y:.1f} °C<extra>Outside</extra>"}
  ], {
    margin:{l:50,r:85,t:12,b:55},paper_bgcolor:"#FBFAF6",plot_bgcolor:"#FBFAF6",font:{family:"IBM Plex Sans",color:"#1E2125",size:12},hovermode:"x unified",showlegend:false,annotations,shapes,
    xaxis:{title:"Time (IST)",gridcolor:"#CFC8BA",tickformat:"%d %b",hoverformat:"%d %b %H:%M"},
    yaxis:{title:"Temperature (°C)",gridcolor:"#CFC8BA"}
  }, {displayModeBar:false,responsive:true});

  const totals = result.summary.flow_totals_kwh || {};
  const entries = Object.entries(totals).sort((a,b) => Math.abs(b[1]) - Math.abs(a[1]));
  Plotly.react("flow-chart", [{y:entries.map(e=>flowLabel(e[0])),x:entries.map(e=>e[1]),type:"bar",orientation:"h",text:entries.map(e=>Number(e[1]).toFixed(1)),textposition:"outside",cliponaxis:false,marker:{color:entries.map(e=>e[1]>=0?"#B5521B":"#2E5E7E")}}], {
    margin:{l:105,r:55,t:8,b:55},paper_bgcolor:"#FBFAF6",plot_bgcolor:"#FBFAF6",font:{family:"IBM Plex Sans",color:"#1E2125",size:11},
    xaxis:{title:"Net heat flow over the period (kWh). Positive means heat entering the room.",gridcolor:"#CFC8BA",zeroline:true,zerolinecolor:"#1E2125"},yaxis:{gridcolor:"#CFC8BA"}
  }, {displayModeBar:false,responsive:true});

  const solar = result.summary.solar_incident_kwh_m2 || {};
  const solarRows = Object.entries(solar).map(([key,value]) => `<tr><td>${flowLabel(key)}</td><td class="num">${Number(value).toFixed(1)}</td></tr>`).join("");
  $("solar-table").innerHTML = `<table class="solar-summary"><thead><tr><th>Solar input</th><th class="num">Value</th></tr></thead><tbody>${solarRows}<tr><td>Transmitted through glazing (kWh)</td><td class="num">${Number(result.summary.solar_transmitted_kwh || 0).toFixed(1)}</td></tr><tr><td>Absorbed by opaque surfaces (kWh)</td><td class="num">${Number(result.summary.solar_absorbed_opaque_kwh || 0).toFixed(1)}</td></tr></tbody></table>`;
}
function showMetrics(s) {
  $("metrics").innerHTML = [
    ["Minimum indoor", `${s.t_min_c.toFixed(1)} °C`],
    ["Maximum indoor", `${s.t_max_c.toFixed(1)} °C`],
    ["Mean indoor − outside", `${s.mean_delta_c.toFixed(1)} K`],
    ["Hours above 0 °C", `${s.hours_above_zero.toFixed(0)} h`],
    ["Heating energy", `${s.heating_kwh.toFixed(0)} kWh`]
  ].map(([label,value]) => `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div></div>`).join("");
}
async function loadSection(design, result) {
  try {
    const response = await fetch("/api/section", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({design,weather_meta:result.meta,period:result.meta.period})});
    if (!response.ok) throw new Error(`Section drawing failed (HTTP ${response.status}).`);
    $("drawing").innerHTML = await response.text();
  } catch (e) {
    $("drawing").innerHTML = `<div class="error">${e.message || "Could not load the section drawing."}</div>`;
  }
}
async function pollJob(jobId) {
  activeJobId = jobId;
  $("cancel-job").hidden = false;
  while (true) {
    const job = await getJSON(`/api/jobs/${jobId}`);
    if (job.kind === "compare" && job.rows) renderCompare(job.rows, job.period);
    if (job.kind === "materials" && job.rows) renderMaterialCompare(job.rows, job.period);
    if (job.status === "running") {
      const seconds = Math.floor((performance.now() - statusStartedAt) / 1000);
      setStatus(`Running, ${seconds} s so far. ${job.progress} of ${job.total} designs done.`);
      await new Promise(resolve => setTimeout(resolve, 1000));
      continue;
    }
    activeJobId = null;
    $("cancel-job").hidden = true;
    stopStatusClock();
    if (job.status === "failed") throw new Error(job.error || "The server reported a failed computation.");
    if (job.status === "cancelled") { setStatus("Computation cancelled.", true); return null; }
    return job;
  }
}
async function runJob(endpoint, options, label, onDone) {
  startStatusClock(label);
  setBusy(true);
  try {
    const started = await getJSON(endpoint, options);
    const job = await pollJob(started.job_id);
    if (job && onDone) await onDone(job, started);
    if (job) {
      const elapsed = Number(job.elapsed_wall_s);
      setStatus(Number.isFinite(elapsed) ? `Done in ${elapsed.toFixed(1)} s, computed on this server.` : "Done. Computed on this server.");
    }
    return job;
  } catch (e) {
    stopStatusClock();
    setStatus(e.message, true);
    throw e;
  } finally {
    setBusy(false);
  }
}
async function run() {
  currentDesign = collectDesign();
  await runJob(`/api/jobs/run?days=${selectedDays()}&coldest=${useColdest()}&source=${weatherSource()}`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(currentDesign)}, "Run", async job => {
    currentResult = job.result?.result || job.result;
    updateProvenance(currentResult.meta);
    plotResult(currentResult);
    showMetrics(currentResult.summary);
    await loadSection(currentDesign, currentResult);
  });
}
async function compare() {
  const design = collectDesign();
  await runJob(`/api/jobs/compare?days=${selectedDays()}&coldest=${useColdest()}&source=${weatherSource()}`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(design)}, "Compare designs");
}
async function compareMaterials() {
  const design = collectDesign();
  await runJob(`/api/jobs/materials?days=${selectedDays()}&coldest=${useColdest()}&source=${weatherSource()}`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(design)}, "Compare wall materials");
}
async function loadDefault() {
  setStatus(`Loading the ${useColdest() ? "coldest " : ""}${selectedDays()}-day weather window...`);
  const started = await getJSON(`/api/jobs/default?days=${selectedDays()}&coldest=${useColdest()}&source=${weatherSource()}`, {method:"POST"});
  currentDesign = started.design;
  const job = await pollJob(started.job_id);
  if (!job) return;
  currentResult = job.result?.result || job.result;
  updateProvenance(currentResult.meta);
  plotResult(currentResult);
  showMetrics(currentResult.summary);
  await loadSection(currentDesign, currentResult);
  setStatus(`Done in ${Number(job.elapsed_wall_s || 0).toFixed(1)} s, computed on this server. ${formatDateRange(currentResult.meta.period)}.`);
}
async function uploadWeather() {
  const file = $("weather_file").files[0];
  if (!file) { setStatus("Choose a weather CSV first.", true); return; }
  setBusy(true);
  try {
    const form = new FormData();
    form.append("file", file);
    const out = await getJSON("/api/upload-weather", {method:"POST",body:form});
    updateProvenance(out.source);
    $("weather_source").value = "upload";
    syncSource();
    setStatus(`Weather file loaded. ${out.rows} hourly rows present. Press Run to simulate it.`);
    $("weather_file").value = "";
  } catch (e) {
    setStatus(e.message, true);
  } finally { setBusy(false); }
}
async function changeWeatherSource() {
  syncSource();
  if (weatherSource() === "bundled") {
    try {
      const out = await getJSON("/api/use-bundled-weather", {method:"POST"});
      updateProvenance(out.source);
      setStatus("Using Leh, 2024 NASA POWER weather. Press Run to simulate it.");
    } catch (e) { setStatus(e.message, true); }
  } else {
    setStatus("Choose a CSV and click Use uploaded weather.");
  }
}
$("run").addEventListener("click", () => run().catch(() => {}));
$("compare").addEventListener("click", () => compare().catch(() => {}));
$("compare-materials").addEventListener("click", () => compareMaterials().catch(() => {}));
$("upload-weather").addEventListener("click", uploadWeather);
$("mass_type").addEventListener("change", setMassVisibility);
$("weather_source").addEventListener("change", () => changeWeatherSource());
$("period").addEventListener("change", () => setStatus(`Weather period set to ${$("period").selectedOptions[0].textContent}. Press Run to apply it.`));
$("cancel-job").addEventListener("click", async () => {
  if (!activeJobId) return;
  try {
    await getJSON(`/api/jobs/${activeJobId}/cancel`, {method:"POST"});
    setStatus("Computation cancelled.", true);
    activeJobId = null;
  } catch (e) { setStatus(e.message, true); }
});
$("sheet").addEventListener("click", async () => {
  if (!currentResult || !currentDesign) { setStatus("Run a design before opening the design sheet.", true); return; }
  try {
    const response = await fetch("/api/design-sheet", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({design:currentDesign,result:currentResult})});
    if (!response.ok) throw new Error(`Design sheet failed (HTTP ${response.status}).`);
    const w = window.open();
    if (!w) { setStatus("The browser blocked the design sheet window. Allow pop-ups for VAJRA.", true); return; }
    w.document.write(await response.text()); w.document.close();
  } catch (e) { setStatus(e.message || "Could not open the design sheet.", true); }
});
$("ansys").addEventListener("click", async () => {
  if (!currentResult || !currentDesign) { setStatus("Run a design before preparing the ANSYS package.", true); return; }
  setBusy(true);
  try {
    const response = await fetch(`/api/ansys-package?days=${selectedDays()}&coldest=${useColdest()}&source=${weatherSource()}`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({design:currentDesign})});
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `ANSYS package failed (HTTP ${response.status}).`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "VAJRA_ANSYS_Level_A.zip"; a.click();
    URL.revokeObjectURL(url);
    setStatus("ANSYS Level A package downloaded.");
  } catch (e) { setStatus(e.message || "Could not prepare the ANSYS package.", true); }
  finally { setBusy(false); }
});
(async () => {
  setBusy(true);
  try {
    await waitForHealth();
    materials = await getJSON("/api/materials");
    populateSelect("wall_material", materials.materials);
    populateSelect("roof_material", materials.materials);
    populateSelect("floor_material", materials.materials);
    populateSelect("glazing", materials.glazing);
    $("wall_material").value = "stone_masonry";
    $("roof_material").value = "mineral_wool";
    $("floor_material").value = "concrete_dense";
    $("glazing").value = "double_clear";
    setMassVisibility();
    syncSource();
    const info = await getJSON("/api/weather-info?source=bundled");
    updateProvenance(info.meta);
    try {
      const a = await getJSON("/api/ansys-validation");
      $("ansys-badge").textContent = a.status === "completed" ? "VALIDATED" : "UNAVAILABLE";
      $("ansys-badge").className = a.status === "completed" ? "badge ok" : "badge";
      $("ansys-metrics").innerHTML = [
        ["Solver", a.solver], ["Scope", a.scope], ["Points compared", Number(a.points_compared).toLocaleString()],
        ["Max |ΔT|", `${Number(a.max_abs_difference_c).toFixed(2)} °C`], ["RMS difference", `${Number(a.rms_difference_c).toFixed(2)} °C`]
      ].map(([x,y]) => `<div class="ansys-metric"><div class="metric-label">${x}</div><div class="metric-value">${y}</div></div>`).join("");
      $("ansys-note").textContent = a.note || "";
    } catch (e) {
      $("ansys-badge").textContent = "UNAVAILABLE";
      $("ansys-note").textContent = e.message || "ANSYS validation record unavailable.";
    }
    await loadDefault();
  } catch (e) {
    setStatus(e.message || "The server could not start the page.", true);
  } finally { setBusy(false); }
})();
