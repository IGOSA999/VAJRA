import pandas as pd
from vajra.api import default_design, MATERIALS, GLAZING
from vajra.solver import simulate
from vajra.weather import synthetic_leh


def test_t03_step_convergence():
    wf = synthetic_leh(4)
    d = default_design()
    d["constructions"]["wall"] = [{"material":"mineral_wool","mm":100}]
    d["constructions"]["roof"] = [{"material":"mineral_wool","mm":100}]
    d["constructions"]["floor"] = [{"material":"eps","mm":50}]
    d["openings"] = []
    r15 = simulate(d, wf, MATERIALS, GLAZING, 15, "free")
    r10 = simulate(d, wf, MATERIALS, GLAZING, 10, "free")
    a = pd.Series(r15["series"]["t_air_in_c"], index=pd.to_datetime(r15["series"]["time"], utc=True)).resample("1h").mean()
    b = pd.Series(r10["series"]["t_air_in_c"], index=pd.to_datetime(r10["series"]["time"], utc=True)).resample("1h").mean()
    aligned = pd.concat([a,b], axis=1).dropna()
    assert float((aligned.iloc[:,0] - aligned.iloc[:,1]).abs().max()) < 0.2
