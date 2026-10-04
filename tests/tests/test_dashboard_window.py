from vajra.api import _coldest_fortnight
from vajra.weather import synthetic_leh


def test_long_file_is_cut_to_fourteen_days():
    cut = _coldest_fortnight(synthetic_leh(60))
    assert len(cut.frame) == 14 * 24
    assert "coldest 14 days" in cut.meta["window_note"]


def test_short_file_is_left_alone():
    w = synthetic_leh(14)
    assert len(_coldest_fortnight(w).frame) == len(w.frame)
