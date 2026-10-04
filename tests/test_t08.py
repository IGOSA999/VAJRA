from vajra.api import default_design, MATERIALS, GLAZING
from vajra.optimise import compare_designs
from vajra.weather import synthetic_leh


def test_t08_reproducibility_and_ranking():
    base = default_design()
    wf = synthetic_leh(3)
    a = compare_designs(base, wf, MATERIALS, GLAZING, candidate_count=6)
    b = compare_designs(base, wf, MATERIALS, GLAZING, candidate_count=6)
    assert a == b
    baseline = next(x for x in a if x["name"] == base["name"])
    assert a[0]["score"] <= baseline["score"]
