from vajra.solar import plane_of_array
from vajra.weather import synthetic_leh


def test_t04_solar_closure_and_sense():
    wf = synthetic_leh(14)
    south = plane_of_array(90, 180, wf.frame.index, wf.frame.ghi_wm2.to_numpy(), wf.frame.dhi_wm2.to_numpy(), wf.frame.dni_wm2.to_numpy(), 34.1526, 77.5771, 0.2)
    north = plane_of_array(90, 0, wf.frame.index, wf.frame.ghi_wm2.to_numpy(), wf.frame.dhi_wm2.to_numpy(), wf.frame.dni_wm2.to_numpy(), 34.1526, 77.5771, 0.2)
    assert float(south.sum()) > float(north.sum())
    assert (wf.frame.ghi_wm2 >= 0).all()
