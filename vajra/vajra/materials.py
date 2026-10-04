from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv


@dataclass(frozen=True)
class Material:
    name: str
    label: str
    lambda_w_mk: float
    rho_kg_m3: float
    c_j_kgk: float
    emissivity: float
    absorptance: float
    source: str
    value_status: str
    notes: str = ""


@dataclass(frozen=True)
class Glazing:
    name: str
    label: str
    u_w_m2k: float
    shgc: float
    source: str
    value_status: str


def _as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value in {key}: {row.get(key)!r}") from exc


def load_materials(path: Path) -> dict[str, Material]:
    materials: dict[str, Material] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if not row.get("source"):
                raise ValueError(f"Material row {row.get('name')} has no source")
            name = row["name"].strip()
            materials[name] = Material(
                name=name,
                label=(row.get("label") or name.replace("_", " ").title()).strip(),
                lambda_w_mk=_as_float(row, "lambda_w_mk"),
                rho_kg_m3=_as_float(row, "rho_kg_m3"),
                c_j_kgk=_as_float(row, "c_j_kgk"),
                emissivity=_as_float(row, "emissivity"),
                absorptance=_as_float(row, "absorptance"),
                source=row["source"].strip(),
                value_status=row["value_status"].strip(),
                notes=row.get("notes", "").strip(),
            )
    return materials


def load_glazing(path: Path) -> dict[str, Glazing]:
    glazing: dict[str, Glazing] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            name = row["name"].strip()
            glazing[name] = Glazing(
                name=name,
                label=(row.get("label") or name.replace("_", " ").title()).strip(),
                u_w_m2k=_as_float(row, "u_w_m2k"),
                shgc=_as_float(row, "shgc"),
                source=row["source"].strip(),
                value_status=row["value_status"].strip(),
            )
    return glazing
