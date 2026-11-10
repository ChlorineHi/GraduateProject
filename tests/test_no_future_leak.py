import numpy as np
import pandas as pd

from urbannoise.scenarios import FutureLeakError, cell_id, open_scenario


def _frame(future_x: int, future_y: int) -> pd.DataFrame:
    rows = [
        ("p", 0, 0, 0, 0),
        ("p", 0, 1, 1, 0),
        ("p", 0, 2, future_x, future_y),
        ("q", 0, 0, 2, 2),
        ("q", 0, 1, 2, 2),
        ("q", 0, 2, future_x, 0),
    ]
    return pd.DataFrame(
        [
            {
                "participant_id": participant_id,
                "day": day,
                "timeslot": timeslot,
                "x": x_coord,
                "y": y_coord,
                "data_source": "synthetic_shaped_real_schema_example",
                "coordinate_system": "fixture_virtual_grid",
                "slots_per_day": 4,
                "schema_example": "not_a_city_extract",
            }
            for participant_id, day, timeslot, x_coord, y_coord in rows
        ]
    )


def test_decision_is_unchanged_when_future_locations_change():
    early = open_scenario("real_mobility", mobility_frame=_frame(4, 4), seed=1)
    late = open_scenario("real_mobility", mobility_frame=_frame(9, 9), seed=1)
    first = early.decide(decision_slot=1, target_slot=2)
    second = late.decide(decision_slot=1, target_slot=2)
    assert first["slots_visible"] == 2
    assert second["slots_visible"] == 2
    assert cell_id(4, 4) not in first["cells"]
    assert cell_id(9, 9) not in second["cells"]
    assert first["participants"] == second["participants"] == ["p", "q"]
    assert first["cells"] == second["cells"]
    assert first["reach"].shape == second["reach"].shape
    assert np.allclose(first["reach"], second["reach"])
    assert all(slot <= 1 for slot, _purpose in early.table.access_log)
    assert early.table.access_log
    assert {purpose for _slot, purpose in early.table.access_log} == {"decision"}


def test_decision_lock_rejects_future_location_reads():
    scenario = open_scenario("real_mobility", mobility_frame=_frame(4, 4), seed=1)
    with scenario.table.lock_decisions(1):
        try:
            scenario.table.read_cell("p", 2, purpose="decision")
        except FutureLeakError:
            pass
        else:
            raise AssertionError("decision read of a future slot was allowed")
        try:
            scenario.table.read_cell("p", 2, purpose="execution")
        except FutureLeakError:
            pass
        else:
            raise AssertionError("execution read was allowed inside a decision lock")
        assert scenario.table.read_cell("p", 1, purpose="decision") == cell_id(1, 0)


def test_execution_reads_the_later_slot_without_editing_it():
    scenario = open_scenario("real_mobility", mobility_frame=_frame(4, 4), seed=2)
    fingerprint = scenario.table.fingerprint()
    scenario.decide(decision_slot=1, target_slot=2)
    scenario.table.access_log.clear()
    hit = scenario.execute_task("p", cell_id(4, 4), task_slot=2, decision_slot=1)
    miss = scenario.execute_task("p", cell_id(0, 0), task_slot=2, decision_slot=1)
    assert hit["success"] is True
    assert hit["actual_cell"] == cell_id(4, 4)
    assert miss["success"] is False
    assert miss["actual_cell"] == cell_id(4, 4)
    assert (2, "execution") in scenario.table.access_log
    assert not any(purpose == "decision" and slot > 1 for slot, purpose in scenario.table.access_log)
    assert scenario.table.fingerprint() == fingerprint
    assert scenario.table.read_cell("p", 2, purpose="execution") == cell_id(4, 4)
    assert scenario.table.read_cell("q", 2, purpose="execution") == cell_id(4, 0)
