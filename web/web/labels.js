const LABELS = {
  stone_masonry: "Stone masonry", concrete_dense: "Dense concrete", fired_clay_brick: "Fired clay brick",
  rammed_earth: "Rammed earth", adobe: "Adobe", eps: "EPS insulation", xps: "XPS insulation",
  mineral_wool: "Mineral wool", pir: "PIR insulation", timber: "Timber", water: "Water",
  pcm_paraffin: "Paraffin PCM", soil: "Soil", single_clear: "Single glazing, clear",
  double_clear: "Double glazing, clear", double_low_e: "Double glazing, low-e"
};
const FLOW_LABELS = {
  wall_main:"Main wall", wall_back:"Back wall", wall_left:"Left wall", wall_right:"Right wall",
  roof:"Roof", floor:"Floor", glazing:"Glazing", ventilation:"Ventilation", interior_mass:"Interior mass"
};
const COLUMN_LABELS = {
  heating_kwh:"Heating energy (kWh)", heating_kwh_per_m2:"Per floor area (kWh/m²)",
  t_min_c:"Minimum indoor temperature (°C)",
  hours_above_zero:"Hours above 0 °C (h)", overheat_degree_hours:"Overheating (K·h)",
  mean_delta_c:"Mean indoor − outside (K)", orientation_deg:"Orientation (°)", insulation_mm:"Insulation (mm)",
  wall_material:"Wall material", glazing:"Glazing", wall_insulation_mm:"Insulation (mm)"
};
function humanize(value) {
  if (value == null) return "";
  const key = String(value);
  return LABELS[key] || FLOW_LABELS[key] || key.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
}
function flowLabel(value) { return FLOW_LABELS[value] || humanize(value); }
function columnLabel(value) { return COLUMN_LABELS[value] || humanize(value); }
