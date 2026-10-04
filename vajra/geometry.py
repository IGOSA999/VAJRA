from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class Surface:
    name: str
    kind: str
    area_m2: float
    tilt_deg: float
    azimuth_deg: float
    orientation_label: str


def norm_azimuth(value: float) -> float:
    return value % 360.0


def build_surfaces(design: dict) -> list[Surface]:
    g = design["geometry"]
    length = float(g["length_m"])
    width = float(g["width_m"])
    height = float(g["wall_height_m"])
    main_az = norm_azimuth(float(g.get("azimuth_deg", 180.0)))
    walls = [
        Surface("wall_main", "wall", width * height, 90.0, main_az, "main facade"),
        Surface("wall_back", "wall", width * height, 90.0, norm_azimuth(main_az + 180), "back facade"),
        Surface("wall_left", "wall", length * height, 90.0, norm_azimuth(main_az - 90), "left facade"),
        Surface("wall_right", "wall", length * height, 90.0, norm_azimuth(main_az + 90), "right facade"),
    ]
    roof = g.get("roof", {"type": "flat", "pitch_deg": 0, "high_side": "N"})
    pitch = float(roof.get("pitch_deg", 0.0))
    roof_type = roof.get("type", "flat")
    if roof_type == "gable":
        half = width / 2.0
        slope_len = sqrt(half * half + (half * __import__("math").tan(__import__("math").radians(pitch))) ** 2)
        area_each = length * slope_len
        roofs = [
            Surface("roof_north", "roof", area_each, pitch, norm_azimuth(main_az), "gable plane 1"),
            Surface("roof_south", "roof", area_each, pitch, norm_azimuth(main_az + 180), "gable plane 2"),
        ]
    elif roof_type == "mono_pitch":
        area = length * width / max(__import__("math").cos(__import__("math").radians(pitch)), 1e-6)
        # A north high side means the roof falls toward south and its exposed normal faces south.
        az = norm_azimuth(180.0 if roof.get("high_side", "N") == "N" else 0.0)
        roofs = [Surface("roof", "roof", area, pitch, az, "mono-pitch roof")]
    else:
        roofs = [Surface("roof", "roof", length * width, 0.0, 0.0, "flat roof")]
    floor = Surface("floor", "floor", length * width, 0.0, 0.0, "ground coupled floor")
    return walls + roofs + [floor]


def wall_area_by_facade(design: dict) -> dict[str, float]:
    g = design["geometry"]
    return {
        "main": float(g["width_m"]) * float(g["wall_height_m"]),
        "back": float(g["width_m"]) * float(g["wall_height_m"]),
        "left": float(g["length_m"]) * float(g["wall_height_m"]),
        "right": float(g["length_m"]) * float(g["wall_height_m"]),
    }


def surface_to_volume_ratio(design: dict) -> float:
    g = design["geometry"]
    l, w, h = float(g["length_m"]), float(g["width_m"]), float(g["wall_height_m"])
    volume = l * w * h
    opaque = 2 * (l + w) * h + l * w
    return opaque / volume
