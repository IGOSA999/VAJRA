from pathlib import Path
from vajra.ansys_export import export_ansys_case, ROOT
from vajra.weather import synthetic_leh

def test_ansys_export_files():
    weather = synthetic_leh(days=1)
    design = {
        "name": "test_case",
        "site": {"lat": 34.1526, "lon": 77.5771, "elevation_m": 3500},
        "geometry": {"length_m": 4, "width_m": 3, "wall_height_m": 2.4, "roof": {"type": "mono_pitch", "pitch_deg": 15, "high_side": "N"}, "azimuth_deg": 180},
        "constructions": {"wall": [{"material": "stone_masonry", "mm": 300}], "roof": [{"material": "mineral_wool", "mm": 100}, {"material": "timber", "mm": 25}], "floor": [{"material": "concrete_dense", "mm": 100}], "ground": {"soil_depth_m": 2}},
        "openings": [{"facade": "main", "width_m": 1.8, "height_m": 1.2, "glazing": "double_clear", "night_cover": {"r_m2k_per_w": 0.8, "from_hour": 17, "to_hour": 9}}],
        "air": {"infiltration_ach": 0.5, "vent_ach": 0.0, "vent_hours": [11,15]},
        "internal_gains_w": 0, "solar_split": {"floor_and_mass": 0.7}, "comfort": {"low_c": 15, "high_c": 28}, "setpoint_c": 15}
    files = export_ansys_case(design, weather, ROOT / "data" / "materials.csv", ROOT / "data" / "glazing.csv")
    names = {p.name for p in files}
    assert {"boundary_conditions.csv", "materials.csv", "wall_panel.mac", "boundary_conditions_table.txt", "boundary_conditions_table_inside.txt", "python_wall_results.csv"} <= names
    boundary = Path(ROOT, "exports", "ansys", "boundary_conditions.csv").read_text()
    macro = Path(ROOT, "exports", "ansys", "wall_panel.mac").read_text()
    assert "time" in boundary and "sol_air_c" in boundary and "h_in_w_m2k" in boundary
    assert "/PREP7" in macro
    assert "ET,1,SOLID278" in macro
    assert "VATT," in macro
    assert "*TREAD,TAMB" in macro
    assert "*TREAD,TIND" in macro
    assert "SF,ALL,CONV" in macro
    assert "ANTYPE,TRANS" in macro
    assert "NSOL,2,INNER_NODE,TEMP" in macro
    assert "*CFOPEN,ansys_wall_results,csv" in macro
