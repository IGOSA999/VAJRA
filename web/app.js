let materials = null;
let currentResult = null;
let currentDesign = null;
const $ = (id) => document.getElementById(id);

async function getJSON(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({detail: response.statusText}));
    throw new Error(body.detail || response.statusText);
  }
  return response.json();
}

function populateSelect(id, values) {
  const select = $(id);
  select.innerHTML = "";
  Object.keys(values).forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  });
}

function selectedDays() { return Number($("period").value); }

function setStatus(message, error=false) {
  const el = $("run-status");
  el.textContent = message;
  el.className = error ? "status error" : "status";
}

function setBusy(busy, activeId=null) {
  ["run", "compare", "compare-materials", "sheet", "ansys", "upload-weather"].forEach((id) => {
    const button = $(id);
    button.disabled = busy;
    if (id === activeId && busy) button.textContent = "Computing...";
  });
  if (!busy) {
    $("run").textContent = "Run";
    $("compare").textContent = "Compare designs";
    $("compare-materials").textContent = "Compare wall materials";
    $("sheet").textContent = "Open design sheet";
    $("ansys").textContent = "Prepare ANSYS files";
    $("upload-weather").textContent = "Use uploaded weather";
  }
}

function collectDesign() {
  for (const [id, label] of [["wall_material", "wall"], ["roof_material", "roof"], ["floor_material", "floor"], ["glazing", "glazing"]]) {
    if (!$(id).value) throw new Error(`Choose a ${label} material first. The material list is still loading.`);
  }
  const [ventStart, ventEnd] = $("vent_hours").value.split(",").map(Number);
  const massType = $("mass_type").value;
  const interiorMass = massType === "none" ? null : {
    material: massType === "water" ? "water" : "pcm_paraffin",
    kg: Number($("mass_kg").value),
    surface_area_m2: Number($("mass_area").value),
    h_inside_w_m2k: Number($("mass_h").value),
    ...(massType === "pcm" ? {latent_heat_j_kg: Number($("pcm_latent").value) * 1000, melt_low_c: Number($("pcm_low").value), melt_high_c: Number($("pcm_high").value)} : {})
  };
  return {
    name: "user design",
    site: {lat: Number($("lat").value), lon: Number($("lon").value), elevation_m: 3500},
    geometry: {
      length_m: Number($("length").value), width_m: Number($("width").value), wall_height_m: Number($("height").value),
      roof: {type: $("roof_type").value, pitch_deg: Number($("pitch").value), high_side: "N"}, azimuth_deg: Number($("azimuth").value)
    },
    constructions: {
      wall: [
        ...(Number($("insulation_mm").value) > 0 ? [{material: "mineral_wool", mm: Number($("insulation_mm").value)}] : []),
        {material: $("wall_material").value, mm: Number($("wall_mm").value)}
      ],
      roof: [{material: $("roof_material").value, mm: Number($("roof_mm").value)}],
      floor: [{material: $("floor_material").value, mm: Number($("floor_mm").value)}],
      ground: {soil_depth_m: 2.0}
    },
    openings: Number($("win_w").value) > 0 && Number($("win_h").value) > 0 ? [{
      facade: "main", width_m: Number($("win_w").value), height_m: Number($("win_h").value), glazing: $("glazing").value,
      night_cover: $("cover").value === "yes" ? {r_m2k_per_w: 0.8, from_hour: 17, to_hour: 9} : {}
    }] : [],
    air: {infiltration_ach: Number($("infiltration").value), vent_ach: Number($("vent").value), vent_hours: [ventStart, ventEnd]},
    internal_gains_w: 0,
    solar_split: {floor_and_mass: 0.7},
    comfort: {low_c: Number($("comfort_low").value), high_c: Number($("comfort_high").value)},
    setpoint_c: Number($("comfort_low").value),
    ground_reflectance: 0.2,
    interior_mass: interiorMass
  };
}

function plotResult(result) {
  const x = result.series.time.map(t => new Date(t));
  const comfortLow = Number($("comfort_low").value);
  const comfortHigh = Number($("comfort_high").value);
  const traces = [
    {x, y: result.series.t_air_in_c, mode:"lines", name:"Indoor", line:{color:"#1E2125",width:2}},
    {x, y: result.series.t_air_out_c, mode:"lines", name:"Outside", line:{color:"#2E5E7E",width:1.5}}
  ];
  Plotly.react("temp-chart", traces, {
    margin:{l:45,r:60,t:10,b:42}, paper_bgcolor:"#FBFAF6", plot_bgcolor:"#FBFAF6",
    font:{family:"IBM Plex Sans",color:"#1E2125",size:12}, hovermode:"x unified", showlegend:false,
    xaxis:{gridcolor:"#CFC8BA"}, yaxis:{title:"Temperature (°C)",gridcolor:"#CFC8BA"},
    shapes:[{type:"rect",xref:"paper",x0:0,x1:1,y0:comfortLow,y1:comfortHigh,fillcolor:"#E4DFD2",line:{width:0},layer:"below"}]
  }, {displayModeBar:false,responsive:true});
  const totals = result.summary.flow_totals_kwh || {};
  Plotly.react("flow-chart", [{x:Object.keys(totals), y:Object.values(totals), type:"bar", marker:{color:"#B5521B"}}], {
    margin:{l:50,r:10,t:10,b:65}, paper_bgcolor:"#FBFAF6", plot_bgcolor:"#FBFAF6",
    font:{family:"IBM Plex Sans",color:"#1E2125",size:12}, xaxis:{gridcolor:"#CFC8BA"}, yaxis:{title:"Heat flow (kWh)",gridcolor:"#CFC8BA"}
  }, {displayModeBar:false,responsive:true});
}

function drawSection(design) {
  const g = design.geometry;
  const scale = 55;
  const bodyW = Math.min(470, g.width_m * scale);
  const bodyH = Math.min(210, g.wall_height_m * scale);
  const wallText = design.constructions.wall.map(x => `${x.material} ${x.mm} mm`).join(", ");
  const roofText = design.constructions.roof.map(x => `${x.material} ${x.mm} mm`).join(", ");
  const massText = design.interior_mass ? `${design.interior_mass.material} ${design.interior_mass.kg} kg` : "no interior mass";
  $("drawing").innerHTML = `<svg viewBox="0 0 560 330" aria-label="Shelter section drawing">
    <rect x="35" y="${220-bodyH}" width="${bodyW}" height="${bodyH}" fill="#FBFAF6" stroke="#1E2125" stroke-width="1.2"/>
    <rect x="55" y="${240-bodyH}" width="${Math.max(60,bodyW-40)}" height="${Math.max(70,bodyH-20)}" fill="#F5F2EB" stroke="#1E2125" stroke-width="0.8"/>
    <line x1="35" y1="${220-bodyH}" x2="${35+bodyW}" y2="${205-bodyH}" stroke="#1E2125" stroke-width="1.2"/>
    <line x1="${35+bodyW}" y1="${205-bodyH}" x2="${35+bodyW}" y2="220" stroke="#1E2125" stroke-width="1.2"/>
    <line x1="65" y1="244" x2="485" y2="244" stroke="#CFC8BA" stroke-width="1"/>
    <text x="65" y="264" font-family="IBM Plex Mono" font-size="11" fill="#1E2125">${wallText}</text>
    <text x="65" y="282" font-family="IBM Plex Mono" font-size="11" fill="#5E6368">roof: ${roofText}</text>
    <text x="65" y="300" font-family="IBM Plex Mono" font-size="11" fill="#5E6368">mass: ${massText}</text>
    <text x="465" y="150" font-family="IBM Plex Mono" font-size="11" fill="#1E2125">N</text>
    <line x1="475" y1="190" x2="475" y2="160" stroke="#1E2125" stroke-width="1.2"/><path d="M475 155 l-5 9 h10 z" fill="#1E2125"/>
    <text x="420" y="308" font-family="IBM Plex Mono" font-size="11" fill="#1E2125">1 m</text>
    <line x1="410" y1="300" x2="480" y2="300" stroke="#1E2125" stroke-width="1.2"/>
    <text x="45" y="25" font-family="IBM Plex Sans" font-size="12" fill="#5E6368">Section: ${g.length_m.toFixed(2)} m × ${g.width_m.toFixed(2)} m × ${g.wall_height_m.toFixed(2)} m</text>
  </svg>`;
}

function showMetrics(s) {
  $("metrics").innerHTML = [
    ["Indoor minimum", `${s.t_min_c.toFixed(2)} °C`], ["Indoor maximum", `${s.t_max_c.toFixed(2)} °C`],
    ["Comfort hours", `${s.comfort_hours.toFixed(1)} h`], ["Below low", `${s.hours_below_low.toFixed(1)} h`], ["Heating energy", `${s.heating_kwh.toFixed(2)} kWh`]
  ].map(([label,value]) => `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div></div>`).join("");
}

function updateProvenance(meta) {
  const source = meta.weather_source ?? meta.source ?? "custom";
  const lat = meta.lat ?? "custom";
  const lon = meta.lon ?? "custom";
  $("weather-line").textContent = `Weather: ${source} | ${lat} N ${lon} E | missing hours: ${meta.missing_hours ?? 0}`;
  $("synthetic-banner").hidden = !meta.synthetic;
}

function renderCompare(rows) {
  const keys = ["name","heating_kwh","heating_kwh_per_m2","comfort_hours","overheat_degree_hours","score","orientation_deg","wall_material","insulation_mm","glazing"];
  $("compare-table").innerHTML = `<thead><tr>${keys.map(k => `<th>${k.replaceAll("_"," ")}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${keys.map(k => `<td class="${typeof r[k]==="number"?"num":""}">${typeof r[k]==="number"?Number(r[k]).toFixed(3):r[k]}</td>`).join("")}</tr>`).join("")}</tbody>`;
}

function renderMaterialCompare(rows) {
  const keys = ["wall_material","wall_insulation_mm","heating_kwh","heating_kwh_per_m2","comfort_hours","overheat_degree_hours"];
  $("material-table").innerHTML = `<thead><tr>${keys.map(k => `<th>${k.replaceAll("_"," ")}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${keys.map(k => `<td class="${typeof r[k]==="number"?"num":""}">${typeof r[k]==="number"?Number(r[k]).toFixed(3):r[k]}</td>`).join("")}</tr>`).join("")}</tbody>`;
}

async function run() {
  setBusy(true, "run"); setStatus(`Computing ${selectedDays()} day model...`);
  try {
    currentDesign = collectDesign();
    const result = await getJSON(`/api/run?days=${selectedDays()}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(currentDesign)});
    currentResult = result;
    updateProvenance(result.meta); plotResult(result); drawSection(currentDesign); showMetrics(result.summary);
    setStatus(`Run complete. ${result.meta.period[0]} to ${result.meta.period[1]}. Values are model estimates.`);
  } catch (err) { setStatus(err.message, true); }
  finally { setBusy(false); }
}

async function compare() {
  setBusy(true, "compare"); setStatus(`Comparing 7 designs on the same ${selectedDays()} day weather window...`);
  try {
    const rows = await getJSON(`/api/compare?days=${selectedDays()}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(collectDesign())});
    renderCompare(rows.rows); setStatus(`Design comparison complete. ${rows.rows.length} rows returned.`);
  } catch (err) { $("compare-table").innerHTML = `<tbody><tr><td class="error">${err.message}</td></tr></tbody>`; setStatus(err.message, true); }
  finally { setBusy(false); }
}

async function compareMaterials() {
  setBusy(true, "compare-materials"); setStatus(`Comparing wall materials on the same ${selectedDays()} day weather window...`);
  try {
    const rows = await getJSON(`/api/compare-materials?days=${selectedDays()}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(collectDesign())});
    renderMaterialCompare(rows.rows); setStatus(`Material comparison complete. ${rows.rows.length} wall materials returned.`);
  } catch (err) { $("material-table").innerHTML = `<tbody><tr><td class="error">${err.message}</td></tr></tbody>`; setStatus(err.message, true); }
  finally { setBusy(false); }
}

async function loadDefault() {
  setStatus(`Loading the bundled Leh case for ${selectedDays()} days...`);
  const data = await getJSON(`/api/default?days=${selectedDays()}`);
  currentDesign = data.design; currentResult = data.result;
  updateProvenance(data.result.meta); plotResult(data.result); drawSection(data.design); showMetrics(data.result.summary);
  setStatus(`Default case loaded. ${data.result.meta.period[0]} to ${data.result.meta.period[1]}. Values are model estimates.`);
}

async function uploadWeather() {
  const file = $("weather_file").files[0];
  if (!file) { setStatus("Choose a weather CSV first.", true); return; }
  setBusy(true, "upload-weather"); setStatus(`Reading ${file.name}...`);
  try {
    const form = new FormData(); form.append("file", file);
    const out = await getJSON("/api/upload-weather", {method:"POST", body:form});
    updateProvenance(out.source);
    setStatus(`Weather file loaded: ${out.rows} hourly rows. Press Run to simulate it.`);
    $("weather_file").value = "";
  } catch (err) { setStatus(err.message, true); }
  finally { setBusy(false); }
}

$("run").addEventListener("click", run);
$("compare").addEventListener("click", compare);
$("compare-materials").addEventListener("click", compareMaterials);
$("upload-weather").addEventListener("click", uploadWeather);
$("period").addEventListener("change", () => setStatus(`Weather period set to ${selectedDays()} days. Press Run to apply it.`));
$("sheet").addEventListener("click", async () => {
  if (!currentResult || !currentDesign) { setStatus("Run a design before opening the design sheet.", true); return; }
  setStatus("Opening the design sheet...");
  const response = await fetch("/api/design-sheet", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({design:currentDesign,result:currentResult})});
  const html = await response.text(); const w = window.open();
  if (!w) { setStatus("The browser blocked the new window. Allow pop-ups for VAJRA.", true); return; }
  w.document.write(html); w.document.close();
});
$("ansys").addEventListener("click", async () => {
  if (!currentResult || !currentDesign) { setStatus("Run a design before preparing ANSYS files.", true); return; }
  setBusy(true, "ansys"); setStatus("Preparing ANSYS Level A files...");
  try {
    const out = await getJSON(`/api/ansys?days=${selectedDays()}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({design:currentDesign})});
    setStatus(`Prepared ${out.files.length} ANSYS files. Check exports/ansys.`);
  } catch (err) { setStatus(err.message, true); }
  finally { setBusy(false); }
});

(async () => {
  setBusy(true);
  try {
    materials = await getJSON("/api/materials");
    populateSelect("wall_material", materials.materials); populateSelect("roof_material", materials.materials); populateSelect("floor_material", materials.materials); populateSelect("glazing", materials.glazing);
    $("wall_material").value = "stone_masonry"; $("roof_material").value = "mineral_wool"; $("floor_material").value = "concrete_dense"; $("glazing").value = "double_clear";
    const info = await getJSON("/api/weather-info"); updateProvenance(info.meta);
    await loadDefault();
  } catch (err) { setStatus(err.message, true); }
  finally { setBusy(false); }
})();
